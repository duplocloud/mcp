"""Tests for DuploCloudMCP server coordinator."""

import re
from unittest.mock import MagicMock, patch

import pytest
from fastmcp import FastMCP

from duplocloud.mcp.server import DuploCloudMCP, _EXCLUDED_RESOURCES


@pytest.fixture
def mock_duplo():
    duplo = MagicMock()
    duplo.config = {"Host": "https://test.duplocloud.net", "Tenant": "default"}
    return duplo


@pytest.fixture
def mcp_server(mcp_instance, mock_duplo):
    """A DuploCloudMCP with an injected test FastMCP instance and default filters."""
    server = DuploCloudMCP(mock_duplo)
    server.mcp = mcp_instance
    return server


class TestInit:
    """Tests for DuploCloudMCP.__init__."""

    def test_duplo_injected(self, mock_duplo):
        server = DuploCloudMCP(mock_duplo)
        assert server.duplo is mock_duplo

    def test_default_filters(self, mock_duplo):
        server = DuploCloudMCP(mock_duplo)
        assert server.resource_filter.pattern == ".*"
        assert server.command_filter.pattern == ".*"

    def test_default_transport(self, mock_duplo):
        server = DuploCloudMCP(mock_duplo)
        assert server.transport == "stdio"
        assert server.port == 8000
        assert server.tool_mode == "compact"

    def test_mcp_initialized_to_app(self, mock_duplo):
        server = DuploCloudMCP(mock_duplo)
        assert server.mcp is not None


class TestRegisterTools:
    """Tests for resource filter application in register_tools."""

    def test_resource_filter_applied(self, mcp_instance, mock_duplo):
        """Only matching resources are passed to the registrar."""
        server = DuploCloudMCP(mock_duplo)
        server.mcp = mcp_instance
        server.tool_mode = "expanded"
        server.resource_filter = re.compile("tenant|service")

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
        mcp_server.tool_mode = "expanded"
        with patch("duplocloud.mcp.server.ToolRegistrar") as MockRegistrar:
            mock_registrar = MockRegistrar.return_value
            mcp_server.register_tools(["tenant", "service", "lambda"])

        registered = mock_registrar.register.call_args[0][0]
        assert sorted(registered) == ["lambda", "service", "tenant"]

    def test_discovers_all_resources_when_none(self, mcp_server):
        """When resource_names is None, discovers from available_resources."""
        mcp_server.tool_mode = "expanded"
        with patch("duplocloud.mcp.server.available_resources", return_value=["tenant", "service"]), \
             patch("duplocloud.mcp.server.ToolRegistrar") as MockRegistrar:
            mock_registrar = MockRegistrar.return_value
            mcp_server.register_tools()

        registered = mock_registrar.register.call_args[0][0]
        assert "tenant" in registered
        assert "service" in registered

    def test_command_filter_passed_to_registrar(self, mcp_instance, mock_duplo):
        """The command filter regex is passed to ToolRegistrar."""
        server = DuploCloudMCP(mock_duplo)
        server.mcp = mcp_instance
        server.tool_mode = "expanded"
        server.command_filter = re.compile("create|find")

        with patch("duplocloud.mcp.server.ToolRegistrar") as MockRegistrar:
            server.register_tools(["tenant"])

        # Check that ToolRegistrar was constructed with the right command filter
        init_args = MockRegistrar.call_args
        command_filter = init_args[0][2]  # 3rd positional arg
        assert command_filter.pattern == "create|find"


class TestSelfExclusion:
    """Tests that the MCP server excludes itself from tool registration."""

    def test_mcp_excluded_from_resource_list(self, mcp_instance, mock_duplo):
        """When 'mcp' appears in available_resources, it is excluded."""
        server = DuploCloudMCP(mock_duplo)
        server.mcp = mcp_instance
        server.tool_mode = "expanded"

        with patch("duplocloud.mcp.server.ToolRegistrar") as MockRegistrar:
            mock_registrar = MockRegistrar.return_value
            server.register_tools(["tenant", "service", "mcp"])

        registered = mock_registrar.register.call_args[0][0]
        assert "mcp" not in registered
        assert "tenant" in registered
        assert "service" in registered

    def test_mcp_not_in_filtered_resources(self, mcp_instance, mock_duplo):
        """'mcp' should not appear in _filtered_resources even with '.*' filter."""
        server = DuploCloudMCP(mock_duplo)
        server.mcp = mcp_instance

        with patch("duplocloud.mcp.server.ToolRegistrar"):
            server.register_tools(["tenant", "mcp"])

        assert "mcp" not in server._filtered_resources
        assert "tenant" in server._filtered_resources

    def test_excluded_resources_constant(self):
        """The exclusion set contains 'mcp'."""
        assert "mcp" in _EXCLUDED_RESOURCES

    def test_mcp_excluded_in_compact_mode(self, mcp_instance, mock_duplo):
        """Compact mode also excludes 'mcp' from resources."""
        server = DuploCloudMCP(mock_duplo)
        server.mcp = mcp_instance
        server.tool_mode = "compact"

        server.register_tools(["tenant", "mcp"])

        assert "mcp" not in server._filtered_resources
