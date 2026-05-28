"""
AgentLink Protocol - WebSocket Client

Connects to a peer AgentLink server, performs the handshake,
and provides a simple interface for sending/receiving messages.

Usage:
    client = AgentLinkClient(name="My Agent")
    await client.connect("ws://192.168.1.100:7600")
    await client.send("Hello from my agent!")
    async for msg in client.messages():
        print(msg)
"""

import asyncio
import json
import logging
import time
import uuid
from typing import Optional, Callable, AsyncIterator

try:
    import websockets
    from websockets.asyncio.client import connect as ws_connect
    HAS_WEBSOCKETS = True
except ImportError:
    HAS_WEBSOCKETS = False

from .protocol import (
    AgentInfo, MessageType, HandshakePhase,
    parse_message, make_handshake, make_message, make_heartbeat,
    make_response, make_error,
)
from .handshake import HandshakeSession, HandshakeState
from .crypto import create_keypair

logger = logging.getLogger("agentlink.client")


class AgentLinkClient:
    """
    AgentLink WebSocket client.
    
    Connects to a peer AgentLink server, performs the initiator-side
    handshake, and provides methods for sending and receiving messages.
    """
    
    def __init__(
        self,
        name: str = "AgentLink Client",
        agent_id: str = None,
        agent_type: str = "custom",
    ):
        self.name = name
        self.agent_id = agent_id or f"agent-{uuid.uuid4().hex[:8]}"
        self.agent_type = agent_type
        
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
        
        # Connection state
        self._websocket = None
        self._handshake: Optional[HandshakeSession] = None
        self._connected = False
        self._message_queue = asyncio.Queue()
        self._response_futures: dict[str, asyncio.Future] = {}
        
        # Handlers
        self._message_handlers: list[Callable] = []
    
    @property
    def is_connected(self) -> bool:
        return self._connected and self._handshake and self._handshake.is_complete
    
    @property
    def peer_info(self) -> Optional[AgentInfo]:
        if self._handshake:
            return self._handshake.peer_info
        return None
    
    @property
    def session_id(self) -> Optional[str]:
        if self._handshake:
            return self._handshake.session_id
        return None
    
    def on_message(self, handler: Callable):
        """Register a message handler. Called with (message_params,)."""
        self._message_handlers.append(handler)
    
    async def connect(self, target: str, pairing_code: str = None) -> bool:
        """
        Connect to an AgentLink server.
        
        Args:
            target: WebSocket URL (e.g., "ws://192.168.1.100:7600")
            pairing_code: Optional pairing code for authentication
        
        Returns:
            True if connected and handshake completed successfully
        """
        if not HAS_WEBSOCKETS:
            raise ImportError(
                "websockets library required. "
                "Install with: pip install websockets"
            )
        
        logger.info(f"[CLIENT] Connecting to {target}...")
        
        try:
            self._websocket = await ws_connect(target)
            self._connected = True
            
            # Initiate handshake
            self._handshake = HandshakeSession(
                agent_info=self.agent_info.model_copy(),
                keypair=self.keypair,
                role="initiator",
            )
            
            # Phase 1: Send HELLO
            hello_msg = self._handshake.start()
            await self._websocket.send(hello_msg)
            logger.info("[CLIENT] Sent HELLO")
            
            # Phase 2: Receive WELCOME
            welcome_msg = await self._websocket.recv()
            ready_msg = self._handshake.receive_welcome(welcome_msg)
            logger.info("[CLIENT] Received WELCOME")
            
            # Phase 3: Send READY
            await self._websocket.send(ready_msg)
            self._handshake.complete_initiator()
            logger.info("[CLIENT] Sent READY - Handshake COMPLETE")
            
            # Start message listener
            asyncio.create_task(self._listen_loop())
            
            # Send capabilities
            await self._send_capabilities()
            
            return True
            
        except Exception as e:
            logger.error(f"[CLIENT] Connection failed: {e}")
            self._connected = False
            return False
    
    async def disconnect(self):
        """Gracefully disconnect from the peer."""
        if self._websocket:
            try:
                # Send disconnect notification
                disconnect_msg = json.dumps({
                    "jsonrpc": "2.0",
                    "method": MessageType.DISCONNECT.value,
                    "params": {"reason": "user_disconnect"},
                })
                await self._websocket.send(disconnect_msg)
                await self._websocket.close()
            except Exception:
                pass
        
        self._connected = False
        self._handshake = None
        logger.info("[CLIENT] Disconnected")
    
    async def send(self, content: str, project: str = None, metadata: dict = None) -> str:
        """
        Send a message to the connected peer.
        
        Returns the message ID.
        """
        if not self.is_connected:
            raise ConnectionError("Not connected to a peer")
        
        msg = make_message(content, project=project, metadata=metadata)
        await self._websocket.send(msg)
        
        # Parse to get message ID
        data = json.loads(msg)
        return data.get("id")
    
    async def send_raw(self, method: str, params: dict) -> str:
        """Send a raw JSON-RPC message."""
        if not self.is_connected:
            raise ConnectionError("Not connected to a peer")
        
        msg = json.dumps({
            "jsonrpc": "2.0",
            "method": method,
            "params": params,
            "id": str(uuid.uuid4()),
        })
        await self._websocket.send(msg)
        return json.loads(msg).get("id")
    
    async def messages(self) -> AsyncIterator[dict]:
        """
        Async iterator that yields incoming messages.
        
        Usage:
            async for msg in client.messages():
                print(msg["params"]["content"])
        """
        while self._connected:
            try:
                msg = await self._message_queue.get()
                yield msg
            except asyncio.CancelledError:
                break
    
    async def _listen_loop(self):
        """Background task that listens for incoming messages."""
        try:
            async for raw_message in self._websocket:
                try:
                    data = parse_message(raw_message)
                    await self._process_message(data)
                except ValueError as e:
                    logger.warning(f"[CLIENT] Invalid message: {e}")
        except websockets.exceptions.ConnectionClosed:
            logger.info("[CLIENT] Connection closed by peer")
        except Exception as e:
            logger.error(f"[CLIENT] Listen error: {e}")
        finally:
            self._connected = False
            # Put None to signal end of message stream
            await self._message_queue.put(None)
    
    async def _process_message(self, data: dict):
        """Process an incoming message."""
        method = data.get("method", "")
        
        # Handle responses to our requests
        if "id" in data and "result" in data:
            msg_id = data["id"]
            if msg_id in self._response_futures:
                self._response_futures[msg_id].set_result(data["result"])
                return
        
        # Handle heartbeat
        if method == MessageType.HEARTBEAT.value:
            await self._websocket.send(make_heartbeat())
            return
        
        # Handle incoming messages
        if method == MessageType.SEND.value:
            # Put in queue for async iteration
            await self._message_queue.put(data)
            
            # Call registered handlers
            for handler in self._message_handlers:
                try:
                    result = handler(data.get("params", {}))
                    if asyncio.iscoroutine(result):
                        await result
                except Exception as e:
                    logger.error(f"[CLIENT] Message handler error: {e}")
            
            # Send delivery confirmation
            if "id" in data:
                await self._websocket.send(
                    make_response({"status": "delivered"}, data["id"])
                )
        
        elif method == MessageType.DISCONNECT.value:
            logger.info("[CLIENT] Peer disconnecting")
            self._connected = False
        
        else:
            logger.debug(f"[CLIENT] Unknown method: {method}")
    
    async def _send_capabilities(self):
        """Send our capabilities to the peer."""
        caps_msg = json.dumps({
            "jsonrpc": "2.0",
            "method": MessageType.CAPABILITIES.value,
            "params": {
                "features": self.agent_info.capabilities,
                "agent_name": self.name,
                "agent_type": self.agent_type,
            },
        })
        await self._websocket.send(caps_msg)


class AgentLinkCLI:
    """
    Interactive CLI client for AgentLink.
    
    Provides a simple terminal interface for connecting to a peer
    agent and exchanging messages.
    """
    
    def __init__(self, name: str = "CLI Agent"):
        self.client = AgentLinkClient(name=name, agent_type="cli")
    
    async def run(self, target: str):
        """Run the interactive CLI."""
        print(f"\nAgentLink CLI Client")
        print(f"Agent: {self.client.name} ({self.client.agent_id})")
        print(f"Connecting to: {target}\n")
        
        # Register message handler
        def on_message(params):
            content = params.get("content", "")
            sender = params.get("metadata", {}).get("sender", "peer")
            print(f"\n[Peer]: {content}")
        
        self.client.on_message(on_message)
        
        # Connect
        success = await self.client.connect(target)
        if not success:
            print("Failed to connect!")
            return
        
        peer = self.client.peer_info
        print(f"Connected to: {peer.agent_name} ({peer.agent_id})")
        print(f"Session: {self.client.session_id}")
        print(f"Type messages and press Enter to send. Ctrl+C to quit.\n")
        
        # Message input loop
        try:
            while self.client.is_connected:
                try:
                    # Non-blocking input using asyncio
                    line = await asyncio.get_event_loop().run_in_executor(
                        None, input, "> "
                    )
                    
                    if line.strip():
                        if line.strip() == "/quit":
                            break
                        if line.strip() == "/info":
                            print(f"Session: {self.client.session_id}")
                            print(f"Peer: {peer.agent_name} ({peer.agent_id})")
                            continue
                        
                        msg_id = await self.client.send(line.strip())
                        logger.debug(f"Sent message: {msg_id}")
                
                except EOFError:
                    break
                except KeyboardInterrupt:
                    break
        
        finally:
            await self.client.disconnect()
            print("\nDisconnected.")


async def run_client(target: str, name: str = "AgentLink Client"):
    """Convenience function to run an interactive client."""
    cli = AgentLinkCLI(name=name)
    await cli.run(target)


if __name__ == "__main__":
    import argparse
    
    parser = argparse.ArgumentParser(description="AgentLink Client")
    parser.add_argument("--target", required=True, help="WebSocket URL to connect to")
    parser.add_argument("--name", default="AgentLink Client", help="Agent display name")
    args = parser.parse_args()
    
    logging.basicConfig(level=logging.INFO)
    
    asyncio.run(run_client(target=args.target, name=args.name))
