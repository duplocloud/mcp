"""MCP server context and custom tool/route registry.

Provides:
  - Ctx: a simple context object holding duplo client and server config,
    injected into custom tool/route handlers at registration time.
  - custom_tool / custom_route: decorators that collect functions into a
    registry. The server drains the registry after duploctl tool discovery
    and registers them with FastMCP, wrapping each to inject the Ctx.

The mode parameter on decorators allows a function to be registered only
when the server is running in a matching mode. If omitted the function
applies to all modes.
"""

from dataclasses import dataclass, field
from typing import Optional

from duplocloud.client import DuploClient

# ---------------------------------------------------------------------------
# Context
# ---------------------------------------------------------------------------

@dataclass
class Ctx:
    """Runtime context injected into custom tool and route handlers.

    Attributes:
        duplo: The DuploCloud client instance.
        config: Server configuration dict (transport, port, filters, etc.).
        tools: List of registered tool names (populated after registration).
        resources: Filtered resource names available to this server instance.
    """
    duplo: DuploClient
    config: dict = field(default_factory=dict)
    tools: list[str] = field(default_factory=list)
    resources: list[str] = field(default_factory=list)


# ---------------------------------------------------------------------------
# Registry
# ---------------------------------------------------------------------------

# Module-level lists that decorators append to.
_tool_registry: list[dict] = []
_route_registry: list[dict] = []


def custom_tool(name: str = None, description: str = None, mode: str = None):
    """Register a function as a custom MCP tool.

    The decorated function must accept ``ctx: Ctx`` as its first parameter.
    Additional parameters become the tool's input schema (inspected by
    FastMCP the same way as any tool function).

    Args:
        name: Tool name. Defaults to the function's ``__name__``.
        description: Tool description. Defaults to the function's docstring.
        mode: Only register when the server mode matches. None = all modes.

    Returns:
        The original function, unmodified.
    """
    def decorator(fn):
        _tool_registry.append({
            "fn": fn,
            "name": name or fn.__name__,
            "description": description or (fn.__doc__ or ""),
            "mode": mode,
        })
        return fn
    return decorator


def custom_route(path: str, methods: list[str], mode: str = None):
    """Register a function as a custom HTTP route.

    The decorated function must accept ``ctx: Ctx`` as its first parameter
    and ``request`` (starlette Request) as its second.

    Args:
        path: URL path (e.g. "/config").
        methods: HTTP methods (e.g. ["GET"]).
        mode: Only register when the server mode matches. None = all modes.

    Returns:
        The original function, unmodified.
    """
    def decorator(fn):
        _route_registry.append({
            "fn": fn,
            "path": path,
            "methods": methods,
            "mode": mode,
        })
        return fn
    return decorator


def drain_tools(mode: Optional[str] = None) -> list[dict]:
    """Return and clear all registered custom tools matching *mode*.

    Entries with ``mode=None`` always match. Consumed entries are removed
    from the registry so they are not registered twice.
    """
    matched = [
        e for e in _tool_registry
        if e["mode"] is None or e["mode"] == mode
    ]
    for e in matched:
        _tool_registry.remove(e)
    return matched


def drain_routes(mode: Optional[str] = None) -> list[dict]:
    """Return and clear all registered custom routes matching *mode*."""
    matched = [
        e for e in _route_registry
        if e["mode"] is None or e["mode"] == mode
    ]
    for e in matched:
        _route_registry.remove(e)
    return matched
