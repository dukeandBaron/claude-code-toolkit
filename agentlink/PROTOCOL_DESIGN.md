# AgentLink Protocol Design
## A2A Communication Protocol for AI Agents (Hermes Agent / Claude Code)

Version: 1.0-draft
Date: 2026-05-28
Author: Hermes Agent Research Subagent

---

## 1. Executive Summary

This document designs "AgentLink" -- a lightweight agent-to-agent (A2A) communication
protocol for connecting two AI agent instances (Hermes Agent, Claude Code, etc.) across
machines. It supports both LAN (same WiFi) and WAN (different networks) communication
with end-to-end encryption and a TCP-like handshake.

### Design Philosophy
- **Simplicity first**: JSON-RPC 2.0 over WebSocket (inspired by MCP and Google A2A)
- **Dual transport**: WebSocket for real-time, HTTP REST for fire-and-forget
- **Zero-config LAN**: mDNS discovery with fallback to manual pairing
- **WAN-ready**: Tailscale/Zerotier overlay OR relay server for NAT traversal
- **Security**: Ed25519 key exchange + AES-256-GCM encrypted payloads

---

## 2. Existing Protocol Analysis

### 2.1 MCP (Model Context Protocol) -- by Anthropic
- Transport: stdio (local) or Streamable HTTP (remote)
- Encoding: JSON-RPC 2.0, UTF-8
- Streamable HTTP: POST to single endpoint, optional SSE streaming
- Session management via Mcp-Session-Id header
- Designed for client-server (tool provider <-> LLM), NOT peer-to-peer
- **Relevant borrow**: JSON-RPC encoding, SSE streaming pattern, session IDs

### 2.2 A2A (Agent2Agent Protocol) -- by Google
- Transport: JSON-RPC 2.0 over HTTP(S)
- Agent discovery via "Agent Card" (JSON document at /.well-known/agent.json)
- Supports: synchronous, streaming (SSE), async push notifications
- Task lifecycle: submitted -> working -> input-required -> completed/failed/canceled
- Rich data: text, files, structured JSON "Parts"
- Designed for enterprise agent orchestration, heavier than we need
- **Relevant borrow**: Agent Card discovery, Task lifecycle, Part-based message format

### 2.3 Agent Protocol -- by AI Agent Foundation
- REST API standard for agent communication
- Focuses on task submission and polling
- Less real-time oriented
- **Verdict**: Too polling-based for our needs

### Our Gap
None of these protocols solve the specific problem of:
- Two EQUAL peers (not client-server) connecting
- NAT traversal for home networks
- Lightweight enough to run inside an AI agent process
- Both LAN and WAN in one protocol

---

## 3. Protocol Design: AgentLink

### 3.1 Architecture Overview

```
  Machine A (Hermes Agent)          Machine B (Claude Code)
  +---------------------+           +---------------------+
  | AgentLink Client    |           | AgentLink Client    |
  |  - WebSocket conn   |<=========>|  - WebSocket conn   |
  |  - HTTP REST API    |           |  - HTTP REST API    |
  |  - mDNS broadcaster |           |  - mDNS listener    |
  +---------------------+           +---------------------+
        |        |                         |        |
    [LAN Mode] [WAN Mode]             [LAN Mode] [WAN Mode]
        |        |                         |        |
   Direct TCP  Tailscale/              Direct TCP  Tailscale/
   or mDNS     Relay Server            or mDNS     Relay Server
```

### 3.2 Transport Layer

**Primary: WebSocket (RFC 6455)**
- Full-duplex, real-time bidirectional messaging
- Low latency (~1ms LAN, ~50ms WAN)
- Built-in framing (no manual message boundary handling)
- Supported by all modern languages and platforms

**Fallback: HTTP REST + SSE**
- For environments where WebSocket is blocked
- POST /api/message for sending
- GET /api/events (SSE) for receiving
- Polling fallback if SSE also blocked

**Why NOT raw TCP?**
- WebSocket IS TCP with HTTP upgrade handshake
- Raw TCP requires manual framing, reconnection, etc.
- WebSocket gives us all TCP benefits + standard tooling

### 3.3 Message Format: JSON-RPC 2.0

Following MCP and A2A conventions:

```json
{
    "jsonrpc": "2.0",
    "method": "agentlink.send",
    "params": {
        "type": "message",
        "content": "Here's my analysis of the 3DGS paper...",
        "attachments": [],
        "metadata": {
            "project": "3dgs-research",
            "timestamp": "2026-05-28T10:30:00Z"
        }
    },
    "id": "msg-uuid-001"
}
```

Response:
```json
{
    "jsonrpc": "2.0",
    "result": {
        "status": "delivered",
        "message_id": "msg-uuid-001"
    },
    "id": "msg-uuid-001"
}
```

### 3.4 Message Types

| Method | Direction | Description |
|--------|-----------|-------------|
| agentlink.handshake | Both | Initial connection handshake |
| agentlink.send | Both | Send a message to peer |
| agentlink.capabilities | Both | Announce agent capabilities |
| agentlink.heartbeat | Both | Keep-alive ping |
| agentlink.disconnect | Both | Graceful disconnect |
| agentlink.file.offer | Both | Offer a file transfer |
| agentlink.file.accept | Both | Accept file transfer |
| agentlink.file.chunk | Both | File data chunk |
| agentlink.task.create | Both | Create a collaborative task |
| agentlink.task.update | Both | Update task status |
| agentlink.error | Both | Error notification |

---

## 4. Connection Handshake Protocol

### 4.1 Three-Phase Handshake (TCP-inspired)

```
Machine A (Initiator)          Machine B (Responder)
       |                              |
       |--- [1] HELLO (agent_info) -->|
       |                              |
       |<-- [2] WELCOME (agent_info) -|
       |                              |
       |--- [3] READY (session_key) ->|
       |                              |
       |<========= ENCRYPTED ========>|
       |     Bidirectional Channel    |
```

Phase 1 - HELLO (Initiator -> Responder):
```json
{
    "jsonrpc": "2.0",
    "method": "agentlink.handshake",
    "params": {
        "phase": "hello",
        "agent_id": "hermes-agent-alice-001",
        "agent_name": "Alice's Hermes Agent",
        "agent_type": "hermes-agent",
        "agent_version": "0.14.0",
        "public_key": "base64-ed25519-public-key",
        "capabilities": ["messaging", "file-transfer", "task-collab"],
        "protocol_version": "1.0",
        "nonce": "random-32-byte-hex"
    },
    "id": "handshake-001"
}
```

Phase 2 - WELCOME (Responder -> Initiator):
```json
{
    "jsonrpc": "2.0",
    "method": "agentlink.handshake",
    "params": {
        "phase": "welcome",
        "agent_id": "claude-code-bob-001",
        "agent_name": "Bob's Claude Code",
        "agent_type": "claude-code",
        "agent_version": "1.0.0",
        "public_key": "base64-ed25519-public-key",
        "capabilities": ["messaging", "file-transfer", "task-collab"],
        "protocol_version": "1.0",
        "nonce": "random-32-byte-hex",
        "challenge": "base64-encrypted-challenge"
    },
    "id": "handshake-001"
}
```

Phase 3 - READY (Initiator -> Responder):
```json
{
    "jsonrpc": "2.0",
    "method": "agentlink.handshake",
    "params": {
        "phase": "ready",
        "session_id": "uuid-session-id",
        "challenge_response": "base64-signed-challenge",
        "shared_secret": "base64-x25519-derived-key",
        "encryption": "aes-256-gcm"
    },
    "id": "handshake-001"
}
```

### 4.2 Key Exchange Flow

1. Both agents generate Ed25519 keypairs on startup
2. Exchange public keys in HELLO/WELCOME
3. Perform X25519 Diffie-Hellman to derive shared secret
4. Use shared secret as AES-256-GCM key for message encryption
5. Sign handshake messages with Ed25519 to prevent MITM

---

## 5. LAN Discovery

### 5.1 mDNS/DNS-SD (Primary Method)

Register service: `_agentlink._tcp.local.`

```
Service Type:  _agentlink._tcp
Instance Name: <agent_name> (<agent_type>)
Port:          7600 (default)
TXT Records:
  - id=<agent_id>
  - type=<agent_type>
  - version=<protocol_version>
  - capabilities=<comma-separated>
```

Python implementation using `zeroconf` library:
```python
from zeroconf import ServiceInfo, Zeroconf
import socket

info = ServiceInfo(
    "_agentlink._tcp.local.",
    "Alice Hermes Agent._agentlink._tcp.local.",
    addresses=[socket.inet_aton("192.168.1.100")],
    port=7600,
    properties={
        "id": "hermes-alice-001",
        "type": "hermes-agent",
        "version": "1.0",
    }
)
zeroconf = Zeroconf()
zeroconf.register_service(info)
```

### 5.2 UDP Broadcast (Fallback)

Broadcast on port 7601 every 5 seconds:
```json
{
    "type": "agentlink.discovery",
    "agent_id": "hermes-alice-001",
    "agent_name": "Alice's Hermes Agent",
    "ws_port": 7600,
    "http_port": 7601
}
```

### 5.3 Manual Pairing (Always Available)

If discovery fails, agents can connect directly:
```
agentlink connect 192.168.1.100:7600
# or
agentlink connect agentlink://alice-hermes.local:7600
```

---

## 6. WAN Connectivity

### 6.1 Option A: Tailscale (Recommended for Simplicity)

Tailscale creates a WireGuard mesh VPN between machines:
- Zero configuration after install
- Works through NATs automatically
- Encrypted by default (WireGuard)
- Free for personal use

Setup:
1. Both users install Tailscale
2. Login with same Tailnet or share device
3. Agent connects to peer's Tailscale IP:7600
4. No port forwarding needed

### 6.2 Option B: Zerotier (Open Source Alternative)

Similar to Tailscale but fully open source:
- Self-hostable controller
- P2P with STUN, falls back to relay
- More configuration needed

### 6.3 Option C: Relay Server

A lightweight relay/proxy server on a VPS:
```
Agent A ---> Relay Server (VPS) ---> Agent B
           wss://relay.example.com
```

The relay server:
- Accepts WebSocket connections from both agents
- Pairs agents by shared secret / room code
- Forwards encrypted messages (never decrypts)
- ~100 lines of Python

### 6.4 Option D: STUN/UDP Hole Punching (Advanced)

For true P2P without any intermediary:
- Use STUN server to discover public IP/port
- Simultaneous open technique
- Unreliable with symmetric NATs
- Not recommended as primary method

### Recommendation
**Use Tailscale for WAN.** It's the most reliable, zero-config solution.
Build a relay server as backup for users who can't install Tailscale.

---

## 7. Security Model

### 7.1 Threat Model

| Threat | Mitigation |
|--------|------------|
| Eavesdropping | AES-256-GCM encryption on all messages |
| Man-in-the-Middle | Ed25519 signature verification during handshake |
| Unauthorized Access | Pre-shared pairing secret OR public key pinning |
| Replay Attacks | Nonce + timestamp in every message |
| Message Tampering | HMAC-SHA256 on message payloads |

### 7.2 Authentication Methods

**Method 1: Pre-Shared Pairing Code (Simplest)**
- One agent generates a 6-digit code
- Other agent enters code to pair
- Similar to Bluetooth pairing
- Codes expire after 5 minutes

**Method 2: Public Key Pinning**
- First connection verified out-of-band
- Public keys stored locally
- Subsequent connections verified against stored keys
- Like SSH known_hosts

**Method 3: API Key + JWT**
- Pre-configured API keys exchanged out-of-band
- JWT tokens for session management
- Best for automated/headless connections

### 7.3 Encryption

```
Handshake:  Ed25519 signatures (authentication)
            X25519 ECDH (key agreement)
Messages:   AES-256-GCM (authenticated encryption)
            With per-message nonce derived from session counter
```

### 7.4 LAN vs WAN Security

LAN (same WiFi):
- mDNS discovery is local-only (safe)
- Can optionally skip encryption for performance on trusted networks
- Pairing code authentication sufficient

WAN (different networks):
- Encryption MANDATORY
- Public key pinning OR API key required
- Tailscale provides WireGuard encryption at network layer
- Application-layer encryption as defense-in-depth

---

## 8. Python Implementation Architecture

### 8.1 Technology Stack

| Component | Library | Purpose |
|-----------|---------|---------|
| WebSocket Server | `websockets` | Real-time bidirectional messaging |
| HTTP REST API | `FastAPI` + `uvicorn` | REST endpoints, SSE fallback |
| mDNS Discovery | `zeroconf` | LAN agent discovery |
| Cryptography | `cryptography` + `PyNaCl` | Ed25519, X25519, AES-GCM |
| Serialization | `pydantic` | Message validation |
| Async Runtime | `asyncio` | Event loop |

### 8.2 Module Structure

```
agentlink/
    __init__.py
    protocol.py        # Message types, JSON-RPC handling
    server.py          # WebSocket + HTTP server
    client.py          # WebSocket client for connecting to peers
    discovery.py       # mDNS + UDP broadcast discovery
    crypto.py          # Key generation, encryption, signing
    handshake.py       # Three-phase handshake implementation
    relay.py           # Relay server for WAN
    config.py          # Configuration management
    storage.py         # Key storage, peer history
```

### 8.3 Core Dependencies (pip install)

```
websockets>=12.0
fastapi>=0.110.0
uvicorn>=0.29.0
zeroconf>=0.131.0
cryptography>=42.0.0
PyNaCl>=1.5.0
pydantic>=2.6.0
httpx>=0.27.0
```

---

## 9. Comparison with Alternatives

| Feature | AgentLink | MCP Streamable HTTP | Google A2A | Raw TCP |
|---------|-----------|-------------------|------------|---------|
| Peer-to-Peer | Yes | No (client-server) | No (client-server) | Yes |
| Real-time | WebSocket | SSE (server->client) | SSE (server->client) | Yes |
| LAN Discovery | mDNS built-in | None | None | None |
| NAT Traversal | Tailscale/Relay | Not addressed | Not addressed | Manual |
| Encryption | E2E + transport | TLS only | TLS only | None built-in |
| Agent Identity | Ed25519 keys | None | Agent Card | None |
| Complexity | Medium | Low | High | Low |
| Python SDK | Built | MCP SDK | a2a-sdk | stdlib |

---

## 10. Implementation Roadmap

### Phase 1: Core Protocol (Week 1)
- [ ] Message types and JSON-RPC encoding
- [ ] WebSocket server/client
- [ ] Three-phase handshake
- [ ] Basic encryption (Ed25519 + AES-GCM)

### Phase 2: LAN Features (Week 2)
- [ ] mDNS discovery
- [ ] UDP broadcast fallback
- [ ] Manual pairing with codes
- [ ] File transfer

### Phase 3: WAN Features (Week 3)
- [ ] Tailscale integration
- [ ] Relay server
- [ ] Reconnection handling
- [ ] Message queuing for offline peers

### Phase 4: Integration (Week 4)
- [ ] Hermes Agent skill integration
- [ ] Claude Code integration
- [ ] Collaborative task management
- [ ] Shared workspace sync

---

## Appendix A: Port Assignments

| Port | Protocol | Purpose |
|------|----------|---------|
| 7600 | WebSocket (WSS) | Primary agent communication |
| 7601 | HTTP | REST API + SSE fallback |
| 7602 | UDP | Discovery broadcast |
| 7603 | mDNS | LAN discovery (multicast) |

## Appendix B: Wire Format Example

Complete handshake sequence over WebSocket:

```
--> {"jsonrpc":"2.0","method":"agentlink.handshake","params":{"phase":"hello","agent_id":"hermes-alice","agent_type":"hermes-agent","public_key":"MCowBQYDK2VwAyEA...","nonce":"a1b2c3..."},"id":"h1"}
<-- {"jsonrpc":"2.0","method":"agentlink.handshake","params":{"phase":"welcome","agent_id":"claude-bob","agent_type":"claude-code","public_key":"MCowBQYDK2VwAyEB...","nonce":"d4e5f6...","challenge":"..."},"id":"h1"}
--> {"jsonrpc":"2.0","method":"agentlink.handshake","params":{"phase":"ready","session_id":"uuid","challenge_response":"signed-by-alice","encryption":"aes-256-gcm"},"id":"h1"}
<-- {"jsonrpc":"2.0","method":"agentlink.capabilities","params":{"features":["messaging","files","tasks"]},"id":"h2"}
--> {"jsonrpc":"2.0","method":"agentlink.send","params":{"content":"Hey Bob, let's work on the 3DGS paper together!","project":"3dgs"},"id":"m1"}
```
