import sys

# Simulate an error condition by setting an environment variable that will cause an error
import os
os.environ["FASTMCP_TEST_ERROR"] = "1"

try:
    # Import after setting the environment variable
    from duplocloud.mcp.server import create_server
    create_server()
    print('Should not reach here')
except Exception as e:
    print(f'Correctly caught error: {e}')
    sys.exit(0)
