"""
AgentLink Protocol Implementation
A lightweight A2A (Agent-to-Agent) communication protocol for AI agents.

Supports:
- WebSocket real-time messaging
- HTTP REST fallback
- LAN discovery via mDNS
- WAN via Tailscale or relay server
- End-to-end encryption (Ed25519 + AES-256-GCM)

Usage:
    # Start a server
    python -m agentlink.server --port 7600 --name "My Agent"

    # Connect to a peer
    python -m agentlink.client --target ws://192.168.1.100:7600
"""

__version__ = "0.1.0"
__protocol_version__ = "1.0"
