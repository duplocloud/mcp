"""Tests for search mode tool registration.

Search mode registers the same underlying tools as expanded mode but applies
a BM25SearchTransform so the LLM sees search_tools + call_tool instead of
the full catalog.

Tests verify:
- search mode applies the BM25 transform (list_tools returns search_tools/call_tool)
- config and docs-prefix tools are pinned (always visible)
- compact mode custom tools are NOT registered in search mode
- search_tools meta-tool can find real tools by natural-language query
- call_tool proxy dispatches to real duploctl wrappers
- validate flag is False in search mode (matches expanded, not compact)
- mode config table drives registration correctly for all three modes
"""

import asyncio
import re
from unittest.mock import MagicMock, patch

import pytest
from fastmcp import FastMCP
from fastmcp.client import Client
from pydantic import BaseModel

from duplocloud.mcp.server import DuploCloudMCP, _EXCLUDED_RESOURCES
from duplocloud.mcp.ctx import _tool_registry, _route_registry
from duplocloud.mcp.tools import ToolRegistrar


# ---------------------------------------------------------------------------
# Helpers shared with test_modes.py
# ---------------------------------------------------------------------------

class FakeModel(BaseModel):
    plan_id: str | None = None
    account_name: str | None = None


TENANT_COMMANDS = {
    "list": {"class": "DuploTenant", "method": "list", "aliases": ["ls"], "model": None},
    "find": {"class": "DuploTenant", "method": "find", "aliases": [], "model": None},
    "create": {"class": "DuploTenant", "method": "create", "aliases": [], "model": "AddTenantRequest"},
}

SERVICE_COMMANDS = {
    "list": {"class": "DuploService", "method": "list", "aliases": [], "model": None},
}


def _make_fake_methods():
    def fake_list():
        """list tenants"""
        return []

    def fake_find(name=""):
        """find tenant"""
        return {"Name": name}

    def fake_create(body=None):
        """create tenant"""
        return {"ok": True}

    return {"list": fake_list, "find": fake_find, "create": fake_create}


def _make_mock_duplo():
    duplo = MagicMock()
    methods = _make_fake_methods()
    resource = MagicMock()
    for name, fn in methods.items():
        setattr(resource, name, fn)
    duplo.load.return_value = resource
    duplo.load_model.side_effect = lambda name: FakeModel if name == "AddTenantRequest" else None
    duplo.validate_model.side_effect = lambda model, data: model().model_dump()
    duplo.config = {"Host": "https://test.duplocloud.net", "Tenant": "default"}
    return duplo


def _make_server(mcp, mock_duplo, tool_mode="search"):
    server = DuploCloudMCP(mock_duplo)
    server.mcp = mcp
    server.tool_mode = tool_mode
    return server


def _tool_names_sync(mcp):
    return {t.name for t in asyncio.run(mcp.list_tools())}


@pytest.fixture(autouse=True)
def clean_registries():
    _tool_registry.clear()
    _route_registry.clear()
    yield
    _tool_registry.clear()
    _route_registry.clear()


@pytest.fixture
def mock_duplo():
    return _make_mock_duplo()


# ---------------------------------------------------------------------------
# Search mode: transform is applied
# ---------------------------------------------------------------------------

class TestSearchModeTransformApplied:
    """Search mode must replace the full catalog with search meta-tools."""

    def test_list_tools_returns_search_tools_not_catalog(self, mcp_instance, mock_duplo):
        """In search mode, BM25SearchTransform is instantiated and added via add_transform."""
        server = _make_server(mcp_instance, mock_duplo, tool_mode="search")

        added_transforms = []
        original_add = mcp_instance.add_transform
        mcp_instance.add_transform = lambda t: added_transforms.append(t)

        with patch("duplocloud.mcp.server.ToolRegistrar"), \
             patch("duplocloud.mcp.server.BM25SearchTransform") as MockTransform:
            server.register_tools(["tenant"])

        mcp_instance.add_transform = original_add

        # BM25SearchTransform must be instantiated
        MockTransform.assert_called_once()
        # The transform instance must have been passed to add_transform
        assert added_transforms == [MockTransform.return_value]

    def test_search_mode_uses_registrar(self, mcp_instance, mock_duplo):
        """Search mode creates a ToolRegistrar (same as expanded)."""
        server = _make_server(mcp_instance, mock_duplo, tool_mode="search")

        with patch("duplocloud.mcp.server.ToolRegistrar") as MockRegistrar, \
             patch("duplocloud.mcp.server.BM25SearchTransform"), \
             patch.object(server, "register_custom"):
            server.register_tools(["tenant"])

        MockRegistrar.assert_called_once()
        MockRegistrar.return_value.register.assert_called_once_with(["tenant"])

    def test_expanded_mode_no_transform(self, mcp_instance, mock_duplo):
        """Expanded mode does not add a BM25SearchTransform."""
        server = _make_server(mcp_instance, mock_duplo, tool_mode="expanded")

        with patch("duplocloud.mcp.server.ToolRegistrar"), \
             patch("duplocloud.mcp.server.BM25SearchTransform") as MockTransform, \
             patch.object(server, "register_custom"):
            server.register_tools(["tenant"])

        MockTransform.assert_not_called()

    def test_compact_mode_no_registrar_no_transform(self, mcp_instance, mock_duplo):
        """Compact mode uses neither ToolRegistrar nor BM25SearchTransform."""
        server = _make_server(mcp_instance, mock_duplo, tool_mode="compact")

        with patch("duplocloud.mcp.server.ToolRegistrar") as MockRegistrar, \
             patch("duplocloud.mcp.server.BM25SearchTransform") as MockTransform, \
             patch.object(server, "register_custom"):
            server.register_tools(["tenant"])

        MockRegistrar.assert_not_called()
        MockTransform.assert_not_called()


# ---------------------------------------------------------------------------
# Search mode: actual BM25 integration (no mocking of BM25)
# ---------------------------------------------------------------------------

class TestSearchModeIntegration:
    """End-to-end: register real tools, apply BM25, verify search behavior."""

    def _register_with_real_bm25(self, mock_duplo):
        """Register tenant tools under search mode with the real BM25 transform."""
        mcp = FastMCP(name="test-search", version="0.0.0")
        server = _make_server(mcp, mock_duplo, tool_mode="search")

        with patch("duplocloud.mcp.tools.commands_for") as mock_cmds, \
             patch("duplocloud.mcp.tools.extract_args") as mock_args:
            # tenant resource: list + find (no body args needed for basic search test)
            def commands_for_stub(name):
                if name == "tenant":
                    return TENANT_COMMANDS
                return {}

            def extract_args_stub(method):
                doc = getattr(method, "__doc__", "")
                if "find" in doc:
                    from tests.test_modes import FakeArg
                    return [FakeArg("name", str)]
                return []

            mock_cmds.side_effect = commands_for_stub
            mock_args.side_effect = extract_args_stub
            server.register_tools(["tenant"])

        return mcp

    async def test_list_tools_shows_search_and_call_not_catalog(self, mock_duplo):
        """After search mode setup, list_tools returns only search meta-tools + pinned."""
        mcp = self._register_with_real_bm25(mock_duplo)

        async with Client(transport=mcp) as client:
            tools = await client.list_tools()
            names = {t.name for t in tools}

        # Must have search and call meta-tools
        assert "search_tools" in names
        assert "call_tool" in names
        # Expanded catalog tools must NOT be listed
        assert "tenant_list" not in names
        assert "tenant_find" not in names
        assert "tenant_create" not in names

    async def test_search_tools_finds_tenant_tools(self, mock_duplo):
        """search_tools returns relevant tenant tools for a 'tenant' query."""
        mcp = self._register_with_real_bm25(mock_duplo)

        async with Client(transport=mcp) as client:
            result = await client.call_tool("search_tools", {"query": "tenant"})

        # Result should mention tenant tools
        result_text = str(result)
        assert "tenant" in result_text.lower()

    async def test_call_tool_dispatches_to_real_tool(self, mock_duplo):
        """call_tool can invoke a registered tool by name."""
        mcp = self._register_with_real_bm25(mock_duplo)

        async with Client(transport=mcp) as client:
            result = await client.call_tool("call_tool", {
                "name": "tenant_list",
                "arguments": {}
            })

        # The real fake_list returns [] which should be serialized
        assert result is not None


# ---------------------------------------------------------------------------
# Search mode: pinned tools always visible
# ---------------------------------------------------------------------------

class TestSearchModePinnedTools:
    """config tool must be pinned (always_visible) in search mode."""

    def test_bm25_configured_with_config_always_visible(self, mcp_instance, mock_duplo):
        """BM25SearchTransform is instantiated with 'config' in always_visible."""
        server = _make_server(mcp_instance, mock_duplo, tool_mode="search")

        with patch("duplocloud.mcp.server.ToolRegistrar"), \
             patch("duplocloud.mcp.server.BM25SearchTransform") as MockTransform, \
             patch.object(server, "register_custom"):
            server.register_tools(["tenant"])

        call_kwargs = MockTransform.call_args
        always_visible = call_kwargs.kwargs.get("always_visible") or (
            call_kwargs.args[0] if call_kwargs.args else []
        )
        assert "config" in always_visible

    def test_bm25_configured_with_max_results(self, mcp_instance, mock_duplo):
        """BM25SearchTransform is instantiated with max_results=7."""
        server = _make_server(mcp_instance, mock_duplo, tool_mode="search")

        with patch("duplocloud.mcp.server.ToolRegistrar"), \
             patch("duplocloud.mcp.server.BM25SearchTransform") as MockTransform, \
             patch.object(server, "register_custom"):
            server.register_tools(["tenant"])

        call_kwargs = MockTransform.call_args
        max_results = call_kwargs.kwargs.get("max_results")
        assert max_results == 7


# ---------------------------------------------------------------------------
# Search mode: compact tools excluded
# ---------------------------------------------------------------------------

class TestSearchModeCompactToolsExcluded:
    """Compact custom tools must NOT be registered in search mode."""

    def test_compact_tools_not_in_search_mode(self, mcp_instance, mock_duplo):
        """In search mode, resources/explain_resource/explain_command/execute are absent."""
        server = _make_server(mcp_instance, mock_duplo, tool_mode="search")

        with patch("duplocloud.mcp.server.ToolRegistrar"), \
             patch("duplocloud.mcp.server.BM25SearchTransform"):
            # Re-import compact_tools module to trigger @custom_tool decorators
            # but the mode filter means they won't register for search mode
            from duplocloud.mcp.ctx import _tool_registry as reg
            # Manually add a compact-mode entry to test filtering
            reg.append({"fn": lambda ctx: None, "name": "resources", "description": "", "mode": "compact"})
            reg.append({"fn": lambda ctx: None, "name": "execute", "description": "", "mode": "compact"})
            server.register_custom(mode="search")

        names = _tool_names_sync(mcp_instance)
        assert "resources" not in names
        assert "execute" not in names


# ---------------------------------------------------------------------------
# Validate flag
# ---------------------------------------------------------------------------

class TestValidateFlag:
    """duplo.validate must be False for search mode (same as expanded, not compact)."""

    def test_validate_false_in_search_mode(self, mock_duplo):
        """Search mode: duplo.validate is False."""
        server = DuploCloudMCP(mock_duplo)

        with patch.object(server, "register_tools"), \
             patch.object(server, "_start_transport"), \
             patch("duplocloud.mcp.server.mount_docs"):
            server.start(
                transport="stdio",
                port=8000,
                resource_filter=".*",
                command_filter=".*",
                tool_mode="search",
                docs=False,
            )

        assert mock_duplo.validate is False

    def test_validate_false_in_expanded_mode(self, mock_duplo):
        """Expanded mode: duplo.validate is False."""
        server = DuploCloudMCP(mock_duplo)

        with patch.object(server, "register_tools"), \
             patch.object(server, "_start_transport"), \
             patch("duplocloud.mcp.server.mount_docs"):
            server.start(
                transport="stdio",
                port=8000,
                resource_filter=".*",
                command_filter=".*",
                tool_mode="expanded",
                docs=False,
            )

        assert mock_duplo.validate is False

    def test_validate_true_in_compact_mode(self, mock_duplo):
        """Compact mode: duplo.validate is True."""
        server = DuploCloudMCP(mock_duplo)

        with patch.object(server, "register_tools"), \
             patch.object(server, "_start_transport"), \
             patch("duplocloud.mcp.server.mount_docs"):
            server.start(
                transport="stdio",
                port=8000,
                resource_filter=".*",
                command_filter=".*",
                tool_mode="compact",
                docs=False,
            )

        assert mock_duplo.validate is True


# ---------------------------------------------------------------------------
# Mode config table drives registration (Phase 2)
# ---------------------------------------------------------------------------

class TestModeConfig:
    """The mode config table must express correct properties for all modes."""

    def test_mode_config_exists(self):
        """A MODE_CONFIG mapping is importable from server."""
        from duplocloud.mcp.server import MODE_CONFIG
        assert "expanded" in MODE_CONFIG
        assert "compact" in MODE_CONFIG
        assert "search" in MODE_CONFIG

    def test_expanded_uses_registrar_no_transform(self):
        from duplocloud.mcp.server import MODE_CONFIG
        cfg = MODE_CONFIG["expanded"]
        assert cfg["use_registrar"] is True
        assert cfg["transform"] is None

    def test_compact_no_registrar_no_transform(self):
        from duplocloud.mcp.server import MODE_CONFIG
        cfg = MODE_CONFIG["compact"]
        assert cfg["use_registrar"] is False
        assert cfg["transform"] is None

    def test_search_uses_registrar_has_transform_factory(self):
        from duplocloud.mcp.server import MODE_CONFIG
        cfg = MODE_CONFIG["search"]
        assert cfg["use_registrar"] is True
        assert cfg["transform"] is not None  # factory or class

    def test_search_validate_false(self):
        from duplocloud.mcp.server import MODE_CONFIG
        assert MODE_CONFIG["search"].get("validate", True) is False

    def test_compact_validate_true(self):
        from duplocloud.mcp.server import MODE_CONFIG
        assert MODE_CONFIG["compact"].get("validate", False) is True

    def test_expanded_validate_false(self):
        from duplocloud.mcp.server import MODE_CONFIG
        assert MODE_CONFIG["expanded"].get("validate", True) is False
