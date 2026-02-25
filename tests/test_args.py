"""Tests for MCP argument definitions and parser construction."""

import os

import pytest

from duplocloud.mcp.args import ARGUMENTS, build_parser, _resolve_env_default


class TestArgumentDefinitions:
    """Verify argument definition structure and defaults."""

    def test_transport_default(self):
        parser = build_parser()
        parsed = parser.parse_args([])
        assert parsed.transport == "http"

    def test_port_default(self):
        parser = build_parser()
        parsed = parser.parse_args([])
        assert parsed.port == 8000

    def test_resource_filter_default(self):
        parser = build_parser()
        parsed = parser.parse_args([])
        assert parsed.resource_filter == ".*"

    def test_command_filter_default(self):
        parser = build_parser()
        parsed = parser.parse_args([])
        assert parsed.command_filter == ".*"


class TestParserConstruction:
    """Verify the parser accepts valid args and rejects invalid ones."""

    def test_valid_transport_stdio(self):
        parser = build_parser()
        parsed = parser.parse_args(["--transport", "stdio"])
        assert parsed.transport == "stdio"

    def test_valid_transport_http(self):
        parser = build_parser()
        parsed = parser.parse_args(["--transport", "http"])
        assert parsed.transport == "http"

    def test_invalid_transport_rejected(self):
        parser = build_parser()
        with pytest.raises(SystemExit):
            parser.parse_args(["--transport", "grpc"])

    def test_custom_port(self):
        parser = build_parser()
        parsed = parser.parse_args(["--port", "9090"])
        assert parsed.port == 9090

    def test_custom_filters(self):
        parser = build_parser()
        parsed = parser.parse_args([
            "--resource-filter", "tenant|service",
            "--command-filter", "create|find",
        ])
        assert parsed.resource_filter == "tenant|service"
        assert parsed.command_filter == "create|find"


class TestEnvVarBinding:
    """Verify environment variable defaults are picked up."""

    def test_transport_env(self, monkeypatch):
        monkeypatch.setenv("DUPLO_MCP_TRANSPORT", "stdio")
        parser = build_parser()
        parsed = parser.parse_args([])
        assert parsed.transport == "stdio"

    def test_port_primary_env(self, monkeypatch):
        monkeypatch.setenv("DUPLO_MCP_PORT", "3000")
        parser = build_parser()
        parsed = parser.parse_args([])
        assert parsed.port == 3000

    def test_port_fallback_env(self, monkeypatch):
        monkeypatch.setenv("PORT", "4000")
        parser = build_parser()
        parsed = parser.parse_args([])
        assert parsed.port == 4000

    def test_port_primary_beats_fallback(self, monkeypatch):
        monkeypatch.setenv("DUPLO_MCP_PORT", "3000")
        monkeypatch.setenv("PORT", "4000")
        parser = build_parser()
        parsed = parser.parse_args([])
        assert parsed.port == 3000

    def test_resource_filter_env(self, monkeypatch):
        monkeypatch.setenv("DUPLO_MCP_RESOURCE_FILTER", "tenant")
        parser = build_parser()
        parsed = parser.parse_args([])
        assert parsed.resource_filter == "tenant"

    def test_command_filter_env(self, monkeypatch):
        monkeypatch.setenv("DUPLO_MCP_COMMAND_FILTER", "list|find")
        parser = build_parser()
        parsed = parser.parse_args([])
        assert parsed.command_filter == "list|find"

    def test_cli_overrides_env(self, monkeypatch):
        monkeypatch.setenv("DUPLO_MCP_TRANSPORT", "stdio")
        parser = build_parser()
        parsed = parser.parse_args(["--transport", "http"])
        assert parsed.transport == "http"
