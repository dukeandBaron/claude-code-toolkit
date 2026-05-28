"""
AgentLink Protocol - Message Types and JSON-RPC Encoding

Based on JSON-RPC 2.0 spec, inspired by MCP and Google A2A protocol.
"""

import json
import uuid
import time
from enum import Enum
from typing import Any, Optional
from pydantic import BaseModel, Field


class MessageType(str, Enum):
    HANDSHAKE = "agentlink.handshake"
    SEND = "agentlink.send"
    CAPABILITIES = "agentlink.capabilities"
    HEARTBEAT = "agentlink.heartbeat"
    DISCONNECT = "agentlink.disconnect"
    FILE_OFFER = "agentlink.file.offer"
    FILE_ACCEPT = "agentlink.file.accept"
    FILE_CHUNK = "agentlink.file.chunk"
    TASK_CREATE = "agentlink.task.create"
    TASK_UPDATE = "agentlink.task.update"
    ERROR = "agentlink.error"


class HandshakePhase(str, Enum):
    HELLO = "hello"
    WELCOME = "welcome"
    READY = "ready"


class AgentInfo(BaseModel):
    """Information about an agent, exchanged during handshake."""
    agent_id: str
    agent_name: str
    agent_type: str  # "hermes-agent", "claude-code", "custom"
    agent_version: str = "1.0.0"
    public_key: Optional[str] = None  # Base64-encoded Ed25519 public key
    capabilities: list[str] = Field(default_factory=lambda: ["messaging"])
    protocol_version: str = "1.0"
    nonce: Optional[str] = None


class HandshakeParams(BaseModel):
    """Parameters for the handshake protocol."""
    phase: HandshakePhase
    agent_id: str
    agent_name: str = ""
    agent_type: str = ""
    agent_version: str = ""
    public_key: Optional[str] = None
    capabilities: list[str] = Field(default_factory=list)
    protocol_version: str = "1.0"
    nonce: Optional[str] = None
    challenge: Optional[str] = None
    challenge_response: Optional[str] = None
    session_id: Optional[str] = None
    encryption: Optional[str] = None


class MessageParams(BaseModel):
    """Parameters for a message."""
    type: str = "message"
    content: str
    attachments: list[dict] = Field(default_factory=list)
    metadata: dict = Field(default_factory=dict)
    project: Optional[str] = None
    timestamp: Optional[str] = None


class ErrorParams(BaseModel):
    """Error parameters."""
    code: int
    message: str
    data: Optional[Any] = None


class JsonRpcRequest(BaseModel):
    """JSON-RPC 2.0 Request."""
    jsonrpc: str = "2.0"
    method: str
    params: dict = Field(default_factory=dict)
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))


class JsonRpcResponse(BaseModel):
    """JSON-RPC 2.0 Response."""
    jsonrpc: str = "2.0"
    result: Optional[Any] = None
    error: Optional[ErrorParams] = None
    id: str


class JsonRpcNotification(BaseModel):
    """JSON-RPC 2.0 Notification (no id, no response expected)."""
    jsonrpc: str = "2.0"
    method: str
    params: dict = Field(default_factory=dict)


# Convenience constructors

def make_handshake(phase: HandshakePhase, agent_info: AgentInfo, **kwargs) -> str:
    """Create a handshake JSON-RPC message."""
    params = {
        "phase": phase.value,
        "agent_id": agent_info.agent_id,
        "agent_name": agent_info.agent_name,
        "agent_type": agent_info.agent_type,
        "agent_version": agent_info.agent_version,
        "public_key": agent_info.public_key,
        "capabilities": agent_info.capabilities,
        "protocol_version": agent_info.protocol_version,
        "nonce": agent_info.nonce,
    }
    params.update(kwargs)
    # Remove None values
    params = {k: v for k, v in params.items() if v is not None}
    
    msg = JsonRpcRequest(
        method=MessageType.HANDSHAKE.value,
        params=params,
    )
    return msg.model_dump_json()


def make_message(content: str, project: str = None, metadata: dict = None) -> str:
    """Create a message JSON-RPC message."""
    params = {
        "type": "message",
        "content": content,
        "timestamp": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
    }
    if project:
        params["project"] = project
    if metadata:
        params["metadata"] = metadata
    
    msg = JsonRpcRequest(
        method=MessageType.SEND.value,
        params=params,
    )
    return msg.model_dump_json()


def make_heartbeat() -> str:
    """Create a heartbeat notification."""
    notif = JsonRpcNotification(
        method=MessageType.HEARTBEAT.value,
        params={"timestamp": time.time()},
    )
    return notif.model_dump_json()


def make_error(code: int, message: str, req_id: str = "0") -> str:
    """Create a JSON-RPC error response."""
    resp = JsonRpcResponse(
        error=ErrorParams(code=code, message=message),
        id=req_id,
    )
    return resp.model_dump_json()


def make_response(result: Any, req_id: str) -> str:
    """Create a JSON-RPC success response."""
    resp = JsonRpcResponse(result=result, id=req_id)
    return resp.model_dump_json()


def parse_message(raw: str) -> dict:
    """Parse a raw JSON string into a message dict.
    
    Returns the parsed dict. Raises ValueError if invalid JSON.
    """
    try:
        data = json.loads(raw)
    except json.JSONDecodeError as e:
        raise ValueError(f"Invalid JSON: {e}")
    
    if "jsonrpc" not in data or data["jsonrpc"] != "2.0":
        raise ValueError("Not a valid JSON-RPC 2.0 message")
    
    return data


def is_request(data: dict) -> bool:
    """Check if a parsed message is a request (has method and id)."""
    return "method" in data and "id" in data


def is_notification(data: dict) -> bool:
    """Check if a parsed message is a notification (has method, no id)."""
    return "method" in data and "id" not in data


def is_response(data: dict) -> bool:
    """Check if a parsed message is a response (has result or error, and id)."""
    return ("result" in data or "error" in data) and "id" in data
