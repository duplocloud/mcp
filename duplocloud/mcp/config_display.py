"""Config display tool and route.

One plain function builds the config dict. Two thin decorated wrappers
expose it as an MCP tool and an HTTP route, both injected with Ctx.
"""

from starlette.requests import Request
from starlette.responses import JSONResponse

from .ctx import Ctx, custom_route, custom_tool


def build_config(ctx: Ctx) -> dict:
    """Build the MCP server configuration summary.

    Mirrors the output of ``duploctl`` (no args) but replaces
    AvailableResources with the filtered list and appends
    MCP-specific settings.

    Args:
        ctx: The injected server context.

    Returns:
        A dict suitable for JSON serialization.
    """
    cfg = dict(ctx.duplo.config)
    cfg["AvailableResources"] = ctx.resources
    cfg["Tools"] = sorted(ctx.tools)
    cfg["MCP"] = ctx.config
    return cfg


@custom_tool(name="config", description="Display current MCP server configuration.")
def config_tool(ctx: Ctx) -> dict:
    """Display current MCP server configuration.

    Returns the DuploCloud connection info, active filters, and the
    list of registered tools.
    """
    return build_config(ctx)


@custom_route("/config", methods=["GET"])
async def config_route(ctx: Ctx, request: Request):
    """GET /config -- same payload as the config tool."""
    return JSONResponse(build_config(ctx))
