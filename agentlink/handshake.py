"""
AgentLink Protocol - Three-Phase Handshake Implementation

The handshake establishes:
1. Agent identity exchange (HELLO / WELCOME)
2. Cryptographic key exchange (X25519 ECDH)
3. Session establishment with encrypted channel (READY)

This is analogous to TCP's three-way handshake (SYN, SYN-ACK, ACK)
but with cryptographic identity verification.
"""

import asyncio
import logging
import time
from enum import Enum
from typing import Optional, Callable, Awaitable

from .protocol import (
    HandshakePhase, AgentInfo, MessageType,
    make_handshake, make_response, make_error, parse_message,
)
from .crypto import AgentKeyPair, SessionCipher, create_keypair, generate_nonce

logger = logging.getLogger("agentlink.handshake")


class HandshakeState(str, Enum):
    IDLE = "idle"
    HELLO_SENT = "hello_sent"
    WELCOME_RECEIVED = "welcome_received"
    READY_SENT = "ready_sent"
    COMPLETE = "complete"
    FAILED = "failed"


class HandshakeError(Exception):
    """Raised when handshake fails."""
    pass


class HandshakeSession:
    """
    Manages the three-phase handshake for one side of the connection.
    
    Usage as Initiator (client):
        session = HandshakeSession(my_info, keypair, role="initiator")
        hello_msg = session.start()         # Phase 1
        # send hello_msg, receive welcome_msg
        ready_msg = session.receive_welcome(welcome_msg)  # Phase 2
        # send ready_msg
        # Handshake complete -> session.cipher available
    
    Usage as Responder (server):
        session = HandshakeSession(my_info, keypair, role="responder")
        # receive hello_msg
        welcome_msg = session.receive_hello(hello_msg)  # Phase 1
        # send welcome_msg, receive ready_msg
        session.receive_ready(ready_msg)  # Phase 2
        # Handshake complete -> session.cipher available
    """
    
    def __init__(
        self,
        agent_info: AgentInfo,
        keypair: AgentKeyPair,
        role: str = "initiator",  # "initiator" or "responder"
    ):
        self.agent_info = agent_info
        self.keypair = keypair
        self.role = role
        self.state = HandshakeState.IDLE
        
        # Peer info (populated during handshake)
        self.peer_info: Optional[AgentInfo] = None
        self.peer_public_key: Optional[str] = None
        self.peer_encryption_key: Optional[str] = None
        
        # Session
        self.session_id: Optional[str] = None
        self.cipher: Optional[SessionCipher] = None
        self.nonce: str = generate_nonce()
        
        # Update agent_info with our nonce
        self.agent_info.nonce = self.nonce
    
    @property
    def is_complete(self) -> bool:
        return self.state == HandshakeState.COMPLETE
    
    def start(self) -> str:
        """
        Phase 1 (Initiator): Send HELLO.
        
        Returns the JSON-RPC message to send.
        """
        if self.role != "initiator":
            raise HandshakeError("Only initiator can start handshake")
        if self.state != HandshakeState.IDLE:
            raise HandshakeError(f"Cannot start handshake in state {self.state}")
        
        self.state = HandshakeState.HELLO_SENT
        
        msg = make_handshake(
            phase=HandshakePhase.HELLO,
            agent_info=self.agent_info,
        )
        
        logger.info(f"[HANDSHAKE] Sent HELLO: {self.agent_info.agent_id}")
        return msg
    
    def receive_hello(self, raw_message: str) -> str:
        """
        Phase 1 (Responder): Receive HELLO, send WELCOME.
        
        Parses the initiator's HELLO message, stores their info,
        and returns the WELCOME response.
        
        Returns the JSON-RPC message to send.
        """
        if self.role != "responder":
            raise HandshakeError("Only responder processes HELLO")
        if self.state != HandshakeState.IDLE:
            raise HandshakeError(f"Cannot process HELLO in state {self.state}")
        
        data = parse_message(raw_message)
        params = data.get("params", {})
        
        if params.get("phase") != HandshakePhase.HELLO.value:
            raise HandshakeError(f"Expected HELLO, got {params.get('phase')}")
        
        # Store peer info
        self.peer_info = AgentInfo(
            agent_id=params["agent_id"],
            agent_name=params.get("agent_name", ""),
            agent_type=params.get("agent_type", "unknown"),
            agent_version=params.get("agent_version", ""),
            public_key=params.get("public_key"),
            capabilities=params.get("capabilities", []),
            protocol_version=params.get("protocol_version", "1.0"),
            nonce=params.get("nonce"),
        )
        self.peer_public_key = params.get("public_key")
        self.peer_encryption_key = params.get("public_key")  # Same for now
        
        logger.info(f"[HANDSHAKE] Received HELLO from: {self.peer_info.agent_id}")
        
        # Generate session ID
        import uuid
        self.session_id = str(uuid.uuid4())
        
        # Create challenge (sign the peer's nonce)
        peer_nonce = params.get("nonce", "")
        challenge = self.keypair.sign_b64(peer_nonce.encode())
        
        self.state = HandshakeState.WELCOME_RECEIVED
        
        msg = make_handshake(
            phase=HandshakePhase.WELCOME,
            agent_info=self.agent_info,
            session_id=self.session_id,
            challenge=challenge,
        )
        
        logger.info(f"[HANDSHAKE] Sent WELCOME: session={self.session_id}")
        return msg
    
    def receive_welcome(self, raw_message: str) -> str:
        """
        Phase 2 (Initiator): Receive WELCOME, send READY.
        
        Verifies the responder's challenge, derives shared key,
        and returns the READY message.
        
        Returns the JSON-RPC message to send.
        """
        if self.role != "initiator":
            raise HandshakeError("Only initiator processes WELCOME")
        if self.state != HandshakeState.HELLO_SENT:
            raise HandshakeError(f"Cannot process WELCOME in state {self.state}")
        
        data = parse_message(raw_message)
        params = data.get("params", {})
        
        if params.get("phase") != HandshakePhase.WELCOME.value:
            raise HandshakeError(f"Expected WELCOME, got {params.get('phase')}")
        
        # Store peer info
        self.peer_info = AgentInfo(
            agent_id=params["agent_id"],
            agent_name=params.get("agent_name", ""),
            agent_type=params.get("agent_type", "unknown"),
            agent_version=params.get("agent_version", ""),
            public_key=params.get("public_key"),
            capabilities=params.get("capabilities", []),
            protocol_version=params.get("protocol_version", "1.0"),
            nonce=params.get("nonce"),
        )
        self.peer_public_key = params.get("public_key")
        self.peer_encryption_key = params.get("public_key")
        
        logger.info(f"[HANDSHAKE] Received WELCOME from: {self.peer_info.agent_id}")
        
        # Verify challenge (responder signed our nonce)
        challenge = params.get("challenge", "")
        if challenge and self.peer_public_key:
            # Verify the signature
            valid = self.keypair.verify(
                self.nonce.encode(),
                __import__('base64').b64decode(challenge),
                self.peer_public_key,
            )
            if not valid:
                raise HandshakeError("Challenge verification failed - possible MITM")
            logger.info("[HANDSHAKE] Challenge verified successfully")
        
        # Derive shared encryption key
        if self.peer_encryption_key:
            shared_key = self.keypair.derive_shared_key(self.peer_encryption_key)
            self.cipher = SessionCipher(shared_key)
            logger.info("[HANDSHAKE] Shared encryption key derived")
        
        # Get session ID
        self.session_id = params.get("session_id")
        
        # Create our challenge response (sign the peer's nonce)
        peer_nonce = params.get("nonce", "")
        challenge_response = self.keypair.sign_b64(peer_nonce.encode())
        
        self.state = HandshakeState.READY_SENT
        
        msg = make_handshake(
            phase=HandshakePhase.READY,
            agent_info=self.agent_info,
            session_id=self.session_id,
            challenge_response=challenge_response,
            encryption="aes-256-gcm",
        )
        
        logger.info(f"[HANDSHAKE] Sent READY: session={self.session_id}")
        return msg
    
    def receive_ready(self, raw_message: str) -> None:
        """
        Phase 3 (Responder): Receive READY.
        
        Verifies the initiator's challenge response and establishes
        the encrypted session.
        """
        if self.role != "responder":
            raise HandshakeError("Only responder processes READY")
        if self.state != HandshakeState.WELCOME_RECEIVED:
            raise HandshakeError(f"Cannot process READY in state {self.state}")
        
        data = parse_message(raw_message)
        params = data.get("params", {})
        
        if params.get("phase") != HandshakePhase.READY.value:
            raise HandshakeError(f"Expected READY, got {params.get('phase')}")
        
        # Verify challenge response (initiator signed our nonce)
        challenge_response = params.get("challenge_response", "")
        if challenge_response and self.peer_public_key:
            valid = self.keypair.verify(
                self.nonce.encode(),
                __import__('base64').b64decode(challenge_response),
                self.peer_public_key,
            )
            if not valid:
                raise HandshakeError("Challenge response verification failed - possible MITM")
            logger.info("[HANDSHAKE] Challenge response verified successfully")
        
        # Derive shared encryption key
        if self.peer_encryption_key:
            shared_key = self.keypair.derive_shared_key(self.peer_encryption_key)
            self.cipher = SessionCipher(shared_key)
            logger.info("[HANDSHAKE] Shared encryption key derived")
        
        self.state = HandshakeState.COMPLETE
        logger.info(f"[HANDSHAKE] Handshake COMPLETE with {self.peer_info.agent_id}")
    
    def complete_initiator(self) -> None:
        """Mark the initiator side as complete after sending READY."""
        self.state = HandshakeState.COMPLETE
        logger.info(f"[HANDSHAKE] Handshake COMPLETE with {self.peer_info.agent_id}")
    
    def get_session_summary(self) -> dict:
        """Get a summary of the established session."""
        return {
            "session_id": self.session_id,
            "state": self.state.value,
            "role": self.role,
            "peer": {
                "id": self.peer_info.agent_id if self.peer_info else None,
                "name": self.peer_info.agent_name if self.peer_info else None,
                "type": self.peer_info.agent_type if self.peer_info else None,
            },
            "encryption": "aes-256-gcm" if self.cipher else None,
            "established_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        }
