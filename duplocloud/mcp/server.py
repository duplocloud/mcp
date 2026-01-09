from fastmcp import FastMCP
from starlette.responses import JSONResponse

mcp = FastMCP(
    "duplocloud-mcp",
)


@mcp.tool
def hello(name: str = "world") -> str:
    """
    Returns a greeting.

    Args:
        name: The name to greet.
    Returns:
        A greeting string.
    """
    return f"Hello, {name}!"


@mcp.custom_route("/health", methods=["GET"])
async def health_check(request):
    """
    Health check endpoint for load balancers and monitoring.

    Returns:
        JSON response with service status.
    """
    return JSONResponse({"status": "healthy", "service": "duplocloud-mcp"})


def create_server() -> FastMCP:
    """
    Create the MCP server and register tools.
    """
    return mcp
