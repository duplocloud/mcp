from .server import create_server


def main():
    """
    Main entry point for the MCP server.
    """
    server = create_server()
    server.run()


if __name__ == "__main__":
    main()
