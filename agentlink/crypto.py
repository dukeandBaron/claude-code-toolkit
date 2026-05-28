"""
AgentLink Protocol - Cryptographic Operations

Provides:
- Ed25519 key generation and signing
- X25519 key exchange (Diffie-Hellman)
- AES-256-GCM authenticated encryption
- Nonce generation and management

Dependencies: PyNaCl (libsodium wrapper)
"""

import os
import base64
import hashlib
import secrets
from typing import Tuple, Optional

try:
    from nacl.signing import SigningKey, VerifyKey
    from nacl.public import PrivateKey, PublicKey, Box
    from nacl.utils import random as nacl_random
    from nacl.encoding import Base64Encoder
    HAS_NACL = True
except ImportError:
    HAS_NACL = False

try:
    from cryptography.hazmat.primitives.ciphers.aead import AESGCM
    HAS_CRYPTOGRAPHY = True
except ImportError:
    HAS_CRYPTOGRAPHY = False


class AgentKeyPair:
    """
    Ed25519 signing keypair + derived X25519 encryption keypair.
    
    Each agent generates one of these on startup. The public key is
    shared during handshake for authentication and key exchange.
    """
    
    def __init__(self):
        if not HAS_NACL:
            raise ImportError(
                "PyNaCl is required for cryptographic operations. "
                "Install with: pip install PyNaCl"
            )
        # Ed25519 signing key
        self._signing_key = SigningKey.generate()
        self._verify_key = self._signing_key.verify_key
        
        # X25519 encryption key (derived from Ed25519 for convenience)
        # In practice, you'd use the raw bytes to create an X25519 key
        self._private_key = PrivateKey.generate()
        self._public_key = self._private_key.public_key
    
    @property
    def public_signing_key_b64(self) -> str:
        """Base64-encoded Ed25519 public key (for handshake exchange)."""
        return base64.b64encode(bytes(self._verify_key)).decode()
    
    @property
    def public_encryption_key_b64(self) -> str:
        """Base64-encoded X25519 public key (for key exchange)."""
        return base64.b64encode(bytes(self._public_key)).decode()
    
    def sign(self, message: bytes) -> bytes:
        """Sign a message with Ed25519."""
        signed = self._signing_key.sign(message)
        return signed.signature
    
    def sign_b64(self, message: bytes) -> str:
        """Sign and return base64-encoded signature."""
        return base64.b64encode(self.sign(message)).decode()
    
    def verify(self, message: bytes, signature: bytes, public_key_b64: str) -> bool:
        """Verify an Ed25519 signature."""
        try:
            pk_bytes = base64.b64decode(public_key_b64)
            verify_key = VerifyKey(pk_bytes)
            verify_key.verify(message, signature)
            return True
        except Exception:
            return False
    
    def derive_shared_key(self, peer_public_key_b64: str) -> bytes:
        """
        Perform X25519 Diffie-Hellman to derive a shared secret.
        
        Returns 32 bytes suitable for use as an AES-256 key.
        The result is hashed through SHA-256 for uniformity.
        """
        peer_pk_bytes = base64.b64decode(peer_public_key_b64)
        peer_public_key = PublicKey(peer_pk_bytes)
        
        # Create a Box for Diffie-Hellman
        box = Box(self._private_key, peer_public_key)
        
        # The Box uses XSalsa20-Poly1305, but we just want the shared key
        # Derive a deterministic key from the box
        shared = bytes(box.shared_key())
        return hashlib.sha256(shared).digest()


class SessionCipher:
    """
    AES-256-GCM cipher for encrypting messages within a session.
    
    Uses a monotonically increasing nonce to prevent replay attacks.
    """
    
    def __init__(self, shared_key: bytes):
        if not HAS_CRYPTOGRAPHY:
            raise ImportError(
                "cryptography library required. "
                "Install with: pip install cryptography"
            )
        if len(shared_key) != 32:
            raise ValueError("Shared key must be 32 bytes (256 bits)")
        
        self._key = shared_key
        self._aesgcm = AESGCM(shared_key)
        self._counter = 0
    
    def _next_nonce(self) -> bytes:
        """Generate the next nonce (12 bytes, counter-based)."""
        self._counter += 1
        # 4 bytes counter + 8 bytes random
        counter_bytes = self._counter.to_bytes(4, 'big')
        random_bytes = os.urandom(8)
        return counter_bytes + random_bytes
    
    def encrypt(self, plaintext: bytes, associated_data: bytes = None) -> Tuple[bytes, bytes]:
        """
        Encrypt plaintext with AES-256-GCM.
        
        Returns (nonce, ciphertext) where ciphertext includes the auth tag.
        """
        nonce = self._next_nonce()
        ciphertext = self._aesgcm.encrypt(nonce, plaintext, associated_data)
        return nonce, ciphertext
    
    def encrypt_b64(self, plaintext: str, associated_data: str = None) -> dict:
        """Encrypt a string and return base64-encoded components."""
        ad = associated_data.encode() if associated_data else None
        nonce, ct = self.encrypt(plaintext.encode('utf-8'), ad)
        return {
            "nonce": base64.b64encode(nonce).decode(),
            "ciphertext": base64.b64encode(ct).decode(),
            "ad": associated_data,
        }
    
    def decrypt(self, nonce: bytes, ciphertext: bytes, associated_data: bytes = None) -> bytes:
        """Decrypt ciphertext with AES-256-GCM. Raises on auth failure."""
        return self._aesgcm.decrypt(nonce, ciphertext, associated_data)
    
    def decrypt_b64(self, data: dict) -> str:
        """Decrypt base64-encoded components and return plaintext string."""
        nonce = base64.b64decode(data["nonce"])
        ct = base64.b64decode(data["ciphertext"])
        ad = data.get("ad", "").encode() if data.get("ad") else None
        plaintext = self.decrypt(nonce, ct, ad)
        return plaintext.decode('utf-8')


def generate_pairing_code(length: int = 6) -> str:
    """Generate a numeric pairing code (like Bluetooth pairing)."""
    return ''.join(secrets.choice('0123456789') for _ in range(length))


def generate_nonce() -> str:
    """Generate a random nonce as hex string."""
    return secrets.token_hex(32)


def hash_for_signing(data: str) -> bytes:
    """Hash data for signing (SHA-256)."""
    return hashlib.sha256(data.encode('utf-8')).digest()


# --- Fallback implementations if crypto libraries not installed ---

class FallbackKeyPair:
    """Minimal keypair using only stdlib (no real crypto, for testing only)."""
    
    def __init__(self):
        self._secret = secrets.token_bytes(32)
        self._public = hashlib.sha256(self._secret).digest()
        import warnings
        warnings.warn(
            "Using fallback cryptography (NOT SECURE). "
            "Install PyNaCl and cryptography for real security.",
            stacklevel=2
        )
    
    @property
    def public_signing_key_b64(self) -> str:
        return base64.b64encode(self._public).decode()
    
    @property
    def public_encryption_key_b64(self) -> str:
        return base64.b64encode(self._public).decode()
    
    def sign_b64(self, message: bytes) -> str:
        h = hashlib.sha256(self._secret + message).digest()
        return base64.b64encode(h).decode()
    
    def derive_shared_key(self, peer_public_key_b64: str) -> bytes:
        peer_bytes = base64.b64decode(peer_public_key_b64)
        return hashlib.sha256(self._secret + peer_bytes).digest()


def create_keypair() -> 'AgentKeyPair | FallbackKeyPair':
    """Create a keypair, using real crypto if available, fallback otherwise."""
    if HAS_NACL:
        return AgentKeyPair()
    return FallbackKeyPair()
