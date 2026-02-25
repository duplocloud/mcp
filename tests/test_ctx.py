"""Tests for the Ctx dataclass and decorator registry."""

import pytest

from duplocloud.mcp.ctx import (
    Ctx,
    _route_registry,
    _tool_registry,
    custom_route,
    custom_tool,
    drain_routes,
    drain_tools,
)


@pytest.fixture(autouse=True)
def clean_registries():
    """Ensure registries are empty before and after each test."""
    _tool_registry.clear()
    _route_registry.clear()
    yield
    _tool_registry.clear()
    _route_registry.clear()


# ---------------------------------------------------------------------------
# Ctx dataclass
# ---------------------------------------------------------------------------

class TestCtx:

    def test_defaults(self):
        ctx = Ctx(duplo=None)
        assert ctx.config == {}
        assert ctx.tools == []
        assert ctx.duplo is None

    def test_fields(self):
        ctx = Ctx(
            duplo="fake_duplo",
            config={"transport": "http"},
            tools=["tenant_list"],
        )
        assert ctx.duplo == "fake_duplo"
        assert ctx.config["transport"] == "http"
        assert ctx.tools == ["tenant_list"]


# ---------------------------------------------------------------------------
# @custom_tool decorator
# ---------------------------------------------------------------------------

class TestCustomToolDecorator:

    def test_registers_function(self):
        @custom_tool()
        def my_tool(ctx):
            pass

        assert len(_tool_registry) == 1
        assert _tool_registry[0]["fn"] is my_tool

    def test_default_name_from_function(self):
        @custom_tool()
        def some_name(ctx):
            pass

        assert _tool_registry[0]["name"] == "some_name"

    def test_explicit_name(self):
        @custom_tool(name="custom_name")
        def fn(ctx):
            pass

        assert _tool_registry[0]["name"] == "custom_name"

    def test_default_description_from_docstring(self):
        @custom_tool()
        def fn(ctx):
            """My description."""
            pass

        assert _tool_registry[0]["description"] == "My description."

    def test_explicit_description(self):
        @custom_tool(description="Overridden.")
        def fn(ctx):
            """Original."""
            pass

        assert _tool_registry[0]["description"] == "Overridden."

    def test_mode_none_by_default(self):
        @custom_tool()
        def fn(ctx):
            pass

        assert _tool_registry[0]["mode"] is None

    def test_mode_set(self):
        @custom_tool(mode="admin")
        def fn(ctx):
            pass

        assert _tool_registry[0]["mode"] == "admin"

    def test_returns_original_function(self):
        @custom_tool()
        def fn(ctx):
            return 42

        assert fn(None) == 42


# ---------------------------------------------------------------------------
# @custom_route decorator
# ---------------------------------------------------------------------------

class TestCustomRouteDecorator:

    def test_registers_route(self):
        @custom_route("/test", methods=["GET"])
        async def my_route(ctx, request):
            pass

        assert len(_route_registry) == 1
        assert _route_registry[0]["fn"] is my_route
        assert _route_registry[0]["path"] == "/test"
        assert _route_registry[0]["methods"] == ["GET"]

    def test_mode_none_by_default(self):
        @custom_route("/x", methods=["POST"])
        async def fn(ctx, request):
            pass

        assert _route_registry[0]["mode"] is None

    def test_mode_set(self):
        @custom_route("/x", methods=["GET"], mode="debug")
        async def fn(ctx, request):
            pass

        assert _route_registry[0]["mode"] == "debug"


# ---------------------------------------------------------------------------
# drain_tools / drain_routes
# ---------------------------------------------------------------------------

class TestDrainTools:

    def test_drain_returns_all_when_no_mode(self):
        @custom_tool()
        def a(ctx):
            pass

        @custom_tool()
        def b(ctx):
            pass

        result = drain_tools()
        assert len(result) == 2
        assert len(_tool_registry) == 0  # cleared

    def test_drain_filters_by_mode(self):
        @custom_tool(mode="admin")
        def admin_fn(ctx):
            pass

        @custom_tool(mode="user")
        def user_fn(ctx):
            pass

        @custom_tool()
        def any_fn(ctx):
            pass

        result = drain_tools(mode="admin")
        names = [e["fn"].__name__ for e in result]
        assert "admin_fn" in names
        assert "any_fn" in names  # mode=None matches all
        assert "user_fn" not in names

        # user_fn should still be in the registry
        assert len(_tool_registry) == 1
        assert _tool_registry[0]["fn"].__name__ == "user_fn"

    def test_drain_is_idempotent(self):
        @custom_tool()
        def fn(ctx):
            pass

        drain_tools()
        result = drain_tools()
        assert result == []


class TestDrainRoutes:

    def test_drain_returns_all_when_no_mode(self):
        @custom_route("/a", methods=["GET"])
        async def a(ctx, req):
            pass

        @custom_route("/b", methods=["POST"])
        async def b(ctx, req):
            pass

        result = drain_routes()
        assert len(result) == 2
        assert len(_route_registry) == 0

    def test_drain_filters_by_mode(self):
        @custom_route("/admin", methods=["GET"], mode="admin")
        async def admin_route(ctx, req):
            pass

        @custom_route("/public", methods=["GET"])
        async def public_route(ctx, req):
            pass

        result = drain_routes(mode="admin")
        paths = [e["path"] for e in result]
        assert "/admin" in paths
        assert "/public" in paths  # mode=None matches all

        assert len(_route_registry) == 0
