import os
import inspect
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

    # Define which operations are read-only (resources) vs write operations (tools)
    READ_OPERATIONS = {'list', 'find', 'logs', 'pods'}
    WRITE_OPERATIONS = {'create', 'update', 'delete', 'apply', 'restart', 'start', 'stop',
                        'expose', 'rollback', 'update_replicas', 'update_image', 'update_env',
                        'update_pod_label', 'bulk_update_image', 'update_otherdockerconfig'}

    def __init__(self,
                 name: str = "duplocloud-mcp"):
        """
        Initialize the DuploCloud MCP server.
        """
        self.mcp = FastMCP(
            name=name,
            version=version("duplocloud-mcp"),
        )
        duplo, args = DuploClient.from_env()
        self.duplo = duplo

    def start(self):
        """
        Start the MCP server.
        """
        # Log environment details
        yaml_formatter = load_format("yaml")
        formatted_info = yaml_formatter(self.duplo.config)
        logger.info(f"DuploCloud Environment Info:\n{formatted_info}")

        self.mcp.run(
            transport="http",
            host="0.0.0.0",
            port=int(os.getenv("PORT", 8000))
        )

    def register_tools(self):
        """
        Register DuploCloud tools and resources with the MCP.

        Uses the duploctl schema to identify @Command decorated methods
        and register them appropriately.
        """
        # Register service resource commands
        self._register_resource_commands("service")

    def _register_resource_commands(self, resource_name: str):
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

            # Determine if this is a read or write operation
            if method_name in self.READ_OPERATIONS:
                self._register_as_resource(resource_name, method_name, method)
            elif method_name in self.WRITE_OPERATIONS:
                self._register_as_tool(resource_name, method_name, method)
            else:
                print(
                    f"  Skipping '{method_name}' (not in READ_OPERATIONS or WRITE_OPERATIONS)")

    def _register_as_resource(self, resource_name: str, method_name: str, method):
        """
        Register a duploctl method as an MCP resource (read-only operation).

        For now, we register read operations as tools instead of resources
        since resources require complex URI template handling. This is a 
        simplified approach that still works.

        Args:
            resource_name: The duploctl resource name
            method_name: The method name
            method: The method reference with preserved signature
        """
        # For simplicity, register read operations as tools
        # They will still be read-only operations, just not URI-based resources
        print(
            f"  Registering read operation as tool: {resource_name}_{method_name}")
        self._register_as_tool(resource_name, method_name, method)

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
