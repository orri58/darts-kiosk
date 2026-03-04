"""
Pairing Service – Secure pairing between Master and Agent.

Flow:
1. Agent generates rotating 6-digit pairing code (rotates every 60s)
2. Master sends code to agent's /api/agent/pair/initiate endpoint
3. Agent verifies code, returns a one-time challenge (random nonce)
4. Master signs challenge with its fingerprint, sends back
5. Agent verifies signature, issues a paired_token
6. Both sides store the trust relationship in TrustedPeer table
7. Future API calls use paired_token + HMAC
"""
import hashlib
import hmac
import secrets
import logging
import time
from datetime import datetime, timezone
from typing import Optional, Tuple
from dataclasses import dataclass

logger = logging.getLogger(__name__)

CODE_ROTATION_SECONDS = 60
CODE_LENGTH = 6
CHALLENGE_EXPIRY_SECONDS = 30


@dataclass
class PairingChallenge:
    nonce: str
    board_id: str
    created_at: float
    master_ip: str


class PairingService:
    """Manages pairing codes, challenges, and token generation."""

    def __init__(self):
        self._current_code: Optional[str] = None
        self._code_generated_at: float = 0
        self._pending_challenges: dict[str, PairingChallenge] = {}
        self._used_nonces: set[str] = set()  # replay prevention

    # ------------------------------------------------------------------
    # Agent side: generate / verify pairing code
    # ------------------------------------------------------------------
    def get_pairing_code(self) -> Tuple[str, int]:
        """Return current 6-digit code and seconds until it expires."""
        now = time.time()
        elapsed = now - self._code_generated_at

        if not self._current_code or elapsed >= CODE_ROTATION_SECONDS:
            self._current_code = self._generate_code()
            self._code_generated_at = now
            elapsed = 0

        remaining = max(0, int(CODE_ROTATION_SECONDS - elapsed))
        return self._current_code, remaining

    def verify_code(self, code: str) -> bool:
        """Verify a submitted pairing code."""
        current, remaining = self.get_pairing_code()
        if remaining <= 0:
            return False
        return hmac.compare_digest(code, current)

    # ------------------------------------------------------------------
    # Challenge-response
    # ------------------------------------------------------------------
    def create_challenge(self, board_id: str, master_ip: str) -> str:
        """Create a one-time challenge nonce for the master to sign."""
        nonce = secrets.token_hex(32)
        self._pending_challenges[nonce] = PairingChallenge(
            nonce=nonce,
            board_id=board_id,
            created_at=time.time(),
            master_ip=master_ip,
        )
        # Cleanup old challenges
        self._cleanup_challenges()
        return nonce

    def verify_challenge_response(self, nonce: str, signature: str,
                                  master_fingerprint: str, master_ip: str) -> bool:
        """Verify the master's signed response to our challenge."""
        if nonce in self._used_nonces:
            logger.warning(f"Replay attempt: nonce {nonce[:8]}... already used")
            return False

        challenge = self._pending_challenges.get(nonce)
        if not challenge:
            logger.warning("Challenge not found")
            return False

        # Check expiry
        if time.time() - challenge.created_at > CHALLENGE_EXPIRY_SECONDS:
            logger.warning("Challenge expired")
            del self._pending_challenges[nonce]
            return False

        # Check IP matches
        if challenge.master_ip != master_ip:
            logger.warning(f"IP mismatch: expected {challenge.master_ip}, got {master_ip}")
            return False

        # Verify signature: HMAC(nonce, master_fingerprint)
        expected = hmac.new(
            master_fingerprint.encode(), nonce.encode(), hashlib.sha256
        ).hexdigest()

        if not hmac.compare_digest(signature, expected):
            logger.warning("Invalid challenge signature")
            return False

        # Mark nonce as used (replay prevention)
        self._used_nonces.add(nonce)
        del self._pending_challenges[nonce]

        # Trim used_nonces set (keep last 1000)
        if len(self._used_nonces) > 1000:
            self._used_nonces = set(list(self._used_nonces)[-500:])

        return True

    # ------------------------------------------------------------------
    # Token generation
    # ------------------------------------------------------------------
    @staticmethod
    def generate_paired_token() -> str:
        """Generate a long-lived paired token for authenticated agent API calls."""
        return secrets.token_urlsafe(48)

    @staticmethod
    def hash_token(token: str) -> str:
        """Hash a token for storage."""
        return hashlib.sha256(token.encode()).hexdigest()

    @staticmethod
    def compute_hmac(token: str, payload: str) -> str:
        """Compute HMAC for request signing."""
        return hmac.new(token.encode(), payload.encode(), hashlib.sha256).hexdigest()

    @staticmethod
    def verify_hmac(token: str, payload: str, signature: str) -> bool:
        """Verify HMAC signature."""
        expected = hmac.new(token.encode(), payload.encode(), hashlib.sha256).hexdigest()
        return hmac.compare_digest(expected, signature)

    @staticmethod
    def compute_fingerprint(identifier: str) -> str:
        """Compute a public fingerprint for a board/master."""
        import socket
        raw = f"{identifier}:{socket.gethostname()}"
        return hashlib.sha256(raw.encode()).hexdigest()[:16]

    # ------------------------------------------------------------------
    # Internal
    # ------------------------------------------------------------------
    def _generate_code(self) -> str:
        return str(secrets.randbelow(10**CODE_LENGTH)).zfill(CODE_LENGTH)

    def _cleanup_challenges(self):
        now = time.time()
        expired = [n for n, c in self._pending_challenges.items()
                   if now - c.created_at > CHALLENGE_EXPIRY_SECONDS * 2]
        for n in expired:
            del self._pending_challenges[n]


pairing_service = PairingService()
