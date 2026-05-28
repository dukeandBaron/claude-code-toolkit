"""
Agent Bridge — Server
WebSocket server with HTTP handshake, LAN discovery, API-key auth,
shared memory sync, and graceful shutdown.

Usage:
    python bridge_server.py [--agent-id ID] [--port PORT] [--secret SECRET]
"""

from __future__ import annotations

import argparse
import asyncio
import json
import logging
import os
import pathlib
import signal
import socket
import sys
import time
from typing import Any, Optional

import websockets
from websockets.server import serve, WebSocketServerProtocol

# Ensure the bridge package is on sys.path
sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))

import config
from protocol import (
    AUTH_EXPIRED,
    AUTH_FAILED,
    AUTH_FORBIDDEN,
    CONFLICT,
    INTERNAL_ERROR,
    INVALID_PARAMS,
    INVALID_REQUEST,
    METHOD_NOT_FOUND,
    RESOURCE_NOT_FOUND,
    JsonRpcNotification,
    JsonRpcRequest,
    JsonRpcResponse,
    Method,
    generate_token,
    is_notification,
    is_request,
    is_response,
    parse_discovery_beacon,
    parse_message,
    verify_token,
)

logger = logging.getLogger("bridge.server")


# ─── Connected Peer ──────────────────────────────────────────────────────────

class Peer:
    """Represents a connected remote agent."""

    def __init__(self, ws: WebSocketServerProtocol, agent_id: str, address: str):
        self.ws = ws
        self.agent_id = agent_id
        self.address = address
        self.connected_at = time.time()
        self.last_heartbeat = time.time()

    def __repr__(self) -> str:
        return f"Peer({self.agent_id!r}, {self.address})"


# ─── Shared Memory Manager ───────────────────────────────────────────────────

class SharedMemory:
    """Read/write shared markdown files (MEMORY.md, TASK_QUEUE.md)."""

    def __init__(self, base_dir: pathlib.Path):
        self.base_dir = base_dir
        self.base_dir.mkdir(parents=True, exist_ok=True)
        # Seed files if missing
        for name, template in [
            (config.MEMORY_FILE.name, "# Shared Memory\n\n"),
            (config.TASK_QUEUE_FILE.name, "# Task Queue\n\n"),
        ]:
            path = self.base_dir / name
            if not path.exists():
                path.write_text(template, encoding="utf-8")
                logger.info("Created %s", path)

    def read(self, filename: str) -> str:
        path = self.base_dir / filename
        if not path.exists():
            raise FileNotFoundError(f"File not found: {filename}")
        # Security: prevent path traversal
        if not path.resolve().is_relative_to(self.base_dir.resolve()):
            raise PermissionError("Path traversal blocked")
        return path.read_text(encoding="utf-8")

    def write(self, filename: str, content: str, append: bool = False) -> None:
        path = self.base_dir / filename
        if not path.resolve().is_relative_to(self.base_dir.resolve()):
            raise PermissionError("Path traversal blocked")
        if append:
            with open(path, "a", encoding="utf-8") as f:
                f.write(content)
        else:
            path.write_text(content, encoding="utf-8")
        logger.info("Wrote %d bytes to %s (append=%s)", len(content), filename, append)

    def list_files(self) -> list[str]:
        return [f.name for f in self.base_dir.iterdir() if f.is_file()]


# ─── Discovery Broadcaster ───────────────────────────────────────────────────

class DiscoveryService:
    """UDP broadcast for LAN agent discovery."""

    def __init__(self, agent_id: str, port: int):
        self.agent_id = agent_id
        self.port = port
        self._running = False
        self._task: Optional[asyncio.Task] = None

    async def start(self) -> None:
        self._running = True
        self._task = asyncio.create_task(self._broadcast_loop())
        logger.info("LAN discovery broadcasting on port %d", config.DISCOVERY_PORT)

    async def stop(self) -> None:
        self._running = False
        if self._task:
            self._task.cancel()
            try:
                await self._task
            except asyncio.CancelledError:
                pass

    async def _broadcast_loop(self) -> None:
        sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        sock.setsockopt(socket.SOL_SOCKET, socket.SO_BROADCAST, 1)
        sock.setblocking(False)
        loop = asyncio.get_event_loop()
        try:
            while self._running:
                beacon = json.dumps({
                    "type": "agent_beacon",
                    "agent_id": self.agent_id,
                    "port": self.port,
                    "timestamp": time.time(),
                }).encode()
                try:
                    await loop.sock_sendto(
                        sock, beacon, (config.DISCOVERY_BROADCAST, config.DISCOVERY_PORT)
                    )
                except OSError as e:
                    logger.debug("Broadcast send error (normal on some networks): %s", e)
                await asyncio.sleep(config.DISCOVERY_INTERVAL)
        finally:
            sock.close()


# ─── Bridge Server ────────────────────────────────────────────────────────────

class BridgeServer:
    """Main bridge server: manages peers, dispatches JSON-RPC methods."""

    def __init__(self, agent_id: str, port: int, secret: str):
        self.agent_id = agent_id
        self.port = port
        self.secret = secret
        self.peers: dict[str, Peer] = {}  # agent_id -> Peer
        self.memory = SharedMemory(config.SHARED_MEMORY_DIR)
        self.discovery = DiscoveryService(agent_id, port)
        self._server = None
        self._shutdown = asyncio.Event()

    async def start(self) -> None:
        logger.info("Starting bridge server: agent=%s port=%d", self.agent_id, self.port)

        # Start LAN discovery
        await self.discovery.start()

        # Start WebSocket server
        self._server = await serve(
            self._handle_connection,
            config.SERVER_HOST,
            self.port,
            max_size=config.MAX_MESSAGE_SIZE,
            ping_interval=config.HEARTBEAT_INTERVAL,
            ping_timeout=config.HEARTBEAT_TIMEOUT,
        )
        logger.info("Bridge server listening on ws://%s:%d", config.SERVER_HOST, self.port)
        logger.info("Shared memory directory: %s", config.SHARED_MEMORY_DIR)

        # Wait for shutdown signal
        await self._shutdown.wait()

    async def stop(self) -> None:
        logger.info("Shutting down bridge server...")
        self._shutdown.set()
        await self.discovery.stop()
        if self._server:
            self._server.close()
            await self._server.wait_closed()
        # Close all peer connections
        for peer in list(self.peers.values()):
            await peer.ws.close(1001, "Server shutting down")
        logger.info("Bridge server stopped.")

    async def _handle_connection(self, ws: WebSocketServerProtocol) -> None:
        """Handle a single incoming WebSocket connection."""
        peer_addr = ws.remote_address
        logger.info("Incoming connection from %s", peer_addr)
        agent_id: Optional[str] = None
        try:
            # ── Authentication phase ──
            agent_id = await self._authenticate(ws)
            if not agent_id:
                return

            peer = Peer(ws, agent_id, str(peer_addr))
            self.peers[agent_id] = peer
            logger.info("Agent '%s' connected from %s", agent_id, peer_addr)

            # ── Message loop ──
            async for raw in ws:
                try:
                    text = raw if isinstance(raw, str) else raw.decode("utf-8")
                    await self._dispatch(peer, text)
                except Exception:
                    logger.exception("Error handling message from %s", agent_id)

        except websockets.ConnectionClosed:
            logger.info("Connection closed: %s", agent_id or peer_addr)
        except Exception:
            logger.exception("Unexpected error for %s", agent_id or peer_addr)
        finally:
            if agent_id and agent_id in self.peers:
                del self.peers[agent_id]
                logger.info("Agent '%s' disconnected", agent_id)

    async def _authenticate(self, ws: WebSocketServerProtocol) -> Optional[str]:
        """Wait for the first message (agent.hello) and verify credentials."""
        try:
            raw = await asyncio.wait_for(ws.recv(), timeout=10.0)
            msg = parse_message(raw if isinstance(raw, str) else raw.decode())
        except (asyncio.TimeoutError, Exception) as e:
            logger.warning("Authentication failed: no hello received (%s)", e)
            await ws.close(4001, "Authentication timeout")
            return None

        if msg.get("method") != Method.HELLO:
            logger.warning("Authentication failed: first message was not agent.hello")
            await ws.close(4001, "Expected agent.hello")
            return None

        params = msg.get("params", {})
        agent_id = params.get("agent_id", "")
        token = params.get("token", "")
        timestamp = params.get("timestamp", 0)

        # Verify token
        if not verify_token(agent_id, token, timestamp, self.secret, config.TOKEN_TTL):
            logger.warning("Auth failed: bad token for agent '%s'", agent_id)
            resp = JsonRpcResponse.error(msg["id"], AUTH_FAILED)
            await ws.send(resp.to_json())
            await ws.close(4003, "Invalid token")
            return None

        # Whitelist check
        if config.ALLOWED_AGENTS and agent_id not in config.ALLOWED_AGENTS:
            logger.warning("Auth failed: agent '%s' not in whitelist", agent_id)
            resp = JsonRpcResponse.error(msg["id"], AUTH_FORBIDDEN)
            await ws.send(resp.to_json())
            await ws.close(4003, "Agent not allowed")
            return None

        # Check for duplicate
        if agent_id in self.peers:
            logger.warning("Agent '%s' already connected, replacing", agent_id)
            old = self.peers.pop(agent_id)
            await old.ws.close(4009, "Replaced by new connection")

        # Send hello response
        resp = JsonRpcResponse.success(msg["id"], {
            "agent_id": self.agent_id,
            "capabilities": config.CAPABILITIES,
            "version": "1.0.0",
            "session_id": os.urandom(8).hex(),
        })
        await ws.send(resp.to_json())
        return agent_id

    async def _dispatch(self, peer: Peer, raw: str) -> None:
        """Parse and dispatch a JSON-RPC message to the right handler."""
        try:
            msg = parse_message(raw)
        except ValueError as e:
            resp = JsonRpcResponse.error("0", INVALID_REQUEST, str(e))
            await peer.ws.send(resp.to_json())
            return

        if is_response(msg):
            # Unsolicited response from peer — ignore
            return

        if is_notification(msg):
            method = msg["method"]
            params = msg.get("params", {})
            await self._handle_notification(peer, method, params)
            return

        if is_request(msg):
            method = msg["method"]
            params = msg.get("params", {})
            msg_id = msg["id"]
            resp = await self._handle_request(peer, msg_id, method, params)
            await peer.ws.send(resp.to_json())
            return

        resp = JsonRpcResponse.error("0", INVALID_REQUEST, "Unrecognized message format")
        await peer.ws.send(resp.to_json())

    async def _handle_notification(
        self, peer: Peer, method: str, params: dict[str, Any]
    ) -> None:
        """Handle a notification (fire-and-forget, no response)."""
        if method == Method.HEARTBEAT:
            peer.last_heartbeat = time.time()
            logger.debug("Heartbeat from %s", peer.agent_id)
        else:
            logger.debug("Notification from %s: %s", peer.agent_id, method)

    async def _handle_request(
        self, peer: Peer, msg_id: str, method: str, params: dict[str, Any]
    ) -> JsonRpcResponse:
        """Route a JSON-RPC request to the appropriate handler."""
        handlers = {
            Method.HEARTBEAT: self._cmd_heartbeat,
            Method.INFO: self._cmd_info,
            Method.MEMORY_READ: self._cmd_memory_read,
            Method.MEMORY_WRITE: self._cmd_memory_write,
            Method.MEMORY_SYNC: self._cmd_memory_sync,
            Method.TASK_PUBLISH: self._cmd_task_publish,
            Method.TASK_CLAIM: self._cmd_task_claim,
            Method.TASK_COMPLETE: self._cmd_task_complete,
            Method.TASK_LIST: self._cmd_task_list,
            Method.MESSAGE_SEND: self._cmd_message_send,
        }
        handler = handlers.get(method)
        if not handler:
            return JsonRpcResponse.error(msg_id, METHOD_NOT_FOUND, f"Unknown method: {method}")
        try:
            return await handler(peer, msg_id, params)
        except Exception as e:
            logger.exception("Handler error for %s.%s", peer.agent_id, method)
            return JsonRpcResponse.error(msg_id, INTERNAL_ERROR, str(e))

    # ── Method handlers ───────────────────────────────────────────────────────

    async def _cmd_heartbeat(
        self, peer: Peer, msg_id: str, params: dict[str, Any]
    ) -> JsonRpcResponse:
        peer.last_heartbeat = time.time()
        return JsonRpcResponse.success(msg_id, {
            "status": "alive",
            "agent_id": self.agent_id,
            "uptime": time.time() - peer.connected_at,
            "peer_count": len(self.peers),
        })

    async def _cmd_info(
        self, peer: Peer, msg_id: str, params: dict[str, Any]
    ) -> JsonRpcResponse:
        return JsonRpcResponse.success(msg_id, {
            "agent_id": self.agent_id,
            "capabilities": config.CAPABILITIES,
            "version": "1.0.0",
            "peers": list(self.peers.keys()),
            "files": self.memory.list_files(),
        })

    async def _cmd_memory_read(
        self, peer: Peer, msg_id: str, params: dict[str, Any]
    ) -> JsonRpcResponse:
        filename = params.get("file", "MEMORY.md")
        try:
            content = self.memory.read(filename)
        except FileNotFoundError:
            return JsonRpcResponse.error(msg_id, RESOURCE_NOT_FOUND, f"File not found: {filename}")
        except PermissionError:
            return JsonRpcResponse.error(msg_id, AUTH_FORBIDDEN, "Path traversal blocked")
        return JsonRpcResponse.success(msg_id, {"file": filename, "content": content})

    async def _cmd_memory_write(
        self, peer: Peer, msg_id: str, params: dict[str, Any]
    ) -> JsonRpcResponse:
        filename = params.get("file", "MEMORY.md")
        content = params.get("content", "")
        append = params.get("append", False)
        try:
            self.memory.write(filename, content, append)
        except PermissionError:
            return JsonRpcResponse.error(msg_id, AUTH_FORBIDDEN, "Path traversal blocked")
        # Broadcast change to other peers
        await self._broadcast_notification(Method.MEMORY_SYNC, {
            "file": filename,
            "changed_by": peer.agent_id,
        }, exclude=peer.agent_id)
        return JsonRpcResponse.success(msg_id, {"ok": True, "file": filename})

    async def _cmd_memory_sync(
        self, peer: Peer, msg_id: str, params: dict[str, Any]
    ) -> JsonRpcResponse:
        filename = params.get("file", "MEMORY.md")
        direction = params.get("direction", "pull")
        try:
            if direction == "pull":
                content = self.memory.read(filename)
                return JsonRpcResponse.success(msg_id, {
                    "file": filename, "content": content, "direction": "pull"
                })
            else:
                content = params.get("content", "")
                self.memory.write(filename, content)
                return JsonRpcResponse.success(msg_id, {
                    "file": filename, "bytes_written": len(content), "direction": "push"
                })
        except FileNotFoundError:
            return JsonRpcResponse.error(msg_id, RESOURCE_NOT_FOUND)
        except PermissionError:
            return JsonRpcResponse.error(msg_id, AUTH_FORBIDDEN, "Path traversal blocked")

    async def _cmd_task_publish(
        self, peer: Peer, msg_id: str, params: dict[str, Any]
    ) -> JsonRpcResponse:
        task_id = params.get("task_id", os.urandom(6).hex())
        title = params.get("title", "Untitled")
        priority = params.get("priority", "normal")
        description = params.get("description", "")
        entry = (
            f"\n## Task: {title}\n"
            f"- **ID**: {task_id}\n"
            f"- **Priority**: {priority}\n"
            f"- **Status**: open\n"
            f"- **Published by**: {peer.agent_id}\n"
            f"- **Description**: {description}\n\n"
        )
        try:
            self.memory.write("TASK_QUEUE.md", entry, append=True)
        except Exception as e:
            return JsonRpcResponse.error(msg_id, INTERNAL_ERROR, str(e))
        await self._broadcast_notification("task.new", {
            "task_id": task_id, "title": title, "priority": priority
        }, exclude=peer.agent_id)
        return JsonRpcResponse.success(msg_id, {"task_id": task_id, "status": "published"})

    async def _cmd_task_claim(
        self, peer: Peer, msg_id: str, params: dict[str, Any]
    ) -> JsonRpcResponse:
        task_id = params.get("task_id", "")
        entry = (
            f"\n### Claim: {task_id}\n"
            f"- **Claimed by**: {peer.agent_id}\n"
            f"- **At**: {time.strftime('%Y-%m-%d %H:%M:%S')}\n\n"
        )
        try:
            self.memory.write("TASK_QUEUE.md", entry, append=True)
        except Exception as e:
            return JsonRpcResponse.error(msg_id, INTERNAL_ERROR, str(e))
        return JsonRpcResponse.success(msg_id, {"task_id": task_id, "claimed_by": peer.agent_id})

    async def _cmd_task_complete(
        self, peer: Peer, msg_id: str, params: dict[str, Any]
    ) -> JsonRpcResponse:
        task_id = params.get("task_id", "")
        result = params.get("result", "")
        entry = (
            f"\n### Complete: {task_id}\n"
            f"- **Completed by**: {peer.agent_id}\n"
            f"- **Result**: {result}\n\n"
        )
        try:
            self.memory.write("TASK_QUEUE.md", entry, append=True)
        except Exception as e:
            return JsonRpcResponse.error(msg_id, INTERNAL_ERROR, str(e))
        return JsonRpcResponse.success(msg_id, {"task_id": task_id, "status": "completed"})

    async def _cmd_task_list(
        self, peer: Peer, msg_id: str, params: dict[str, Any]
    ) -> JsonRpcResponse:
        try:
            content = self.memory.read("TASK_QUEUE.md")
        except FileNotFoundError:
            content = ""
        return JsonRpcResponse.success(msg_id, {"content": content})

    async def _cmd_message_send(
        self, peer: Peer, msg_id: str, params: dict[str, Any]
    ) -> JsonRpcResponse:
        target = params.get("target", "")
        text = params.get("text", "")
        if target and target in self.peers:
            notification = JsonRpcNotification(
                method="message.receive",
                params={"from": peer.agent_id, "text": text},
            )
            await self.peers[target].ws.send(notification.to_json())
            return JsonRpcResponse.success(msg_id, {"delivered": True, "to": target})
        elif target:
            return JsonRpcResponse.error(msg_id, RESOURCE_NOT_FOUND, f"Peer not found: {target}")
        else:
            # Broadcast
            await self._broadcast_notification("message.receive", {
                "from": peer.agent_id, "text": text
            }, exclude=peer.agent_id)
            return JsonRpcResponse.success(msg_id, {"delivered": True, "to": "broadcast"})

    async def _broadcast_notification(
        self, method: str, params: dict[str, Any], exclude: str = ""
    ) -> None:
        notification = JsonRpcNotification(method=method, params=params)
        payload = notification.to_json()
        for pid, peer in self.peers.items():
            if pid != exclude:
                try:
                    await peer.ws.send(payload)
                except websockets.ConnectionClosed:
                    pass


# ─── HTTP Health Endpoint ─────────────────────────────────────────────────────

async def health_check_handler(path: str, headers: dict) -> Optional[tuple]:
    """Minimal HTTP health check on the WebSocket port."""
    if path == "/health":
        body = json.dumps({
            "status": "ok",
            "agent_id": _server_instance.agent_id if _server_instance else "unknown",
            "peers": len(_server_instance.peers) if _server_instance else 0,
            "uptime": time.time(),
        }).encode()
        return (200, [("Content-Type", "application/json")], body)
    return None


# Module-level ref for health handler
_server_instance: Optional[BridgeServer] = None


# ─── Main ─────────────────────────────────────────────────────────────────────

def setup_logging() -> None:
    logging.basicConfig(
        level=getattr(logging, config.LOG_LEVEL, logging.INFO),
        format=config.LOG_FORMAT,
        datefmt=config.LOG_DATE_FORMAT,
    )


async def run_server(agent_id: str, port: int, secret: str) -> None:
    global _server_instance
    server = BridgeServer(agent_id, port, secret)
    _server_instance = server

    loop = asyncio.get_running_loop()

    def _signal_handler() -> None:
        logger.info("Shutdown signal received")
        asyncio.ensure_future(server.stop())

    if sys.platform != "win32":
        for sig in (signal.SIGINT, signal.SIGTERM):
            loop.add_signal_handler(sig, _signal_handler)

    try:
        await server.start()
    except KeyboardInterrupt:
        pass
    finally:
        await server.stop()


def main() -> None:
    parser = argparse.ArgumentParser(description="Agent Bridge Server")
    parser.add_argument("--agent-id", default=f"hermes-{socket.gethostname()}")
    parser.add_argument("--port", type=int, default=config.SERVER_PORT)
    parser.add_argument("--secret", default=config.get_secret())
    args = parser.parse_args()

    setup_logging()
    logger.info("Agent ID : %s", args.agent_id)
    logger.info("Port     : %d", args.port)
    logger.info("Secret   : %s...%s", args.secret[:4], args.secret[-4:] if len(args.secret) > 8 else "****")

    try:
        asyncio.run(run_server(args.agent_id, args.port, args.secret))
    except KeyboardInterrupt:
        logger.info("Interrupted, exiting.")


if __name__ == "__main__":
    main()
