"""Global FastMCP server instance.

This module provides the global FastMCP instance that other modules can import
to register custom routes, tools, or resources using decorators. This follows
the standard FastMCP pattern where the mcp instance is the central hub.

Example:
    from duplocloud.mcp.app import mcp

    @mcp.tool()
    def my_tool():
        return "result"
"""

from importlib.metadata import version

from fastmcp import FastMCP
from starlette.requests import Request
from starlette.responses import JSONResponse, Response

# Global FastMCP instance - safe to create at import time (no credentials needed)
mcp: FastMCP = FastMCP(
    name="duplocloud-mcp",
    version=version("duplocloud-mcp"),
)


@mcp.custom_route("/health", methods=["GET"])
async def health_check(request: Request) -> Response:
    """Health check endpoint for load balancers and monitoring.

    Returns:
        JSON response with service status.
    """
    return JSONResponse({"status": "healthy", "service": "duplocloud-mcp"})
