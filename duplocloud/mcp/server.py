"""DuploCloud MCP server lifecycle coordinator.

DuploCloudMCP knows about transport, ports, and which resources to register.
It does not know how tool wrapping, signature rewriting, or model resolution
works -- that is delegated to ToolRegistrar.
"""

import inspect
import re
from typing import Any, Optional

from duplocloud.client import DuploClient
from duplocloud.commander import available_resources, load_format
from fastmcp import FastMCP
from fastmcp.utilities.logging import get_logger

from .app import mcp as mcp_app
from .args import build_parser
from .ctx import Ctx, drain_routes, drain_tools
from .tools import ToolRegistrar

# Import modules that use @custom_tool / @custom_route so
# the registry is populated before register_custom() drains it.
from . import config_display as _  # noqa: F401
from . import compact_tools as __  # noqa: F401

logger = get_logger(__name__)


class DuploCloudMCP:
    """DuploCloud MCP server.

    Thin coordinator that owns server lifecycle: argument parsing, resource
    filtering, tool registration delegation, and transport startup.
    """

    def __init__(
        self,
        mcp: FastMCP,
        duplo: DuploClient,
        transport: str = "http",
        port: int = 8000,
        resource_filter: str = ".*",
        command_filter: str = ".*",
        tool_mode: str = "expanded",
    ):
        """Initialize the server.

        Args:
            mcp: The FastMCP instance.
            duplo: The DuploCloud client instance.
            transport: Transport protocol ("stdio" or "http").
            port: Port for HTTP transport.
            resource_filter: Regex pattern for resource names to include.
            command_filter: Regex pattern for command names to include.
            tool_mode: Tool registration mode ("expanded" or "compact").
        """
        self.mcp = mcp
        self.duplo = duplo
        self.transport = transport
        self.port = port
        self.resource_filter = re.compile(resource_filter)
        self.command_filter = re.compile(command_filter)
        self.tool_mode = tool_mode
        self._filtered_resources: list[str] = []

    @staticmethod
    def from_args(args: Optional[list[str]] = None):
        """Create a DuploCloudMCP instance from CLI arguments.

        DuploClient handles its own arguments and returns the rest.
        The remaining arguments are parsed for MCP server configuration.

        Args:
            args: CLI arguments (uses sys.argv if None).

        Returns:
            A configured DuploCloudMCP instance.
        """
        duplo, rest = DuploClient.from_env()

        parser = build_parser()
        parsed = parser.parse_args(rest if args is None else args)

        return DuploCloudMCP(
            mcp=mcp_app,
            duplo=duplo,
            transport=parsed.transport,
            port=parsed.port,
            resource_filter=parsed.resource_filter,
            command_filter=parsed.command_filter,
            tool_mode=parsed.tool_mode,
        )

    def register_tools(self, resource_names: Optional[list[str]] = None):
        """Register DuploCloud tools with the MCP server.

        If resource_names is None, discovers all available resources.
        Applies the resource filter before delegating to ToolRegistrar.

        Args:
            resource_names: Explicit list of resources, or None for all.
        """
        if resource_names is None:
            resource_names = available_resources()

        # Apply resource filter
        filtered = [
            name for name in resource_names
            if self.resource_filter.fullmatch(name)
        ]

        skipped = set(resource_names) - set(filtered)
        if skipped:
            for name in sorted(skipped):
                logger.debug(f"Skipping resource '{name}' (resource filter)")

        self._filtered_resources = sorted(filtered)
        logger.info(f"Registering tools for: {', '.join(self._filtered_resources)}")

        if self.tool_mode == "compact":
            logger.info("Compact mode: tools provided by custom tools (execute, explain, resources)")
        else:
            registrar = ToolRegistrar(self.mcp, self.duplo, self.command_filter)
            registrar.register(filtered)

        # Register custom tools and routes, injecting context
        self.register_custom(mode=self.tool_mode)

    def register_custom(self, mode: Optional[str] = None):
        """Drain the custom tool/route registries and register them.

        Builds a Ctx from current server state, then wraps each registered
        function so Ctx (and Request for routes) are injected automatically.
        The wrapper's visible signature is the original minus the ``ctx``
        parameter, so FastMCP only sees the user-facing parameters.

        Args:
            mode: Only register entries matching this mode (None = all).
        """
        ctx = self._build_ctx()

        # --- custom tools ---
        for entry in drain_tools(mode):
            fn = entry["fn"]
            tool_name = entry["name"]
            description = entry["description"]

            # Build a wrapper that injects ctx, hiding it from FastMCP
            wrapper = self._inject_ctx(fn, ctx)
            self.mcp.tool(name=tool_name, description=description or None)(wrapper)
            logger.info(f"    {tool_name} (custom)")

        # --- custom routes ---
        for entry in drain_routes(mode):
            fn = entry["fn"]
            path = entry["path"]
            methods = entry["methods"]

            # Route wrapper: inject ctx, pass request through
            async def route_handler(request, _fn=fn, _ctx=ctx):
                return await _fn(_ctx, request)

            self.mcp.custom_route(path, methods=methods)(route_handler)
            logger.info(f"    route {path} (custom)")

    def _build_ctx(self) -> Ctx:
        """Build a Ctx snapshot from current server state."""
        return Ctx(
            duplo=self.duplo,
            config={
                "transport": self.transport,
                "port": self.port,
                "resource_filter": self.resource_filter.pattern,
                "command_filter": self.command_filter.pattern,
                "tool_mode": self.tool_mode,
            },
            tools=self._list_tool_names(),
            resources=list(self._filtered_resources),
        )

    def _list_tool_names(self) -> list[str]:
        """Collect names of all tools currently registered on the FastMCP instance."""
        import asyncio

        async def _get():
            return [t.name for t in await self.mcp.list_tools()]

        # If there's already a running loop, schedule on it; otherwise run fresh
        try:
            asyncio.get_running_loop()
            # We're inside an event loop already — create a task
            asyncio.ensure_future(_get())
            # This path shouldn't happen during startup, but handle it
            return []
        except RuntimeError:
            return asyncio.run(_get())

    @staticmethod
    def _inject_ctx(fn, ctx: Ctx):
        """Wrap fn so that ctx is injected and hidden from FastMCP.

        Removes the ``ctx`` parameter from the wrapper's signature so
        FastMCP only sees the remaining user-facing parameters.

        Args:
            fn: The function to wrap (must accept ctx as first arg).
            ctx: The context to inject.

        Returns:
            A wrapper with ctx-free signature.
        """
        sig = inspect.signature(fn)
        # Remove 'ctx' from the visible signature
        new_params = [
            p for p in sig.parameters.values()
            if p.name != "ctx"
        ]

        def wrapper(*args, **kwargs):
            return fn(ctx, *args, **kwargs)

        wrapper.__name__ = fn.__name__
        wrapper.__doc__ = fn.__doc__
        wrapper.__signature__ = sig.replace(parameters=new_params)
        wrapper.__annotations__ = {
            p.name: p.annotation
            for p in new_params
            if p.annotation is not inspect.Parameter.empty
        }
        return wrapper

    def start(self):
        """Start the MCP server.

        Logs environment info and active filters, then runs the transport.
        """
        yaml_formatter = load_format("yaml")
        formatted_info = yaml_formatter(self.duplo.config)
        logger.info(f"DuploCloud Environment Info:\n{formatted_info}")

        # Log active filters if non-default
        logger.info(f"Tool mode: {self.tool_mode}")
        if self.resource_filter.pattern != ".*":
            logger.info(f"Resource filter: {self.resource_filter.pattern}")
        if self.command_filter.pattern != ".*":
            logger.info(f"Command filter: {self.command_filter.pattern}")

        run_kwargs: dict[str, Any] = {"transport": self.transport}
        if self.transport == "http":
            run_kwargs["host"] = "0.0.0.0"
            run_kwargs["port"] = self.port

        logger.info(f"Starting MCP server with transport: {self.transport}")
        if self.transport == "http":
            logger.info(f"Server at http://0.0.0.0:{self.port}/mcp")

        return self.mcp.run(**run_kwargs)
