"""
Agent Bridge — Configuration
Central configuration for ports, secrets, paths, and timeouts.
"""

import os
import pathlib
import secrets as _secrets_mod

# ─── Paths ────────────────────────────────────────────────────────────────────
BRIDGE_ROOT = pathlib.Path(__file__).resolve().parent

SHARED_MEMORY_DIR = BRIDGE_ROOT / "shared"
MEMORY_FILE = SHARED_MEMORY_DIR / "MEMORY.md"
TASK_QUEUE_FILE = SHARED_MEMORY_DIR / "TASK_QUEUE.md"

# ─── Network ──────────────────────────────────────────────────────────────────
SERVER_HOST = os.environ.get("BRIDGE_HOST", "0.0.0.0")
SERVER_PORT = int(os.environ.get("BRIDGE_PORT", "9527"))

DISCOVERY_PORT = int(os.environ.get("BRIDGE_DISCOVERY_PORT", "9527"))
DISCOVERY_INTERVAL = 5
DISCOVERY_BROADCAST = "255.255.255.255"

# ─── Authentication ───────────────────────────────────────────────────────────
API_SECRET = os.environ.get("BRIDGE_SECRET", "")
TOKEN_TTL = 300  # seconds, 5 min window
ALLOWED_AGENTS: list[str] = []  # empty = allow all with valid token

# ─── Timeouts ─────────────────────────────────────────────────────────────────
HEARTBEAT_INTERVAL = 15
HEARTBEAT_TIMEOUT = 45
CLIENT_RECONNECT_DELAY = 5
MAX_MESSAGE_SIZE = 4 * 1024 * 1024  # 4 MB

# ─── Logging ──────────────────────────────────────────────────────────────────
LOG_LEVEL = os.environ.get("BRIDGE_LOG_LEVEL", "INFO").upper()
LOG_FORMAT = "%(asctime)s [%(name)s] %(levelname)s  %(message)s"
LOG_DATE_FORMAT = "%Y-%m-%d %H:%M:%S"

# ─── Capabilities ─────────────────────────────────────────────────────────────
CAPABILITIES = [
    "memory.read",
    "memory.write",
    "memory.sync",
    "task.publish",
    "task.claim",
    "task.complete",
    "task.list",
    "message.send",
    "file.transfer",
    "agent.heartbeat",
    "agent.info",
]


def get_secret() -> str:
    """Return the API secret, generating + persisting one if necessary."""
    if API_SECRET:
        return API_SECRET

    secret_file = BRIDGE_ROOT / ".bridge_secret"
    if secret_file.exists():
        return secret_file.read_text(encoding="utf-8").strip()

    new_secret = _secrets_mod.token_urlsafe(32)
    secret_file.write_text(new_secret, encoding="utf-8")
    print(f"[config] Generated new shared secret -> {secret_file}")
    print(f"[config] Set BRIDGE_SECRET env on the other agent,")
    print(f"         or copy .bridge_secret to the other machine.")
    return new_secret
