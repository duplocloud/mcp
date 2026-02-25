"""Tests for custom tool/route registration and context injection.

Tests the server's register_custom flow, _inject_ctx, and the config
display tool/route as a real consumer of the pattern.
"""

import asyncio
import inspect
from unittest.mock import MagicMock, patch

import pytest
from fastmcp import FastMCP
from starlette.testclient import TestClient

from duplocloud.mcp.config_display import build_config
from duplocloud.mcp.ctx import (
    Ctx,
    _route_registry,
    _tool_registry,
    custom_route,
    custom_tool,
)
from duplocloud.mcp.server import DuploCloudMCP


@pytest.fixture(autouse=True)
def clean_registries():
    """Ensure registries are empty before and after each test."""
    _tool_registry.clear()
    _route_registry.clear()
    yield
    _tool_registry.clear()
    _route_registry.clear()


@pytest.fixture
def mock_duplo():
    duplo = MagicMock()
    duplo.host = "https://test.duplocloud.net"
    duplo.tenant = "default"
    duplo.config = {
        "Host": "https://test.duplocloud.net",
        "Tenant": "default",
        "HomeDir": "/home/test/.duplo",
        "ConfigFile": "/home/test/.duplo/config.yaml",
        "CacheDir": "/home/test/.duplo/cache",
        "Version": "0.4.2",
        "Path": "/usr/bin/duploctl",
        "AvailableResources": ["tenant", "service"],
    }
    return duplo


@pytest.fixture
def ctx(mock_duplo):
    return Ctx(
        duplo=mock_duplo,
        config={"transport": "http", "port": 8000,
                "resource_filter": ".*", "command_filter": ".*"},
        tools=["tenant_list", "tenant_find", "tenant_create"],
    )


# ---------------------------------------------------------------------------
# _inject_ctx
# ---------------------------------------------------------------------------

class TestInjectCtx:

    def test_hides_ctx_from_signature(self, ctx):
        def fn(ctx: Ctx, name: str = "test") -> dict:
            return {"name": name}

        wrapper = DuploCloudMCP._inject_ctx(fn, ctx)
        sig = inspect.signature(wrapper)
        assert "ctx" not in sig.parameters
        assert "name" in sig.parameters

    def test_injects_ctx_at_call_time(self, ctx):
        received = {}

        def fn(ctx: Ctx, greeting: str = "hello"):
            received["ctx"] = ctx
            received["greeting"] = greeting
            return f"{greeting} from {ctx.duplo.tenant}"

        wrapper = DuploCloudMCP._inject_ctx(fn, ctx)
        result = wrapper(greeting="hi")
        assert result == "hi from default"
        assert received["ctx"] is ctx

    def test_preserves_name_and_doc(self, ctx):
        def my_func(ctx: Ctx):
            """My docstring."""
            pass

        wrapper = DuploCloudMCP._inject_ctx(my_func, ctx)
        assert wrapper.__name__ == "my_func"
        assert wrapper.__doc__ == "My docstring."

    def test_no_extra_params_for_zero_arg_tool(self, ctx):
        def fn(ctx: Ctx) -> dict:
            return {}

        wrapper = DuploCloudMCP._inject_ctx(fn, ctx)
        sig = inspect.signature(wrapper)
        assert len(sig.parameters) == 0

    def test_annotations_exclude_ctx(self, ctx):
        def fn(ctx: Ctx, name: str = "x") -> dict:
            return {}

        wrapper = DuploCloudMCP._inject_ctx(fn, ctx)
        assert "ctx" not in wrapper.__annotations__
        assert wrapper.__annotations__.get("name") is str


# ---------------------------------------------------------------------------
# register_custom (integration with FastMCP)
# ---------------------------------------------------------------------------

class TestRegisterCustom:

    def test_custom_tool_registered_on_mcp(self, mock_duplo):
        """A @custom_tool function ends up as a FastMCP tool."""
        @custom_tool(name="test_tool", description="A test.")
        def test_tool(ctx: Ctx):
            return {"ok": True}

        mcp = FastMCP(name="test", version="0.0.0")
        server = DuploCloudMCP(mcp=mcp, duplo=mock_duplo)

        server.register_custom()

        # Verify it's registered
        tools = asyncio.run(mcp.list_tools())
        names = [t.name for t in tools]
        assert "test_tool" in names

    def test_custom_tool_ctx_injected(self, mock_duplo):
        """When the tool is called, ctx is injected."""
        received_ctx = {}

        @custom_tool(name="spy_tool")
        def spy(ctx: Ctx):
            received_ctx["duplo"] = ctx.duplo
            return "spied"

        mcp = FastMCP(name="test", version="0.0.0")
        server = DuploCloudMCP(mcp=mcp, duplo=mock_duplo)
        server.register_custom()

        # Call the tool through FastMCP
        result = asyncio.run(mcp.call_tool("spy_tool", {}))
        assert received_ctx["duplo"] is mock_duplo

    def test_mode_filter_on_custom_tool(self, mock_duplo):
        """Tools with non-matching mode are not registered."""
        @custom_tool(name="admin_only", mode="admin")
        def admin_tool(ctx: Ctx):
            return "admin"

        @custom_tool(name="always")
        def always_tool(ctx: Ctx):
            return "always"

        mcp = FastMCP(name="test", version="0.0.0")
        server = DuploCloudMCP(mcp=mcp, duplo=mock_duplo)

        # Register with mode="user" — admin_only should not match
        server.register_custom(mode="user")

        tools = asyncio.run(mcp.list_tools())
        names = [t.name for t in tools]
        assert "always" in names
        assert "admin_only" not in names

    def test_custom_tool_with_extra_params(self, mock_duplo):
        """Tool params beyond ctx are visible to FastMCP."""
        @custom_tool(name="greeter")
        def greet(ctx: Ctx, name: str = "world"):
            return f"hello {name}"

        mcp = FastMCP(name="test", version="0.0.0")
        server = DuploCloudMCP(mcp=mcp, duplo=mock_duplo)
        server.register_custom()

        result = asyncio.run(mcp.call_tool("greeter", {"name": "duplo"}))
        # FastMCP wraps results; just check it didn't error
        assert result is not None


# ---------------------------------------------------------------------------
# register_custom -- HTTP route integration
# ---------------------------------------------------------------------------

class TestCustomRoutes:
    """Verify @custom_route functions are reachable via HTTP."""

    def test_route_responds(self, mock_duplo):
        """A @custom_route handler is reachable at its path."""
        @custom_route("/ping", methods=["GET"])
        async def ping_route(ctx: Ctx, request):
            from starlette.responses import JSONResponse
            return JSONResponse({"pong": True})

        mcp = FastMCP(name="test", version="0.0.0")
        server = DuploCloudMCP(mcp=mcp, duplo=mock_duplo)
        server.register_custom()

        client = TestClient(mcp.http_app(), raise_server_exceptions=True)
        resp = client.get("/ping")
        assert resp.status_code == 200
        assert resp.json() == {"pong": True}

    def test_route_ctx_injected(self, mock_duplo):
        """The ctx object is available inside the route handler."""
        received = {}

        @custom_route("/spy", methods=["GET"])
        async def spy_route(ctx: Ctx, request):
            from starlette.responses import JSONResponse
            received["duplo"] = ctx.duplo
            return JSONResponse({"tenant": ctx.duplo.tenant})

        mcp = FastMCP(name="test", version="0.0.0")
        server = DuploCloudMCP(mcp=mcp, duplo=mock_duplo)
        server.register_custom()

        client = TestClient(mcp.http_app(), raise_server_exceptions=True)
        resp = client.get("/spy")
        assert resp.status_code == 200
        assert resp.json()["tenant"] == "default"
        assert received["duplo"] is mock_duplo

    def test_config_route_returns_200(self, mock_duplo):
        """The built-in /config route returns 200 with JSON."""
        # config_display is already imported (Python caches modules), so the
        # decorators don't re-run. Manually push the real config_route entry
        # into the registry that the autouse fixture cleared.
        from duplocloud.mcp.config_display import config_route
        _route_registry.append({
            "fn": config_route,
            "path": "/config",
            "methods": ["GET"],
            "mode": None,
        })

        mcp = FastMCP(name="test", version="0.0.0")
        server = DuploCloudMCP(mcp=mcp, duplo=mock_duplo)
        server.register_custom()

        client = TestClient(mcp.http_app(), raise_server_exceptions=True)
        resp = client.get("/config")
        assert resp.status_code == 200
        body = resp.json()
        assert "Tools" in body
        assert "MCP" in body
        assert "Host" in body

    def test_route_mode_filter_not_registered(self, mock_duplo):
        """Route with non-matching mode is not reachable."""
        @custom_route("/secret", methods=["GET"], mode="admin")
        async def secret_route(ctx: Ctx, request):
            from starlette.responses import JSONResponse
            return JSONResponse({"secret": True})

        mcp = FastMCP(name="test", version="0.0.0")
        server = DuploCloudMCP(mcp=mcp, duplo=mock_duplo)
        server.register_custom(mode="user")  # "admin" route should be skipped

        client = TestClient(mcp.http_app(), raise_server_exceptions=False)
        resp = client.get("/secret")
        assert resp.status_code == 404


# ---------------------------------------------------------------------------
# build_config (the pure function)
# ---------------------------------------------------------------------------

class TestBuildConfig:

    def test_extends_duplo_config(self, ctx):
        """build_config starts from duplo.config and adds to it."""
        result = build_config(ctx)
        # Keys inherited from duplo.config
        assert result["Host"] == "https://test.duplocloud.net"
        assert result["Tenant"] == "default"
        assert result["Version"] == "0.4.2"
        assert result["HomeDir"] == "/home/test/.duplo"
        assert result["Path"] == "/usr/bin/duploctl"

    def test_replaces_available_resources(self, ctx):
        """AvailableResources is replaced with the filtered resource list."""
        result = build_config(ctx)
        assert result["AvailableResources"] == ctx.resources

    def test_tools_sorted(self, ctx):
        result = build_config(ctx)
        assert result["Tools"] == ["tenant_create", "tenant_find", "tenant_list"]

    def test_mcp_config(self, ctx):
        result = build_config(ctx)
        assert result["MCP"]["transport"] == "http"
        assert result["MCP"]["port"] == 8000
        assert result["MCP"]["resource_filter"] == ".*"
        assert result["MCP"]["command_filter"] == ".*"

    def test_config_reflects_filters(self, mock_duplo):
        ctx = Ctx(
            duplo=mock_duplo,
            config={
                "transport": "stdio",
                "port": 9090,
                "resource_filter": "tenant",
                "command_filter": "list|find",
            },
            tools=["tenant_list", "tenant_find"],
        )
        result = build_config(ctx)
        assert result["MCP"]["resource_filter"] == "tenant"
        assert result["MCP"]["command_filter"] == "list|find"
        assert result["Tools"] == ["tenant_find", "tenant_list"]

    def test_does_not_mutate_duplo_config(self, ctx):
        """build_config must not modify the original duplo.config."""
        original = dict(ctx.duplo.config)
        build_config(ctx)
        assert ctx.duplo.config == original
