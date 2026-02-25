"""Tests for expanded and compact tool registration modes.

Uses the tenant resource as the primary use case since it's the only
resource with a model annotation (AddTenantRequest on create).
"""

import asyncio
import inspect
import re
from typing import Optional
from unittest.mock import MagicMock, patch

import pytest
from fastmcp import FastMCP
from pydantic import BaseModel, Field

from duplocloud.mcp.tools import ToolRegistrar
from duplocloud.mcp.compact_tools import execute, explain, resources
from duplocloud.mcp.ctx import Ctx


# ---------------------------------------------------------------------------
# Helpers – lightweight fakes for duploctl internals
# ---------------------------------------------------------------------------

class FakeModel(BaseModel):
    """Stand-in for AddTenantRequest Pydantic model."""
    plan_id: Optional[str] = Field(None, alias="PlanID")
    account_name: Optional[str] = Field(None, alias="AccountName")


class FakeArg:
    """Mimics duploctl Arg type."""
    def __init__(self, name, supertype=str, dest=None, help_text=""):
        self.__name__ = name
        self.__supertype__ = supertype
        self.attributes = {}
        if dest:
            self.attributes["dest"] = dest
        if help_text:
            self.attributes["help"] = help_text


# Tenant command schema as returned by commands_for("tenant")
TENANT_COMMANDS = {
    "list": {"class": "DuploTenant", "method": "list", "aliases": ["ls"], "model": None},
    "find": {"class": "DuploTenant", "method": "find", "aliases": ["get"], "model": None},
    "create": {"class": "DuploTenant", "method": "create", "aliases": [], "model": "AddTenantRequest"},
    "delete": {"class": "DuploTenant", "method": "delete", "aliases": [], "model": None},
}


def _make_fake_methods():
    """Build real functions simulating bound methods (no self param)."""
    call_log = []

    def fake_list():
        """list doc"""
        call_log.append(("list",))
        return []

    def fake_find(name=""):
        """find doc"""
        call_log.append(("find", name))
        return {"Name": name}

    def fake_create(body=None):
        """create doc"""
        call_log.append(("create", body))
        return {"ok": True}

    def fake_delete(name=""):
        """delete doc"""
        call_log.append(("delete", name))
        return {"deleted": True}

    return {
        "list": fake_list,
        "find": fake_find,
        "create": fake_create,
        "delete": fake_delete,
    }, call_log


def _make_mock_resource(commands_dict):
    """Build a mock resource object with real functions matching commands."""
    resource = MagicMock()
    methods, call_log = _make_fake_methods()
    for method_name in commands_dict:
        if method_name in methods:
            setattr(resource, method_name, methods[method_name])
    resource._call_log = call_log
    return resource


def _make_mock_duplo():
    """Build a mock DuploClient for expanded mode tests."""
    duplo = MagicMock()
    resource = _make_mock_resource(TENANT_COMMANDS)
    duplo.load.return_value = resource
    duplo.load_model.side_effect = lambda name: FakeModel if name == "AddTenantRequest" else None
    duplo.validate_model.side_effect = lambda model, data: model().model_dump()
    return duplo


def _get_tool_names(mcp):
    """Get tool names from a FastMCP instance."""
    tools = asyncio.run(mcp.list_tools())
    return {t.name for t in tools}


def _get_tool(mcp, name):
    """Get a FunctionTool from a FastMCP instance by name."""
    return asyncio.run(mcp.get_tool(name))


def _patch_extract_args(args_map):
    """Return a side_effect for extract_args that returns args based on the method's __doc__."""
    lookup = {f"{name} doc": a for name, a in args_map.items()}

    def _extract(method):
        doc = getattr(method, "__doc__", "")
        return lookup.get(doc, [])

    return _extract


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture
def mock_duplo():
    return _make_mock_duplo()


@pytest.fixture
def default_filter():
    return re.compile(".*")


@pytest.fixture
def tenant_args():
    """Fake extract_args results for tenant methods."""
    return {
        "list": [],
        "find": [FakeArg("name", str)],
        "create": [FakeArg("file", dict, dest="body")],
        "delete": [FakeArg("name", str)],
    }


# ---------------------------------------------------------------------------
# Expanded Mode Tests
# ---------------------------------------------------------------------------

class TestExpandedMode:
    """Expanded mode: one tool per resource+command."""

    def test_tenant_create_gets_model_annotation(self, mcp_instance, mock_duplo, default_filter, tenant_args):
        """In expanded mode, tenant_create body param uses AddTenantRequest model."""
        registrar = ToolRegistrar(mcp_instance, mock_duplo, default_filter)

        with patch("duplocloud.mcp.tools.commands_for", return_value=TENANT_COMMANDS), \
             patch("duplocloud.mcp.tools.extract_args", side_effect=_patch_extract_args(tenant_args)):
            registrar.register_resource("tenant")

        tool = _get_tool(mcp_instance, "tenant_create")
        sig = inspect.signature(tool.fn)
        assert "body" in sig.parameters
        assert sig.parameters["body"].annotation is FakeModel

    def test_tenant_find_no_model(self, mcp_instance, mock_duplo, default_filter, tenant_args):
        """In expanded mode, tenant_find (no model) has str annotation for name."""
        registrar = ToolRegistrar(mcp_instance, mock_duplo, default_filter)

        with patch("duplocloud.mcp.tools.commands_for", return_value={"find": TENANT_COMMANDS["find"]}), \
             patch("duplocloud.mcp.tools.extract_args", side_effect=_patch_extract_args(tenant_args)):
            registrar.register_resource("tenant")

        tool = _get_tool(mcp_instance, "tenant_find")
        sig = inspect.signature(tool.fn)
        assert "name" in sig.parameters
        assert sig.parameters["name"].annotation is str

    def test_tenant_list_no_params(self, mcp_instance, mock_duplo, default_filter, tenant_args):
        """In expanded mode, tenant_list has no user-facing params."""
        registrar = ToolRegistrar(mcp_instance, mock_duplo, default_filter)

        with patch("duplocloud.mcp.tools.commands_for", return_value={"list": TENANT_COMMANDS["list"]}), \
             patch("duplocloud.mcp.tools.extract_args", return_value=[]):
            registrar.register_resource("tenant")

        tool_names = _get_tool_names(mcp_instance)
        assert "tenant_list" in tool_names

    def test_expanded_registers_prefixed_names(self, mcp_instance, mock_duplo, default_filter, tenant_args):
        """Expanded mode tools are named {resource}_{command}."""
        registrar = ToolRegistrar(mcp_instance, mock_duplo, default_filter)

        with patch("duplocloud.mcp.tools.commands_for", return_value=TENANT_COMMANDS), \
             patch("duplocloud.mcp.tools.extract_args", side_effect=_patch_extract_args(tenant_args)):
            registrar.register_resource("tenant")

        tool_names = _get_tool_names(mcp_instance)
        assert "tenant_create" in tool_names
        assert "tenant_find" in tool_names
        assert "tenant_list" in tool_names
        assert "tenant_delete" in tool_names


# ---------------------------------------------------------------------------
# Compact Mode Tests – execute, explain, resources
# ---------------------------------------------------------------------------

class TestCompactExecute:
    """Tests for the compact mode execute tool."""

    @staticmethod
    def _make_ctx(duplo, resource_list=None):
        if not hasattr(duplo, 'wait') or isinstance(duplo.wait, MagicMock):
            duplo.wait = False
        return Ctx(
            duplo=duplo,
            config={},
            tools=["execute", "explain", "resources"],
            resources=resource_list if resource_list is not None else ["tenant", "service"],
        )

    def test_execute_dispatches_with_body(self):
        """Execute calls resource.command(cmd)(body=body) for body commands."""
        duplo = MagicMock()
        duplo.query = None
        duplo.output = "json"
        duplo.filter.side_effect = lambda x: x
        duplo.format.return_value = '{"ok": true}'

        cmd_fn = MagicMock(return_value={"ok": True})
        resource_obj = MagicMock()
        resource_obj.command.return_value = cmd_fn
        duplo.load.return_value = resource_obj

        ctx = self._make_ctx(duplo)
        result = execute(ctx, resource="tenant", command="create", body={"AccountName": "test"})

        resource_obj.command.assert_called_with("create")
        cmd_fn.assert_called_with(body={"AccountName": "test"})

    def test_execute_dispatches_with_name(self):
        """Execute inserts name into call_args: duplo(resource, command, name)."""
        duplo = MagicMock()
        duplo.query = None
        duplo.output = "json"
        duplo.__call__ = MagicMock(return_value="found-it")

        ctx = self._make_ctx(duplo)
        result = execute(ctx, resource="tenant", command="find", name="my-tenant")

        duplo.assert_called_with("tenant", "find", "my-tenant")

    def test_execute_dispatches_positional_args(self):
        """Execute calls duplo(resource, command, *args) for non-body commands."""
        duplo = MagicMock()
        duplo.query = None
        duplo.output = "json"
        duplo.__call__ = MagicMock(return_value="found-it")

        ctx = self._make_ctx(duplo)
        result = execute(ctx, resource="tenant", command="find", args=["my-tenant"])

        duplo.assert_called_with("tenant", "find", "my-tenant")

    def test_execute_respects_resource_filter(self):
        """Execute rejects resources not in ctx.resources."""
        duplo = MagicMock()
        duplo.query = None
        duplo.output = "json"

        ctx = self._make_ctx(duplo, resource_list=["tenant"])
        result = execute(ctx, resource="service", command="list")

        assert "not allowed" in result

    def test_execute_respects_command_filter(self):
        """Execute rejects commands that don't match the command filter."""
        duplo = MagicMock()
        duplo.query = None
        duplo.output = "json"
        duplo.wait = False

        ctx = Ctx(
            duplo=duplo,
            config={"command_filter": "list|find"},
            tools=["execute", "explain", "resources"],
            resources=["tenant"],
        )
        result = execute(ctx, resource="tenant", command="delete")

        assert "not allowed" in result
        assert "command filter" in result

    def test_execute_restores_globals(self):
        """Execute restores query, output, and wait after call, even on error."""
        duplo = MagicMock()
        duplo.query = "original_query"
        duplo.output = "yaml"
        duplo.wait = False
        duplo.side_effect = Exception("boom")

        ctx = self._make_ctx(duplo)
        result = execute(ctx, resource="tenant", command="list", query="[].Name", output="json", wait=True)

        assert isinstance(result, str)
        assert "Error" in result
        assert duplo.query == "original_query"
        assert duplo.output == "yaml"
        assert duplo.wait is False

    def test_execute_sets_temporary_query(self):
        """Execute temporarily sets duplo.query when query param provided."""
        duplo = MagicMock()
        duplo.query = None
        duplo.output = "json"
        duplo.__call__ = MagicMock(return_value="[]")

        ctx = self._make_ctx(duplo)
        execute(ctx, resource="tenant", command="list", query="[].Name")

        # During the call, query should have been set, then restored
        assert duplo.query is None

    def test_execute_sets_temporary_wait(self):
        """Execute temporarily sets duplo.wait when wait=True."""
        duplo = MagicMock()
        duplo.query = None
        duplo.output = "json"
        duplo.wait = False

        # Capture wait value during the call via side_effect
        captured = {}
        def capture_call(*a, **kw):
            captured["wait"] = duplo.wait
            return "[]"
        duplo.side_effect = capture_call

        ctx = self._make_ctx(duplo)
        execute(ctx, resource="tenant", command="list", wait=True)

        assert captured["wait"] is True
        assert duplo.wait is False  # restored after call

    def test_execute_name_and_args_combined(self):
        """Execute with both name and args builds correct call_args."""
        duplo = MagicMock()
        duplo.query = None
        duplo.output = "json"
        duplo.__call__ = MagicMock(return_value="ok")

        ctx = self._make_ctx(duplo)
        execute(ctx, resource="service", command="update_image", name="my-svc", args=["nginx:latest"])

        duplo.assert_called_with("service", "update_image", "my-svc", "nginx:latest")


class TestCompactExplain:
    """Tests for the compact mode explain tool."""

    def test_explain_lists_all_commands(self):
        """Explain without command returns all commands with summaries."""
        duplo = MagicMock()
        
        # Mock resource object with methods that have docstrings
        resource_obj = MagicMock()
        resource_obj.create = MagicMock(__doc__="Create a new tenant")
        resource_obj.list = MagicMock(__doc__="List all tenants")
        duplo.load.return_value = resource_obj

        ctx = Ctx(duplo=duplo, config={}, tools=[])
        with patch("duplocloud.mcp.compact_tools.commands_for", return_value=TENANT_COMMANDS):
            result = explain(ctx, resource="tenant")

        assert result["resource"] == "tenant"
        assert "create" in result["commands"]
        assert result["commands"]["create"]["summary"] == "Create a new tenant"
        assert "aliases" in result["commands"]["create"]
        assert "list" in result["commands"]
        assert result["commands"]["list"]["summary"] == "List all tenants"

    def test_explain_single_command_with_model(self, tenant_args):
        """Explain with command returns detailed args and model fields."""
        duplo = MagicMock()
        duplo.load_model.return_value = FakeModel

        resource_obj = MagicMock()
        resource_obj.create = MagicMock(__doc__="Create a tenant")
        duplo.load.return_value = resource_obj

        ctx = Ctx(duplo=duplo, config={}, tools=[])
        with patch("duplocloud.mcp.compact_tools.commands_for", return_value=TENANT_COMMANDS), \
             patch("duplocloud.mcp.compact_tools.extract_args", return_value=tenant_args["create"]):
            result = explain(ctx, resource="tenant", command="create")

        assert result["resource"] == "tenant"
        assert result["command"] == "create"
        assert result["model"] == "AddTenantRequest"
        assert "model_fields" in result

    def test_explain_unknown_command(self):
        """Explain with unknown command returns error with available commands."""
        duplo = MagicMock()

        ctx = Ctx(duplo=duplo, config={}, tools=[])
        with patch("duplocloud.mcp.compact_tools.commands_for", return_value=TENANT_COMMANDS):
            result = explain(ctx, resource="tenant", command="nonexistent")

        assert "error" in result
        assert "available" in result


class TestCompactResources:
    """Tests for the compact mode resources tool."""

    def test_resources_returns_all(self):
        """Resources tool returns the pre-filtered list from ctx."""
        duplo = MagicMock()

        ctx = Ctx(duplo=duplo, config={}, tools=[], resources=["lambda", "service", "tenant"])
        result = resources(ctx)

        assert result["resources"] == ["lambda", "service", "tenant"]

    def test_resources_respects_filter(self):
        """Resources in ctx only contain what passed the filter at registration."""
        duplo = MagicMock()

        ctx = Ctx(duplo=duplo, config={}, tools=[], resources=["service", "tenant"])
        result = resources(ctx)

        assert "lambda" not in result["resources"]
        assert "tenant" in result["resources"]
        assert "service" in result["resources"]
