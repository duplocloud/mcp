import sys
import traceback
from .server import DuploCloudMCP


def main():
    """
    Main entry point for the MCP server when invoked as a CLI command.

    Returns:
        int: Exit code (0 for success, non-zero for failure)
    """
    try:
        print("Starting DuploCloud MCP Server...")
        server = DuploCloudMCP.from_args()

        # Register all tools and resources
        print("Registering DuploCloud tools and resources...")
        server.register_tools()

        # Start the server
        print("MCP Server ready!")
        server.start()
        return 0
    except KeyboardInterrupt:
        print("\nServer interrupted. Shutting down gracefully...", file=sys.stderr)
        return 0
    except Exception as e:
        print(f"Error starting MCP server: {e}", file=sys.stderr)
        traceback.print_exc()
        return 1


if __name__ == "__main__":
    sys.exit(main())
