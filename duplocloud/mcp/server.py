import os
import sys
import inspect
import argparse
from typing import Optional, Any
from fastmcp import FastMCP
from importlib.metadata import version
from duplocloud.client import DuploClient
from duplocloud.commander import schema, resources, extract_args, load_format
from duplocloud.argtype import Arg
from fastmcp.utilities.logging import get_logger

logger = get_logger(__name__)


class DuploCloudMCP():
    """
    DuploCloud MCP wrapper for duploctl commands.

    Wraps duploctl @Command decorated methods and exposes them as MCP resources 
    (for read operations) or tools (for write operations).
    """

    # Define which operations should also be registered as resources
    READ_OPERATIONS = {'list', 'find', 'logs', 'pods'}

    def __init__(self,
                 duplo: DuploClient,
                 transport: str = "http",
                 port: int = 8000,
                 name: str = "duplocloud-mcp"):
        """
        Initialize the DuploCloud MCP server.

        Args:
            duplo: The DuploCloud client instance
            transport: The transport protocol to use (stdio or http)
            port: The port to listen on for HTTP transport
            name: The name of the MCP server
        """
        self.mcp = FastMCP(
            name=name,
            version=version("duplocloud-mcp"),
        )
        self.duplo = duplo
        self.transport = transport
        self.port = port

    @staticmethod
    def from_args(args: Optional[list[str]] = None):
        """
        Create a DuploCloudMCP instance from command-line arguments.

        The duplocloud-client handles its own arguments and returns the rest.
        We parse the remaining arguments for MCP server configuration.

        Args:
            args: Command-line arguments (uses sys.argv if None)

        Returns:
            DuploCloudMCP: An instance of the MCP server
        """
        # The duplocloud-client handles its own arguments and returns the rest
        duplo, rest = DuploClient.from_env()

        # Parse the rest of the arguments for MCP server config
        parser = argparse.ArgumentParser(
            description="DuploCloud MCP Server",
            prog="duplocloud-mcp"
        )
        parser.add_argument(
            "--transport",
            choices=["stdio", "http"],
            default=os.getenv("MCP_TRANSPORT", "http"),
            help="The transport protocol to use (default: http)"
        )
        parser.add_argument(
            "--port",
            type=int,
            default=int(os.getenv("PORT", os.getenv("MCP_PORT", "8000"))),
            help="The port to listen on for HTTP transport (default: 8000)"
        )

        # Parse the remaining args
        parsed = parser.parse_args(rest if args is None else args)

        return DuploCloudMCP(
            duplo=duplo,
            transport=parsed.transport,
            port=parsed.port
        )

    def start(self):
        """
        Start the MCP server.
        """
        # Log environment details
        yaml_formatter = load_format("yaml")
        formatted_info = yaml_formatter(self.duplo.config)
        logger.info(f"DuploCloud Environment Info:\n{formatted_info}")

        # Set up the run arguments.
        run_kwargs: dict[str, Any] = {
            "transport": self.transport
        }
        if self.transport == "http":
            run_kwargs["host"] = "0.0.0.0"
            run_kwargs["port"] = self.port
            # Configure uvicorn to handle shutdown more gracefully
            run_kwargs["uvicorn_config"] = {
                "timeout_graceful_shutdown": 1
            }

        logger.info(f"Starting MCP server with transport: {self.transport}")
        if self.transport == "http":
            logger.info(
                f"Server will be available at http://{run_kwargs['host']}:{run_kwargs['port']}/mcp")

        return self.mcp.run(**run_kwargs)

    def register_tools(self):
        """
        Register DuploCloud tools and resources with the MCP.

        Uses the duploctl schema to identify @Command decorated methods
        and register them appropriately.
        """
        # Register service resource commands
        self._register_commands("service")

    def _register_commands(self, resource_name: str):
        """
        Register all @Command decorated methods from a duploctl resource.

        Uses the commander.schema to identify which methods are actual commands
        vs helper methods.

        Args:
            resource_name: The name of the duploctl resource (e.g., "service", "pod", "tenant")
        """
        # Load the duploctl resource instance
        resource = self.duplo.load(resource_name)

        # Get the resource class info from resources registry
        resource_info = resources.get(resource_name)
        if not resource_info:
            print(
                f"Warning: Resource '{resource_name}' not found in resources registry")
            return

        class_name = resource_info["class"]
        print(
            f"Registering commands for {resource_name} (class: {class_name})")

        # Iterate through the schema to find @Command decorated methods for this resource
        for qualified_name, command_info in schema.items():
            # The qualified_name format is "ClassName.method_name"
            # Check if this command belongs to our resource class
            if command_info["class"] != class_name:
                continue

            method_name = command_info["method"]

            # Get the actual method from the resource instance
            method = getattr(resource, method_name, None)
            if not method or not callable(method):
                print(
                    f"  Warning: Method '{method_name}' not found or not callable")
                continue

            # Register read operations as resources (in addition to tools)
            if method_name in self.READ_OPERATIONS:
                self._register_as_resource(resource_name, method_name, method)

            # All @Command methods are registered as tools
            self._register_as_tool(resource_name, method_name, method)

    def _register_as_resource(self, resource_name: str, method_name: str, method):
        """
        Register a duploctl method as an MCP resource (read-only operation).

        Placeholder for future resource registration implementation.
        TODO: Implement URI-based resource registration with templates.

        Args:
            resource_name: The duploctl resource name
            method_name: The method name
            method: The method reference with preserved signature
        """
        # Placeholder - will implement resource registration later
        pass

    def _register_as_tool(self, resource_name: str, method_name: str, method):
        """
        Register a duploctl method as an MCP tool (write operation).

        Creates a wrapper function that converts Arg types to standard Python types
        so FastMCP/Pydantic can properly introspect and validate them.

        Args:
            resource_name: The duploctl resource name
            method_name: The method name
            method: The method reference with preserved signature
        """
        tool_name = f"{resource_name}_{method_name}"

        # Extract Arg annotations
        cliargs = extract_args(method)

        # If no Args, register directly
        if not cliargs:
            self.mcp.tool(name=tool_name)(method)
            print(f"  Registered tool: {tool_name} (no args)")
            return

        # Build new parameters with base Python types
        new_params = []
        sig = inspect.signature(method)

        for arg in cliargs:
            # Get the original parameter
            orig_param = sig.parameters.get(arg.__name__)
            if not orig_param:
                continue

            # Create new parameter with base type from __supertype__
            new_param = inspect.Parameter(
                name=arg.__name__,
                kind=inspect.Parameter.POSITIONAL_OR_KEYWORD,
                default=orig_param.default if orig_param.default is not inspect.Parameter.empty else inspect.Parameter.empty,
                annotation=arg.__supertype__  # Use the base Python type
            )
            new_params.append(new_param)

        # Create wrapper function that returns raw structured data
        def wrapper(*args, **kwargs):
            result = method(*args, **kwargs)
            # Return raw data - FastMCP will serialize it
            return result

        # Set proper attributes
        wrapper.__name__ = tool_name
        wrapper.__doc__ = method.__doc__
        wrapper.__annotations__ = {p.name: p.annotation for p in new_params}
        # Don't set return type annotation - let FastMCP infer from actual data
        wrapper.__signature__ = inspect.Signature(new_params)

        # Register with FastMCP
        self.mcp.tool(name=tool_name)(wrapper)
        print(f"  Registered tool: {tool_name}")
