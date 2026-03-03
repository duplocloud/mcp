"""DuploCloud MCP server — duploctl resource plugin.

Registers ``mcp`` as a duploctl resource so the server can be launched via::

    duploctl mcp --transport stdio --tool-mode compact

DuploCloudMCP knows about transport, ports, and which resources to register.
It does not know how tool wrapping, signature rewriting, or model resolution
works -- that is delegated to ToolRegistrar.
"""

import asyncio
import inspect
import re
from typing import Any, Optional

from duplocloud.argtype import Arg
from duplocloud.client import DuploClient
from duplocloud.commander import Command, Resource, available_resources, load_format
from duplocloud.resource import DuploResource
from fastmcp.utilities.logging import get_logger

from . import compact_tools as _compact_tools  # noqa: F401
from . import config_display as _config_display  # noqa: F401
from .app import mcp as mcp_app
from .ctx import Ctx, drain_routes, drain_tools
from .tools import ToolRegistrar

logger = get_logger(__name__)

# Resources that must never be registered as MCP tools.
# "mcp" is excluded to prevent the server from registering itself.
_EXCLUDED_RESOURCES = {"mcp"}

# ---------------------------------------------------------------------------
# MCP-specific Arg types
# ---------------------------------------------------------------------------

TRANSPORT = Arg(
    "transport", "-tp",
    help="The transport protocol to use (stdio or http)",
    default="stdio",
    choices=["stdio", "http"],
    env="DUPLO_MCP_TRANSPORT",
)

PORT = Arg(
    "port", "-mp",
    help="The port to listen on for HTTP transport",
    type=int,
    default=8000,
    env="DUPLO_MCP_PORT",
)

RESOURCE_FILTER = Arg(
    "resource_filter", "--resource-filter",
    help="Regex pattern for resource names to include",
    default=".*",
    env="DUPLO_MCP_RESOURCE_FILTER",
)

COMMAND_FILTER = Arg(
    "command_filter", "--command-filter",
    help="Regex pattern for command names to include",
    default=".*",
    env="DUPLO_MCP_COMMAND_FILTER",
)

TOOL_MODE = Arg(
    "tool_mode", "--tool-mode",
    help="Tool registration mode: expanded or compact",
    default="compact",
    choices=["expanded", "compact"],
    env="DUPLO_MCP_TOOL_MODE",
)


# ---------------------------------------------------------------------------
# Resource plugin
# ---------------------------------------------------------------------------

@Resource("mcp")
class DuploCloudMCP(DuploResource):
    """DuploCloud MCP server.

    Starts a Model Context Protocol server that discovers duploctl resources
    and exposes them as MCP tools for AI agents and compatible clients.
    """

    def __init__(self, duplo: DuploClient):
        super().__init__(duplo)
        self.duplo.output = None
        self.mcp = mcp_app
        self._filtered_resources: list[str] = []
        self.transport = "stdio"
        self.port = 8000
        self.resource_filter = re.compile(".*")
        self.command_filter = re.compile(".*")
        self.tool_mode = "compact"

    def __call__(self, *args):
        """Parse CLI args and start the MCP server.

        Overrides :meth:`DuploResource.__call__` so that no subcommand name
        is required.  ``duploctl mcp --transport stdio`` routes directly to
        :meth:`start` via its argparse wrapper.
        """
        c = self.command("start")
        return c(*args)

    @Command()
    def start(
        self,
        transport: TRANSPORT,
        port: PORT,
        resource_filter: RESOURCE_FILTER,
        command_filter: COMMAND_FILTER,
        tool_mode: TOOL_MODE,
    ):
        """Start the MCP server.

        Starts the DuploCloud MCP server with the specified configuration.
        The server discovers duploctl resources and exposes them as MCP tools.
        """
        if transport is not None:
            self.transport = transport
        if port is not None:
            self.port = port
        if resource_filter is not None:
            self.resource_filter = re.compile(resource_filter)
        if command_filter is not None:
            self.command_filter = re.compile(command_filter)
        if tool_mode is not None:
            self.tool_mode = tool_mode

        self.duplo.validate = self.tool_mode == "compact"

        self.register_tools()
        self._start_transport()

    # ------------------------------------------------------------------
    # Tool registration
    # ------------------------------------------------------------------

    def register_tools(self, resource_names: Optional[list[str]] = None):
        """Register DuploCloud tools with the MCP server.

        If resource_names is None, discovers all available resources.
        Always excludes internal resources (like ``mcp`` itself), then
        applies the resource filter before delegating to ToolRegistrar.

        Args:
            resource_names: Explicit list of resources, or None for all.
        """
        if resource_names is None:
            resource_names = available_resources()

        # Always strip internal resources first
        resource_names = [
            name for name in resource_names
            if name not in _EXCLUDED_RESOURCES
        ]

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

    # ------------------------------------------------------------------
    # Internals
    # ------------------------------------------------------------------

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

        async def _get():
            return [t.name for t in await self.mcp.list_tools()]

        # If there's already a running loop, schedule on it; otherwise run fresh
        try:
            asyncio.get_running_loop()
            asyncio.ensure_future(_get())
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

    def _start_transport(self):
        """Log environment info and active filters, then run the transport."""
        yaml_formatter = load_format("yaml")
        formatted_info = yaml_formatter(self.duplo.config)
        logger.info(f"DuploCloud Environment Info:\n{formatted_info}")

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
