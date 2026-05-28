"""
AgentLink Protocol - WebSocket Server

Runs on each agent instance, accepting incoming connections from peers.
Handles the handshake, message routing, and session management.

Usage:
    server = AgentLinkServer(name="My Agent", port=7600)
    server.on_message(my_handler)
    await server.start()
"""

import asyncio
import json
import logging
import time
import uuid
from typing import Optional, Callable, Any

try:
    import websockets
    from websockets.asyncio.server import serve, ServerConnection
    HAS_WEBSOCKETS = True
except ImportError:
    HAS_WEBSOCKETS = False

try:
    from fastapi import FastAPI, WebSocket, WebSocketDisconnect
    from fastapi.responses import JSONResponse
    import uvicorn
    HAS_FASTAPI = True
except ImportError:
    HAS_FASTAPI = False

from .protocol import (
    AgentInfo, MessageType, HandshakePhase,
    parse_message, is_request, is_notification, is_response,
    make_response, make_error, make_heartbeat, make_message,
)
from .handshake import HandshakeSession, HandshakeState
from .crypto import create_keypair, generate_nonce

logger = logging.getLogger("agentlink.server")


class PeerSession:
    """Represents an active connection to a peer agent."""
    
    def __init__(self, websocket, handshake: HandshakeSession):
        self.websocket = websocket
        self.handshake = handshake
        self.connected_at = time.time()
        self.last_activity = time.time()
        self.message_count = 0
    
    @property
    def peer_id(self) -> Optional[str]:
        if self.handshake.peer_info:
            return self.handshake.peer_info.agent_id
        return None
    
    @property
    def is_active(self) -> bool:
        return self.handshake.is_complete
    
    def touch(self):
        self.last_activity = time.time()
        self.message_count += 1


class AgentLinkServer:
    """
    AgentLink WebSocket server.
    
    Accepts incoming WebSocket connections, performs the three-phase
    handshake, and routes messages to registered handlers.
    """
    
    def __init__(
        self,
        name: str = "AgentLink Server",
        agent_id: str = None,
        agent_type: str = "custom",
        port: int = 7600,
        host: str = "0.0.0.0",
    ):
        self.name = name
        self.agent_id = agent_id or f"agent-{uuid.uuid4().hex[:8]}"
        self.agent_type = agent_type
        self.port = port
        self.host = host
        
        # Crypto
        self.keypair = create_keypair()
        
        # Agent info for handshake
        self.agent_info = AgentInfo(
            agent_id=self.agent_id,
            agent_name=self.name,
            agent_type=self.agent_type,
            public_key=self.keypair.public_encryption_key_b64,
            capabilities=["messaging", "file-transfer", "task-collab"],
        )
        
        # Active peer sessions
        self.peers: dict[str, PeerSession] = {}
        
        # Message handlers
        self._message_handlers: list[Callable] = []
        self._connect_handlers: list[Callable] = []
        self._disconnect_handlers: list[Callable] = []
        
        # Server state
        self._server = None
        self._running = False
    
    def on_message(self, handler: Callable):
        """Register a message handler. Called with (peer_id, message_dict)."""
        self._message_handlers.append(handler)
    
    def on_connect(self, handler: Callable):
        """Register a connection handler. Called with (peer_id, peer_info)."""
        self._connect_handlers.append(handler)
    
    def on_disconnect(self, handler: Callable):
        """Register a disconnection handler. Called with (peer_id,)."""
        self._disconnect_handlers.append(handler)
    
    async def start(self):
        """Start the WebSocket server."""
        if not HAS_WEBSOCKETS:
            raise ImportError(
                "websockets library required. "
                "Install with: pip install websockets"
            )
        
        logger.info(f"[SERVER] Starting AgentLink server on {self.host}:{self.port}")
        logger.info(f"[SERVER] Agent: {self.name} ({self.agent_id})")
        logger.info(f"[SERVER] Public key: {self.keypair.public_encryption_key_b64[:20]}...")
        
        self._server = await serve(
            self._handle_connection,
            self.host,
            self.port,
        )
        self._running = True
        
        logger.info(f"[SERVER] AgentLink server listening on ws://{self.host}:{self.port}")
        
        # Start heartbeat task
        asyncio.create_task(self._heartbeat_loop())
        
        return self._server
    
    async def stop(self):
        """Stop the server."""
        self._running = False
        if self._server:
            self._server.close()
            await self._server.wait_closed()
        logger.info("[SERVER] AgentLink server stopped")
    
    async def _handle_connection(self, websocket: ServerConnection):
        """Handle a new WebSocket connection."""
        peer_id = None
        try:
            # Create a new handshake session (we are responder)
            handshake = HandshakeSession(
                agent_info=self.agent_info.model_copy(),
                keypair=self.keypair,
                role="responder",
            )
            
            peer_session = PeerSession(websocket, handshake)
            
            logger.info(f"[SERVER] New connection from {websocket.remote_address}")
            
            async for raw_message in websocket:
                try:
                    peer_session.touch()
                    await self._process_message(peer_session, raw_message)
                except Exception as e:
                    logger.error(f"[SERVER] Error processing message: {e}")
                    await websocket.send(make_error(-32603, str(e)))
            
        except websockets.exceptions.ConnectionClosed:
            logger.info(f"[SERVER] Connection closed: {peer_id}")
        except Exception as e:
            logger.error(f"[SERVER] Connection error: {e}")
        finally:
            if peer_id and peer_id in self.peers:
                del self.peers[peer_id]
                for handler in self._disconnect_handlers:
                    try:
                        result = handler(peer_id)
                        if asyncio.iscoroutine(result):
                            await result
                    except Exception as e:
                        logger.error(f"[SERVER] Disconnect handler error: {e}")
    
    async def _process_message(self, peer_session: PeerSession, raw: str):
        """Process a single message from a peer."""
        try:
            data = parse_message(raw)
        except ValueError as e:
            logger.warning(f"[SERVER] Invalid message: {e}")
            return
        
        handshake = peer_session.handshake
        
        # Handle handshake messages
        if data.get("method") == MessageType.HANDSHAKE.value:
            await self._handle_handshake(peer_session, data)
            return
        
        # Only process non-handshake messages if handshake is complete
        if not handshake.is_complete:
            logger.warning("[SERVER] Received message before handshake complete")
            await peer_session.websocket.send(
                make_error(-32002, "Handshake not complete")
            )
            return
        
        peer_id = handshake.peer_info.agent_id
        
        # Handle different message types
        method = data.get("method", "")
        
        if method == MessageType.HEARTBEAT.value:
            # Respond with heartbeat
            await peer_session.websocket.send(make_heartbeat())
        
        elif method == MessageType.SEND.value:
            # Route to message handlers
            for handler in self._message_handlers:
                try:
                    result = handler(peer_id, data.get("params", {}))
                    if asyncio.iscoroutine(result):
                        await result
                except Exception as e:
                    logger.error(f"[SERVER] Message handler error: {e}")
            
            # Send acknowledgment
            if "id" in data:
                await peer_session.websocket.send(
                    make_response({"status": "delivered"}, data["id"])
                )
        
        elif method == MessageType.DISCONNECT.value:
            logger.info(f"[SERVER] Peer {peer_id} disconnecting")
            await peer_session.websocket.close()
        
        else:
            logger.warning(f"[SERVER] Unknown method: {method}")
    
    async def _handle_handshake(self, peer_session: PeerSession, data: dict):
        """Handle handshake messages."""
        handshake = peer_session.handshake
        params = data.get("params", {})
        phase = params.get("phase")
        
        try:
            if phase == HandshakePhase.HELLO.value and handshake.role == "responder":
                # Phase 1: Receive HELLO, send WELCOME
                raw = json.dumps(data)
                welcome_msg = handshake.receive_hello(raw)
                await peer_session.websocket.send(welcome_msg)
                logger.info(f"[SERVER] Handshake: sent WELCOME")
                
            elif phase == HandshakePhase.READY.value and handshake.role == "responder":
                # Phase 3: Receive READY
                raw = json.dumps(data)
                handshake.receive_ready(raw)
                
                peer_id = handshake.peer_info.agent_id
                self.peers[peer_id] = peer_session
                
                logger.info(f"[SERVER] Handshake COMPLETE with {peer_id}")
                
                # Notify connect handlers
                for handler in self._connect_handlers:
                    try:
                        result = handler(peer_id, handshake.peer_info)
                        if asyncio.iscoroutine(result):
                            await result
                    except Exception as e:
                        logger.error(f"[SERVER] Connect handler error: {e}")
            
            else:
                logger.warning(f"[SERVER] Unexpected handshake phase: {phase}")
        
        except Exception as e:
            logger.error(f"[SERVER] Handshake error: {e}")
            await peer_session.websocket.send(
                make_error(-32001, f"Handshake failed: {e}", data.get("id"))
            )
    
    async def send_to_peer(self, peer_id: str, message: str) -> bool:
        """Send a message to a connected peer."""
        if peer_id not in self.peers:
            logger.warning(f"[SERVER] Peer {peer_id} not connected")
            return False
        
        peer = self.peers[peer_id]
        try:
            await peer.websocket.send(message)
            return True
        except Exception as e:
            logger.error(f"[SERVER] Failed to send to {peer_id}: {e}")
            return False
    
    async def broadcast(self, message: str):
        """Send a message to all connected peers."""
        for peer_id in list(self.peers.keys()):
            await self.send_to_peer(peer_id, message)
    
    async def _heartbeat_loop(self):
        """Send periodic heartbeats to all peers."""
        while self._running:
            await asyncio.sleep(30)
            heartbeat = make_heartbeat()
            for peer_id in list(self.peers.keys()):
                try:
                    await self.send_to_peer(peer_id, heartbeat)
                except Exception:
                    pass
    
    def get_peers(self) -> list[dict]:
        """Get info about connected peers."""
        result = []
        for peer_id, session in self.peers.items():
            result.append({
                "peer_id": peer_id,
                "peer_name": session.handshake.peer_info.agent_name if session.handshake.peer_info else "unknown",
                "connected_at": session.connected_at,
                "message_count": session.message_count,
            })
        return result


async def run_server(
    name: str = "AgentLink Server",
    agent_type: str = "custom",
    port: int = 7600,
    host: str = "0.0.0.0",
    message_handler: Callable = None,
):
    """
    Convenience function to start an AgentLink server.
    
    Args:
        name: Display name for this agent
        agent_type: Type identifier (e.g., "hermes-agent", "claude-code")
        port: WebSocket port
        host: Bind address
        message_handler: Async function called with (peer_id, message_params)
    """
    server = AgentLinkServer(
        name=name,
        agent_type=agent_type,
        port=port,
        host=host,
    )
    
    if message_handler:
        server.on_message(message_handler)
    
    # Print connection info
    server.on_connect(lambda pid, info: print(f"\n[+] Peer connected: {info.agent_name} ({pid})"))
    server.on_disconnect(lambda pid: print(f"\n[-] Peer disconnected: {pid}"))
    
    await server.start()
    
    print(f"\nAgentLink Server running on ws://{host}:{port}")
    print(f"Agent ID: {server.agent_id}")
    print(f"Public Key: {server.keypair.public_encryption_key_b64}")
    print("Waiting for connections...\n")
    
    # Keep running
    try:
        while True:
            await asyncio.sleep(1)
    except KeyboardInterrupt:
        await server.stop()


if __name__ == "__main__":
    import argparse
    
    parser = argparse.ArgumentParser(description="AgentLink Server")
    parser.add_argument("--name", default="My Agent", help="Agent display name")
    parser.add_argument("--type", default="custom", help="Agent type")
    parser.add_argument("--port", type=int, default=7600, help="WebSocket port")
    parser.add_argument("--host", default="0.0.0.0", help="Bind address")
    args = parser.parse_args()
    
    logging.basicConfig(level=logging.INFO)
    
    def print_message(peer_id, params):
        content = params.get("content", "")
        print(f"\n[{peer_id}]: {content}")
    
    asyncio.run(run_server(
        name=args.name,
        agent_type=args.type,
        port=args.port,
        host=args.host,
        message_handler=print_message,
    ))
