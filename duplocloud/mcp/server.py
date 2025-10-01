from fastmcp import FastMCP

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


def create_server() -> FastMCP:
    """
    Create the MCP server and register tools.
    """
    return mcp
