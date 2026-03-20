"""DuploCloud documentation MCP proxy.

Provides a FastMCP proxy to the GitBook-hosted DuploCloud documentation
so that documentation tools are exposed alongside the duploctl tools.
"""

from fastmcp import FastMCP
from fastmcp.server import create_proxy
from fastmcp.utilities.logging import get_logger

logger = get_logger(__name__)

# The DuploCloud documentation MCP endpoint (GitBook Streamable HTTP).
DOCS_MCP_URL = "https://docs.duplocloud.com/docs/~gitbook/mcp"

# Prefix applied to proxied tool names (e.g. docs_search).
DOCS_PREFIX = "docs"


def mount_docs(mcp: FastMCP):
    """Mount the DuploCloud documentation proxy onto the server.

    Creates a proxy to the GitBook documentation MCP endpoint and
    mounts it with a ``docs`` prefix so tool names are namespaced.

    Args:
        mcp: The FastMCP server instance to mount onto.
    """
    logger.info(f"Mounting documentation proxy: {DOCS_MCP_URL}")
    docs_proxy = create_proxy(DOCS_MCP_URL, name="duplocloud-docs")
    mcp.mount(docs_proxy, prefix=DOCS_PREFIX)
