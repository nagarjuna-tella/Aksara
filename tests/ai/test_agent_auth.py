"""
Tests for aksara.ai.auth — HMAC-based agent token signing and verification.
"""

from __future__ import annotations

import time

import pytest

from aksara.ai.auth import sign_agent_token, verify_agent_token


class TestSignAgentToken:
    def test_import(self):
        assert callable(sign_agent_token)
        assert callable(verify_agent_token)

    def test_returns_three_part_string(self):
        token = sign_agent_token("agent-1", "secret")
        parts = token.split(".")
        assert len(parts) == 3

    def test_empty_agent_id_raises(self):
        with pytest.raises(ValueError, match="agent_id"):
            sign_agent_token("", "secret")

    def test_empty_secret_raises(self):
        with pytest.raises(ValueError, match="secret"):
            sign_agent_token("agent-1", "")


class TestVerifyAgentToken:
    def test_round_trip(self):
        token = sign_agent_token("agent-1", "secret")
        payload = verify_agent_token(token, "secret")
        assert payload["agent_id"] == "agent-1"

    def test_wrong_secret_raises(self):
        token = sign_agent_token("agent-1", "right-secret")
        with pytest.raises(ValueError, match="signature"):
            verify_agent_token(token, "wrong-secret")

    def test_tampered_payload_raises(self):
        import base64
        token = sign_agent_token("agent-1", "secret")
        header, body, sig = token.split(".")
        # Tamper: flip first byte of body
        raw = base64.urlsafe_b64decode(body + "==")
        tampered = bytes([raw[0] ^ 0xFF]) + raw[1:]
        bad_body = base64.urlsafe_b64encode(tampered).rstrip(b"=").decode()
        bad_token = f"{header}.{bad_body}.{sig}"
        with pytest.raises(ValueError):
            verify_agent_token(bad_token, "secret")

    def test_extra_claims_preserved(self):
        token = sign_agent_token("agent-1", "secret", extra={"scope": "read"})
        payload = verify_agent_token(token, "secret")
        assert payload["scope"] == "read"

    def test_expired_token_raises(self):
        # Issue a token that expired 10 seconds ago
        token = sign_agent_token("agent-1", "secret", ttl_seconds=-10)
        with pytest.raises(ValueError, match="expired"):
            verify_agent_token(token, "secret")

    def test_clock_skew_tolerance(self):
        # Tight TTL but with enough skew tolerance
        token = sign_agent_token("agent-1", "secret", ttl_seconds=-5)
        payload = verify_agent_token(token, "secret", clock_skew_seconds=10)
        assert payload["agent_id"] == "agent-1"

    def test_invalid_format_raises(self):
        with pytest.raises(ValueError, match="format"):
            verify_agent_token("not-a-real-token", "secret")

    def test_empty_secret_raises(self):
        token = sign_agent_token("agent-1", "secret")
        with pytest.raises(ValueError, match="secret"):
            verify_agent_token(token, "")

    def test_iat_and_exp_present(self):
        before = int(time.time())
        token = sign_agent_token("agent-1", "secret", ttl_seconds=60)
        after = int(time.time())
        payload = verify_agent_token(token, "secret")
        assert payload["iat"] >= before
        assert payload["iat"] <= after
        assert payload["exp"] == payload["iat"] + 60
