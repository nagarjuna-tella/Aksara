"""Regression coverage for v0.7.2 configuration parsing repairs."""

from __future__ import annotations

import pytest

from aksara.conf import Settings, _split_list_env


@pytest.mark.parametrize(
    ("raw", "expected"),
    [
        ("", []),
        ("example.com", ["example.com"]),
        ("https://example.com", ["https://example.com"]),
        ("https://example.com:8443", ["https://example.com:8443"]),
        ("example.com:8443", ["example.com:8443"]),
        ("192.0.2.1", ["192.0.2.1"]),
        ("2001:db8::1", ["2001:db8::1"]),
        ("[2001:db8::1]:8443", ["[2001:db8::1]:8443"]),
        (" one.example , two.example ", ["one.example", "two.example"]),
        (
            '["https://one.example:8443", "[2001:db8::1]:9443"]',
            ["https://one.example:8443", "[2001:db8::1]:9443"],
        ),
        ("one.example;two.example", ["one.example;two.example"]),
    ],
)
def test_list_environment_parser_has_platform_independent_grammar(raw, expected):
    assert _split_list_env(raw) == expected


@pytest.mark.parametrize(
    "raw",
    ["one.example,,two.example", "[not-json", '["valid", 42]', '["valid", " "]'],
)
def test_list_environment_parser_rejects_malformed_or_ambiguous_input(raw):
    with pytest.raises(ValueError, match="list-valued environment variable"):
        _split_list_env(raw)


def test_mcp_environment_lists_preserve_urls_and_ports(monkeypatch):
    monkeypatch.setenv(
        "AKSARA_MCP_ALLOWED_ORIGINS",
        "https://example.com, https://example.com:8443",
    )
    monkeypatch.setenv(
        "AKSARA_MCP_ALLOWED_HOSTS",
        '["api.example.com:443", "[2001:db8::1]:8443"]',
    )

    configured = Settings()

    assert configured.mcp_allowed_origins == [
        "https://example.com",
        "https://example.com:8443",
    ]
    assert configured.mcp_allowed_hosts == [
        "api.example.com:443",
        "[2001:db8::1]:8443",
    ]


def test_explicit_python_list_configuration_is_unchanged(monkeypatch):
    monkeypatch.delenv("AKSARA_MCP_ALLOWED_ORIGINS", raising=False)

    configured = Settings(mcp_allowed_origins=["https://app.example.com"])

    assert configured.mcp_allowed_origins == ["https://app.example.com"]


def test_explicit_empty_environment_list_is_preserved(monkeypatch):
    monkeypatch.setenv("AKSARA_MCP_ALLOWED_ORIGINS", "")
    monkeypatch.setenv("AKSARA_MCP_ALLOWED_HOSTS", "   ")

    configured = Settings()

    assert configured.mcp_allowed_origins == []
    assert configured.mcp_allowed_hosts == []
