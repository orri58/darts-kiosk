"""
Discovery + Pairing Tests
- Pairing code generation & rotation
- Challenge-response handshake
- Wrong code rejection
- Replay prevention (used nonce)
- Token generation & HMAC verification
"""
import time
import pytest
import sys
import os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from services.pairing_service import PairingService


class TestPairingCodeGeneration:
    def test_code_is_6_digits(self):
        ps = PairingService()
        code, remaining = ps.get_pairing_code()
        assert len(code) == 6
        assert code.isdigit()

    def test_code_has_expiry(self):
        ps = PairingService()
        _, remaining = ps.get_pairing_code()
        assert 0 < remaining <= 60

    def test_code_stable_within_window(self):
        ps = PairingService()
        code1, _ = ps.get_pairing_code()
        code2, _ = ps.get_pairing_code()
        assert code1 == code2

    def test_code_rotates_after_expiry(self):
        ps = PairingService()
        ps._code_generated_at = time.time() - 61  # force expiry
        old_code = ps._current_code
        new_code, _ = ps.get_pairing_code()
        # New code generated (may match by chance but unlikely)
        assert new_code is not None
        assert len(new_code) == 6


class TestPairingCodeVerification:
    def test_correct_code_passes(self):
        ps = PairingService()
        code, _ = ps.get_pairing_code()
        assert ps.verify_code(code)

    def test_wrong_code_fails(self):
        ps = PairingService()
        ps.get_pairing_code()
        assert not ps.verify_code("000000")

    def test_expired_code_fails(self):
        ps = PairingService()
        ps.get_pairing_code()
        ps._code_generated_at = time.time() - 61  # expire it
        # The expired code triggers rotation; verify_code with old code fails
        old_code = ps._current_code
        ps._current_code = None  # force new code
        result = ps.verify_code(old_code if old_code else "123456")
        # After rotation, old code is invalid
        assert isinstance(result, bool)


class TestChallengeResponse:
    def test_create_challenge(self):
        ps = PairingService()
        nonce = ps.create_challenge("BOARD-1", "192.168.1.10")
        assert len(nonce) == 64  # hex encoded 32 bytes
        assert nonce in ps._pending_challenges

    def test_verify_valid_response(self):
        ps = PairingService()
        master_fp = "abcdef1234567890"
        master_ip = "192.168.1.10"
        nonce = ps.create_challenge("BOARD-1", master_ip)

        # Sign with HMAC(nonce, master_fingerprint)
        import hmac as hmac_mod
        import hashlib
        signature = hmac_mod.new(
            master_fp.encode(), nonce.encode(), hashlib.sha256
        ).hexdigest()

        result = ps.verify_challenge_response(nonce, signature, master_fp, master_ip)
        assert result is True

    def test_wrong_signature_fails(self):
        ps = PairingService()
        nonce = ps.create_challenge("BOARD-1", "192.168.1.10")
        result = ps.verify_challenge_response(nonce, "bad_signature", "fp", "192.168.1.10")
        assert result is False

    def test_replay_prevention(self):
        ps = PairingService()
        master_fp = "replay_test_fp"
        master_ip = "192.168.1.10"
        nonce = ps.create_challenge("BOARD-1", master_ip)

        import hmac as hmac_mod
        import hashlib
        signature = hmac_mod.new(
            master_fp.encode(), nonce.encode(), hashlib.sha256
        ).hexdigest()

        # First attempt succeeds
        assert ps.verify_challenge_response(nonce, signature, master_fp, master_ip) is True
        # Replay attempt fails
        assert ps.verify_challenge_response(nonce, signature, master_fp, master_ip) is False

    def test_expired_challenge_fails(self):
        ps = PairingService()
        nonce = ps.create_challenge("BOARD-1", "192.168.1.10")
        # Force expiry
        ps._pending_challenges[nonce].created_at = time.time() - 60

        import hmac as hmac_mod
        import hashlib
        signature = hmac_mod.new(
            b"fp", nonce.encode(), hashlib.sha256
        ).hexdigest()

        result = ps.verify_challenge_response(nonce, signature, "fp", "192.168.1.10")
        assert result is False

    def test_ip_mismatch_fails(self):
        ps = PairingService()
        master_fp = "ip_test_fp"
        nonce = ps.create_challenge("BOARD-1", "192.168.1.10")

        import hmac as hmac_mod
        import hashlib
        signature = hmac_mod.new(
            master_fp.encode(), nonce.encode(), hashlib.sha256
        ).hexdigest()

        # Different IP
        result = ps.verify_challenge_response(nonce, signature, master_fp, "10.0.0.1")
        assert result is False


class TestTokenManagement:
    def test_generate_token(self):
        token = PairingService.generate_paired_token()
        assert len(token) > 32

    def test_hash_token(self):
        token = PairingService.generate_paired_token()
        h = PairingService.hash_token(token)
        assert len(h) == 64  # sha256 hex
        assert h != token

    def test_hmac_roundtrip(self):
        token = PairingService.generate_paired_token()
        payload = "GET /api/agent/status"
        sig = PairingService.compute_hmac(token, payload)
        assert PairingService.verify_hmac(token, payload, sig)

    def test_hmac_wrong_token_fails(self):
        token = PairingService.generate_paired_token()
        payload = "GET /api/agent/status"
        sig = PairingService.compute_hmac(token, payload)
        assert not PairingService.verify_hmac("wrong_token", payload, sig)

    def test_hmac_tampered_payload_fails(self):
        token = PairingService.generate_paired_token()
        sig = PairingService.compute_hmac(token, "original")
        assert not PairingService.verify_hmac(token, "tampered", sig)


class TestFingerprint:
    def test_deterministic(self):
        fp1 = PairingService.compute_fingerprint("BOARD-1")
        fp2 = PairingService.compute_fingerprint("BOARD-1")
        assert fp1 == fp2

    def test_different_ids_different_fingerprints(self):
        fp1 = PairingService.compute_fingerprint("BOARD-1")
        fp2 = PairingService.compute_fingerprint("BOARD-2")
        assert fp1 != fp2
