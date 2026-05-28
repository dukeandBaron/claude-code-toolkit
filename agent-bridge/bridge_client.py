"""
Agent Bridge — Client
Connects to another bridge server, authenticates, and provides a clean API
for sending JSON-RPC messages.

Usage:
    python bridge_client.py --peer HOST:PORT [--agent-id ID] [--secret SECRET]
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
from typing import Any, Callable, Coroutine, Optional

import websockets

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))

import config
from protocol import (
    INTERNAL_ERROR,
    METHOD_NOT_FOUND,
    JsonRpcNotification,
    JsonRpcRequest,
    JsonRpcResponse,
    Method,
    generate_token,
    parse_message,
    is_notification,
    is_request,
    is_response,
    parse_discovery_beacon,
)

logger = logging.getLogger("bridge.client")

# Type alias for response callbacks
ResponseCallback = Callable[[dict[str, Any]], Coroutine[Any, Any, None]]


class BridgeClient:
    """WebSocket client that connects to a bridge server."""

    def __init__(
        self,
        agent_id: str,
        peer_host: str,
        peer_port: int,
        secret: str,
    ):
        self.agent_id = agent_id
        self.peer_host = peer_host
        self.peer_port = peer_port
        self.secret = secret
        self._ws: Optional[websockets.WebSocketClientProtocol] = None
        self._pending: dict[str, asyncio.Future] = {}  # msg_id -> Future
        self._notification_handlers: dict[str, Callable] = {}
        self._running = False
        self._send_lock = asyncio.Lock()
        self._connected = asyncio.Event()

    # ── Connection lifecycle ──────────────────────────────────────────────────

    async def connect(self) -> None:
        """Connect and authenticate with the bridge server. Retries on failure."""
        self._running = True
        while self._running:
            try:
                await self._connect_once()
            except (OSError, websockets.InvalidHandshake) as e:
                logger.warning("Connection failed: %s", e)
            except websockets.ConnectionClosed as e:
                logger.warning("Connection closed: %s (code=%s)", e.reason, e.code)
            except Exception:
                logger.exception("Unexpected connection error")

            if self._running:
                logger.info("Reconnecting in %d seconds...", config.CLIENT_RECONNECT_DELAY)
                await asyncio.sleep(config.CLIENT_RECONNECT_DELAY)

    async def _connect_once(self) -> None:
        """Single connection attempt: TCP connect, authenticate, enter message loop."""
        uri = f"ws://{self.peer_host}:{self.peer_port}"
        logger.info("Connecting to %s ...", uri)

        async with websockets.connect(
            uri,
            max_size=config.MAX_MESSAGE_SIZE,
            ping_interval=config.HEARTBEAT_INTERVAL,
            ping_timeout=config.HEARTBEAT_TIMEOUT,
            open_timeout=10,
            close_timeout=5,
        ) as ws:
            self._ws = ws
            logger.info("WebSocket connected, authenticating...")

            # ── Authenticate ──
            if not await self._authenticate(ws):
                return

            self._connected.set()
            logger.info("Authenticated successfully with server.")

            # ── Message loop ──
            try:
                async for raw in ws:
                    text = raw if isinstance(raw, str) else raw.decode("utf-8")
                    await self._handle_message(text)
            finally:
                self._connected.clear()
                self._ws = None
                # Cancel pending requests
                for fut in self._pending.values():
                    if not fut.done():
                        fut.set_exception(ConnectionError("Connection lost"))
                self._pending.clear()

    async def _authenticate(self, ws: websockets.WebSocketClientProtocol) -> bool:
        """Send agent.hello and wait for server response."""
        timestamp = time.time()
        token = generate_token(self.agent_id, self.secret, timestamp)
        hello = JsonRpcRequest(
            method=Method.HELLO,
            params={
                "agent_id": self.agent_id,
                "token": token,
                "timestamp": timestamp,
                "version": "1.0.0",
            },
        )
        await ws.send(hello.to_json())
        logger.debug("Sent agent.hello, waiting for response...")

        try:
            raw = await asyncio.wait_for(ws.recv(), timeout=10.0)
            msg = parse_message(raw if isinstance(raw, str) else raw.decode())
        except asyncio.TimeoutError:
            logger.error("Authentication timeout")
            await ws.close(4001, "Auth timeout")
            return False
        except Exception as e:
            logger.error("Authentication error: %s", e)
            return False

        if "error" in msg:
            err = msg["error"]
            logger.error("Authentication rejected: %s", err)
            return False

        result = msg.get("result", {})
        logger.info(
            "Server agent=%s, session=%s, capabilities=%s",
            result.get("agent_id"),
            result.get("session_id"),
            result.get("capabilities"),
        )
        return True

    async def disconnect(self) -> None:
        """Gracefully disconnect."""
        self._running = False
        if self._ws:
            await self._ws.close(1000, "Client disconnecting")
        self._connected.clear()

    @property
    def is_connected(self) -> bool:
        return self._connected.is_set()

    # ── Message sending ───────────────────────────────────────────────────────

    async def call(
        self, method: str, params: Optional[dict[str, Any]] = None, timeout: float = 30.0
    ) -> dict[str, Any]:
        """Send a JSON-RPC request and wait for the response. Returns result dict."""
        if not self._ws:
            raise ConnectionError("Not connected")

        req = JsonRpcRequest(method=method, params=params or {})
        future: asyncio.Future = asyncio.get_running_loop().create_future()
        self._pending[req.id] = future

        async with self._send_lock:
            await self._ws.send(req.to_json())

        try:
            resp = await asyncio.wait_for(future, timeout=timeout)
        except asyncio.TimeoutError:
            self._pending.pop(req.id, None)
            raise TimeoutError(f"No response for {method} within {timeout}s")

        if "error" in resp:
            err = resp["error"]
            raise RuntimeError(f"RPC error {err.get('code')}: {err.get('message')}")

        return resp.get("result", {})

    async def notify(self, method: str, params: Optional[dict[str, Any]] = None) -> None:
        """Send a JSON-RPC notification (no response expected)."""
        if not self._ws:
            raise ConnectionError("Not connected")
        notification = JsonRpcNotification(method=method, params=params or {})
        async with self._send_lock:
            await self._ws.send(notification.to_json())

    # ── Message receiving ─────────────────────────────────────────────────────

    async def _handle_message(self, raw: str) -> None:
        """Dispatch incoming messages: responses to pending calls, notifications, or requests."""
        try:
            msg = parse_message(raw)
        except ValueError:
            logger.warning("Received unparseable message")
            return

        # Response to a pending call
        if is_response(msg):
            msg_id = msg.get("id", "")
            future = self._pending.pop(msg_id, None)
            if future and not future.done():
                future.set_result(msg)
            return

        # Notification from server
        if is_notification(msg):
            method = msg["method"]
            params = msg.get("params", {})
            handler = self._notification_handlers.get(method)
            if handler:
                try:
                    await handler(params)
                except Exception:
                    logger.exception("Notification handler error for %s", method)
            else:
                logger.info("Unhandled notification: %s %s", method, params)
            return

        # Request from server (rare, but protocol supports it)
        if is_request(msg):
            logger.info("Incoming request from server: %s (not yet handled)", msg["method"])

    def on_notification(self, method: str, handler: Callable) -> None:
        """Register a handler for a specific notification method."""
        self._notification_handlers[method] = handler

    # ── Discovery ─────────────────────────────────────────────────────────────

    @staticmethod
    async def discover_peers(timeout: float = 5.0) -> list[dict[str, Any]]:
        """Listen for UDP discovery beacons on the LAN. Returns list of discovered agents."""
        peers: list[dict[str, Any]] = []
        sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        sock.setblocking(False)
        try:
            sock.bind(("", config.DISCOVERY_PORT))
        except OSError:
            logger.warning("Could not bind discovery port %d", config.DISCOVERY_PORT)
            return peers

        loop = asyncio.get_running_loop()
        deadline = time.time() + timeout
        try:
            while time.time() < deadline:
                remaining = deadline - time.time()
                if remaining <= 0:
                    break
                try:
                    data, addr = await asyncio.wait_for(
                        loop.sock_recvfrom(sock, 4096), timeout=remaining
                    )
                    beacon = parse_discovery_beacon(data)
                    if beacon:
                        beacon["address"] = addr[0]
                        # Deduplicate
                        if not any(p["agent_id"] == beacon["agent_id"] for p in peers):
                            peers.append(beacon)
                            logger.info(
                                "Discovered agent '%s' at %s:%d",
                                beacon["agent_id"],
                                addr[0],
                                beacon.get("port"),
                            )
                except asyncio.TimeoutError:
                    break
        finally:
            sock.close()
        return peers

    # ── Convenience methods ───────────────────────────────────────────────────

    async def memory_read(self, filename: str = "MEMORY.md") -> str:
        """Read a shared memory file from the server."""
        result = await self.call(Method.MEMORY_READ, {"file": filename})
        return result.get("content", "")

    async def memory_write(self, filename: str, content: str, append: bool = False) -> bool:
        """Write content to a shared memory file on the server."""
        result = await self.call(Method.MEMORY_WRITE, {
            "file": filename, "content": content, "append": append
        })
        return result.get("ok", False)

    async def memory_sync(self, filename: str, direction: str = "pull") -> str:
        """Sync a memory file. direction='pull' downloads, 'push' uploads."""
        params: dict[str, Any] = {"file": filename, "direction": direction}
        if direction == "push":
            path = config.SHARED_MEMORY_DIR / filename
            if path.exists():
                params["content"] = path.read_text(encoding="utf-8")
            else:
                raise FileNotFoundError(f"Local file not found: {path}")
        result = await self.call(Method.MEMORY_SYNC, params)
        return result.get("content", "")

    async def send_message(self, text: str, target: str = "") -> bool:
        """Send a message to a specific agent or broadcast."""
        result = await self.call(Method.MESSAGE_SEND, {"text": text, "target": target})
        return result.get("delivered", False)

    async def publish_task(self, title: str, description: str = "", priority: str = "normal") -> str:
        """Publish a task to the shared task queue."""
        result = await self.call(Method.TASK_PUBLISH, {
            "title": title, "description": description, "priority": priority
        })
        return result.get("task_id", "")

    async def get_server_info(self) -> dict[str, Any]:
        """Get server info (capabilities, peers, files)."""
        return await self.call(Method.INFO)


# ─── Interactive REPL ─────────────────────────────────────────────────────────

async def interactive_loop(client: BridgeClient) -> None:
    """Simple REPL for interacting with the bridge."""
    print()
    print("=" * 60)
    print("  Agent Bridge Client — Interactive Mode")
    print("=" * 60)
    print("  Commands:")
    print("    info              Show server info")
    print("    read [file]       Read shared memory file")
    print("    write <file> ...  Write to shared memory file")
    print("    msg <text>        Broadcast a message")
    print("    task <title>      Publish a task")
    print("    list              List tasks")
    print("    discover          Discover LAN peers")
    print("    quit              Exit")
    print("=" * 60)

    await client._connected.wait()

    loop = asyncio.get_event_loop()
    while client.is_connected:
        try:
            line = await loop.run_in_executor(None, lambda: input("\nbridge> "))
        except (EOFError, KeyboardInterrupt):
            break

        line = line.strip()
        if not line:
            continue

        parts = line.split(None, 1)
        cmd = parts[0].lower()
        arg = parts[1] if len(parts) > 1 else ""

        try:
            if cmd in ("quit", "exit", "q"):
                break
            elif cmd == "info":
                info = await client.get_server_info()
                print(json.dumps(info, indent=2, ensure_ascii=False))
            elif cmd == "read":
                content = await client.memory_read(arg or "MEMORY.md")
                print(content)
            elif cmd == "write":
                if not arg:
                    print("Usage: write <filename> <content>")
                    continue
                fname, _, content = arg.partition(" ")
                ok = await client.memory_write(fname, content)
                print("OK" if ok else "FAILED")
            elif cmd == "msg":
                ok = await client.send_message(arg)
                print("Delivered" if ok else "Not delivered")
            elif cmd == "task":
                tid = await client.publish_task(arg)
                print(f"Published task: {tid}")
            elif cmd == "list":
                content = await client.call(Method.TASK_LIST)
                print(json.dumps(content, indent=2, ensure_ascii=False))
            elif cmd == "discover":
                peers = await BridgeClient.discover_peers(timeout=3)
                for p in peers:
                    print(f"  {p['agent_id']} at {p['address']}:{p['port']}")
            else:
                print(f"Unknown command: {cmd}")
        except Exception as e:
            print(f"Error: {e}")

    await client.disconnect()


# ─── Main ─────────────────────────────────────────────────────────────────────

def setup_logging() -> None:
    logging.basicConfig(
        level=getattr(logging, config.LOG_LEVEL, logging.INFO),
        format=config.LOG_FORMAT,
        datefmt=config.LOG_DATE_FORMAT,
    )


async def run_client(
    agent_id: str, peer_host: str, peer_port: int, secret: str, interactive: bool = True
) -> None:
    client = BridgeClient(agent_id, peer_host, peer_port, secret)

    # Register notification handlers
    async def on_memory_sync(params: dict) -> None:
        logger.info("Memory sync notification: %s changed by %s",
                     params.get("file"), params.get("changed_by"))

    async def on_message_receive(params: dict) -> None:
        print(f"\n  [MESSAGE from {params.get('from', '?')}]: {params.get('text', '')}")

    async def on_task_new(params: dict) -> None:
        print(f"\n  [NEW TASK] {params.get('title')} (id={params.get('task_id')})")

    client.on_notification("memory.sync", on_memory_sync)
    client.on_notification("message.receive", on_message_receive)
    client.on_notification("task.new", on_task_new)

    if interactive:
        connect_task = asyncio.create_task(client.connect())
        await asyncio.sleep(1)  # Give connection time to establish
        try:
            await interactive_loop(client)
        finally:
            await client.disconnect()
            connect_task.cancel()
            try:
                await connect_task
            except asyncio.CancelledError:
                pass
    else:
        await client.connect()


def main() -> None:
    parser = argparse.ArgumentParser(description="Agent Bridge Client")
    parser.add_argument("--peer", required=True, help="Server address as HOST:PORT")
    parser.add_argument("--agent-id", default=f"hermes-{socket.gethostname()}")
    parser.add_argument("--secret", default=config.get_secret())
    parser.add_argument("--no-interactive", action="store_true", help="Run in non-interactive mode")
    args = parser.parse_args()

    # Parse peer address
    if ":" in args.peer:
        host, port_str = args.peer.rsplit(":", 1)
        port = int(port_str)
    else:
        host = args.peer
        port = config.SERVER_PORT

    setup_logging()
    logger.info("Agent ID : %s", args.agent_id)
    logger.info("Peer     : %s:%d", host, port)

    try:
        asyncio.run(run_client(
            agent_id=args.agent_id,
            peer_host=host,
            peer_port=port,
            secret=args.secret,
            interactive=not args.no_interactive,
        ))
    except KeyboardInterrupt:
        logger.info("Interrupted, exiting.")


if __name__ == "__main__":
    main()
