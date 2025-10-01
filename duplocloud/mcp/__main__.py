import os
from .server import create_server
import sys


def main():
    """
    Main entry point for the MCP server when invoked as a CLI command.

    Returns:
        int: Exit code (0 for success, non-zero for failure)
    """
    try:
        print("Starting DuploCloud MCP Server...")
        server = create_server()
        server.run(
            transport="http",
            host="0.0.0.0",
            port=int(os.getenv("PORT", 8000))
        )
        return 0
    except KeyboardInterrupt:
        print("\nServer interrupted. Shutting down...")
        return 0
    except Exception as e:
        print(f"Error starting MCP server: {e}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main())
