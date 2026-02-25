import asyncio
import sys

from .server import DuploCloudMCP


def main():
    try:
        server = DuploCloudMCP.from_args()
        server.register_tools()
        server.start()
    except (KeyboardInterrupt, asyncio.CancelledError, SystemExit):
        pass
    except Exception as e:
        print(f"Error: {e}", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
