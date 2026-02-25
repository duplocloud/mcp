"""Tests for DuploCloudMCP server coordinator."""

import re
from unittest.mock import MagicMock, patch

import pytest
from fastmcp import FastMCP

from duplocloud.mcp.server import DuploCloudMCP


@pytest.fixture
def mock_duplo():
    duplo = MagicMock()
    duplo.config = {"Host": "https://test.duplocloud.net", "Tenant": "default"}
    return duplo


@pytest.fixture
def mcp_server(mcp_instance, mock_duplo):
    return DuploCloudMCP(
        mcp=mcp_instance,
        duplo=mock_duplo,
        transport="http",
        port=8000,
        resource_filter=".*",
        command_filter=".*",
    )


class TestInit:
    """Tests for DuploCloudMCP.__init__."""

    def test_default_filters(self, mcp_instance, mock_duplo):
        server = DuploCloudMCP(mcp=mcp_instance, duplo=mock_duplo)
        assert server.resource_filter.pattern == ".*"
        assert server.command_filter.pattern == ".*"

    def test_custom_filters(self, mcp_instance, mock_duplo):
        server = DuploCloudMCP(
            mcp=mcp_instance,
            duplo=mock_duplo,
            resource_filter="tenant|service",
            command_filter="create|find",
        )
        assert server.resource_filter.pattern == "tenant|service"
        assert server.command_filter.pattern == "create|find"

    def test_filters_are_compiled(self, mcp_instance, mock_duplo):
        server = DuploCloudMCP(
            mcp=mcp_instance,
            duplo=mock_duplo,
            resource_filter="tenant",
        )
        assert isinstance(server.resource_filter, re.Pattern)
        assert server.resource_filter.fullmatch("tenant")
        assert not server.resource_filter.fullmatch("service")


class TestRegisterTools:
    """Tests for resource filter application in register_tools."""

    def test_resource_filter_applied(self, mcp_instance, mock_duplo):
        """Only matching resources are passed to the registrar."""
        server = DuploCloudMCP(
            mcp=mcp_instance,
            duplo=mock_duplo,
            resource_filter="tenant|service",
        )

        with patch("duplocloud.mcp.server.ToolRegistrar") as MockRegistrar:
            mock_registrar = MockRegistrar.return_value
            server.register_tools(["tenant", "service", "lambda", "hosts"])

        # Registrar should only get the filtered names
        mock_registrar.register.assert_called_once()
        registered = mock_registrar.register.call_args[0][0]
        assert "tenant" in registered
        assert "service" in registered
        assert "lambda" not in registered
        assert "hosts" not in registered

    def test_default_filter_passes_all(self, mcp_server):
        """Default .* filter passes all resources."""
        with patch("duplocloud.mcp.server.ToolRegistrar") as MockRegistrar:
            mock_registrar = MockRegistrar.return_value
            mcp_server.register_tools(["tenant", "service", "lambda"])

        registered = mock_registrar.register.call_args[0][0]
        assert registered == ["tenant", "service", "lambda"]

    def test_discovers_all_resources_when_none(self, mcp_server):
        """When resource_names is None, discovers from available_resources."""
        with patch("duplocloud.mcp.server.available_resources", return_value=["tenant", "service"]), \
             patch("duplocloud.mcp.server.ToolRegistrar") as MockRegistrar:
            mock_registrar = MockRegistrar.return_value
            mcp_server.register_tools()

        registered = mock_registrar.register.call_args[0][0]
        assert "tenant" in registered
        assert "service" in registered

    def test_command_filter_passed_to_registrar(self, mcp_instance, mock_duplo):
        """The command filter regex is passed to ToolRegistrar."""
        server = DuploCloudMCP(
            mcp=mcp_instance,
            duplo=mock_duplo,
            command_filter="create|find",
        )

        with patch("duplocloud.mcp.server.ToolRegistrar") as MockRegistrar:
            server.register_tools(["tenant"])

        # Check that ToolRegistrar was constructed with the right command filter
        init_args = MockRegistrar.call_args
        command_filter = init_args[0][2]  # 3rd positional arg
        assert command_filter.pattern == "create|find"


class TestFromArgs:
    """Tests for DuploCloudMCP.from_args."""

    def test_from_args_with_defaults(self):
        mock_duplo = MagicMock()
        with patch("duplocloud.mcp.server.DuploClient") as MockClient, \
             patch("duplocloud.mcp.server.mcp_app"):
            MockClient.from_env.return_value = (mock_duplo, [])
            server = DuploCloudMCP.from_args([])

        assert server.transport == "http"
        assert server.port == 8000
        assert server.resource_filter.pattern == ".*"
        assert server.command_filter.pattern == ".*"

    def test_from_args_with_custom_args(self):
        mock_duplo = MagicMock()
        with patch("duplocloud.mcp.server.DuploClient") as MockClient, \
             patch("duplocloud.mcp.server.mcp_app"):
            MockClient.from_env.return_value = (mock_duplo, [])
            server = DuploCloudMCP.from_args([
                "--transport", "stdio",
                "--resource-filter", "service",
                "--command-filter", "create|find",
            ])

        assert server.transport == "stdio"
        assert server.resource_filter.pattern == "service"
        assert server.command_filter.pattern == "create|find"
