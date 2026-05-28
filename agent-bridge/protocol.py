"""
Agent Bridge — Protocol layer
JSON-RPC 2.0 message types, builder helpers, and authentication utilities.
"""

from __future__ import annotations

import hashlib
import hmac
import json
import time
import uuid
from dataclasses import dataclass, field, asdict
from enum import Enum
from typing import Any, Optional


# ─── JSON-RPC 2.0 Constants ──────────────────────────────────────────────────

JSONRPC_VERSION = "2.0"

# Standard error codes
PARSE_ERROR = -32700
INVALID_REQUEST = -32600
METHOD_NOT_FOUND = -32601
INVALID_PARAMS = -32602
INTERNAL_ERROR = -32603

# Application-level error codes (use range -32000 to -32099)
AUTH_FAILED = -32000
AUTH_EXPIRED = -32001
AUTH_FORBIDDEN = -32002
RESOURCE_NOT_FOUND = -32003
CONFLICT = -32004


# ─── Error Messages ───────────────────────────────────────────────────────────

ERROR_MESSAGES = {
    PARSE_ERROR: "Parse error",
    INVALID_REQUEST: "Invalid request",
    METHOD_NOT_FOUND: "Method not found",
    INVALID_PARAMS: "Invalid params",
    INTERNAL_ERROR: "Internal error",
    AUTH_FAILED: "Authentication failed",
    AUTH_EXPIRED: "Token expired",
    AUTH_FORBIDDEN: "Agent not in whitelist",
    RESOURCE_NOT_FOUND: "Resource not found",
    CONFLICT: "Resource conflict",
}


# ─── Data classes ─────────────────────────────────────────────────────────────

class Method(str, Enum):
    """All supported JSON-RPC methods."""
    HELLO = "agent.hello"
    HEARTBEAT = "agent.heartbeat"
    INFO = "agent.info"
    MEMORY_READ = "memory.read"
    MEMORY_WRITE = "memory.write"
    MEMORY_SYNC = "memory.sync"
    TASK_PUBLISH = "task.publish"
    TASK_CLAIM = "task.claim"
    TASK_COMPLETE = "task.complete"
    TASK_LIST = "task.list"
    MESSAGE_SEND = "message.send"
    FILE_TRANSFER = "file.transfer"


@dataclass
class JsonRpcRequest:
    """Outbound JSON-RPC 2.0 request."""
    method: str
    params: dict[str, Any] = field(default_factory=dict)
    id: str = field(default_factory=lambda: uuid.uuid4().hex[:12])
    jsonrpc: str = JSONRPC_VERSION

    def to_dict(self) -> dict[str, Any]:
        d: dict[str, Any] = {
            "jsonrpc": self.jsonrpc,
            "method": self.method,
            "id": self.id,
        }
        if self.params:
            d["params"] = self.params
        return d

    def to_json(self) -> str:
        return json.dumps(self.to_dict(), ensure_ascii=False)


@dataclass
class JsonRpcResponse:
    """JSON-RPC 2.0 response (success or error)."""
    id: str
    result: Any = None
    error: Optional[dict[str, Any]] = None
    jsonrpc: str = JSONRPC_VERSION

    @property
    def is_error(self) -> bool:
        return self.error is not None

    def to_dict(self) -> dict[str, Any]:
        d: dict[str, Any] = {"jsonrpc": self.jsonrpc, "id": self.id}
        if self.error:
            d["error"] = self.error
        else:
            d["result"] = self.result
        return d

    def to_json(self) -> str:
        return json.dumps(self.to_dict(), ensure_ascii=False)

    @staticmethod
    def success(id: str, result: Any) -> "JsonRpcResponse":
        return JsonRpcResponse(id=id, result=result)

    @staticmethod
    def error(id: str, code: int, message: str = "", data: Any = None) -> "JsonRpcResponse":
        err: dict[str, Any] = {
            "code": code,
            "message": message or ERROR_MESSAGES.get(code, "Unknown error"),
        }
        if data is not None:
            err["data"] = data
        return JsonRpcResponse(id=id, error=err)


@dataclass
class JsonRpcNotification:
    """JSON-RPC 2.0 notification (no id, no response expected)."""
    method: str
    params: dict[str, Any] = field(default_factory=dict)
    jsonrpc: str = JSONRPC_VERSION

    def to_json(self) -> str:
        return json.dumps({
            "jsonrpc": self.jsonrpc,
            "method": self.method,
            "params": self.params,
        }, ensure_ascii=False)


# ─── Parsing helpers ──────────────────────────────────────────────────────────

def parse_message(raw: str) -> dict[str, Any]:
    """Parse a raw JSON string into a message dict. Raises ValueError on bad JSON."""
    try:
        msg = json.loads(raw)
    except json.JSONDecodeError as exc:
        raise ValueError(f"Invalid JSON: {exc}") from exc
    if not isinstance(msg, dict):
        raise ValueError("Message must be a JSON object")
    return msg


def is_request(msg: dict[str, Any]) -> bool:
    """True if the message is a request (has method AND id)."""
    return "method" in msg and "id" in msg


def is_notification(msg: dict[str, Any]) -> bool:
    """True if the message is a notification (has method but no id)."""
    return "method" in msg and "id" not in msg


def is_response(msg: dict[str, Any]) -> bool:
    """True if the message is a response (has result or error, plus id)."""
    return "id" in msg and ("result" in msg or "error" in msg)


# ─── Authentication helpers ───────────────────────────────────────────────────

def generate_token(agent_id: str, secret: str, timestamp: Optional[float] = None) -> str:
    """Generate HMAC-SHA256 token: HMAC(secret, agent_id + str(timestamp))."""
    ts = timestamp if timestamp is not None else time.time()
    payload = f"{agent_id}{ts}"
    return hmac.new(
        secret.encode("utf-8"),
        payload.encode("utf-8"),
        hashlib.sha256,
    ).hexdigest()


def verify_token(
    agent_id: str,
    token: str,
    timestamp: float,
    secret: str,
    ttl: int = 300,
) -> bool:
    """Verify a token is valid and not expired. Returns True on success."""
    # Check freshness
    if abs(time.time() - timestamp) > ttl:
        return False
    # Recompute and compare
    expected = generate_token(agent_id, secret, timestamp)
    return hmac.compare_digest(token, expected)


# ─── Discovery messages ───────────────────────────────────────────────────────

def discovery_beacon(agent_id: str, port: int, capabilities: list[str]) -> bytes:
    """Build a UDP discovery beacon payload."""
    return json.dumps({
        "type": "agent_beacon",
        "agent_id": agent_id,
        "port": port,
        "capabilities": capabilities,
        "timestamp": time.time(),
    }).encode("utf-8")


def parse_discovery_beacon(data: bytes) -> Optional[dict[str, Any]]:
    """Try to parse a UDP datagram as a discovery beacon. Returns None on failure."""
    try:
        obj = json.loads(data.decode("utf-8"))
        if isinstance(obj, dict) and obj.get("type") == "agent_beacon":
            return obj
    except Exception:
        pass
    return None
