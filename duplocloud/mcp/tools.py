"""Tool registration for the DuploCloud MCP server.

The ToolRegistrar class owns the mechanics of turning duploctl @Command
methods into MCP tools. It handles signature rewriting, model resolution,
wrapper construction, and FastMCP registration.
"""

import inspect
import re

from duplocloud.client import DuploClient
from duplocloud.commander import commands_for, extract_args
from fastmcp import FastMCP
from fastmcp.utilities.logging import get_logger

from .utils import get_docstring_summary, resolve_docstring_template

logger = get_logger(__name__)

# Operations that should also be registered as MCP resources (future)
READ_OPERATIONS = {"list", "find", "logs", "pods"}


class ToolRegistrar:
    """Registers duploctl @Command methods as MCP tools.

    Holds references to the FastMCP instance, DuploClient, and the compiled
    command filter regex. Each public method does one thing and is
    independently testable.
    """

    def __init__(self, mcp: FastMCP, duplo: DuploClient, command_filter: re.Pattern):
        """Initialize the registrar.

        Args:
            mcp: The FastMCP instance to register tools on.
            duplo: The DuploCloud client instance.
            command_filter: Compiled regex for filtering command names.
        """
        self.mcp = mcp
        self.duplo = duplo
        self.command_filter = command_filter

    def register(self, resource_names: list[str]):
        """Register tools for a list of resources.

        Iterates over resource names, calling register_resource for each.
        Catches and logs errors per resource so one failure doesn't block others.

        Args:
            resource_names: List of resource names to register.
        """
        for resource_name in resource_names:
            try:
                self.register_resource(resource_name)
            except Exception as e:
                logger.error(f"Failed to register commands for {resource_name}: {e}")

    def register_resource(self, resource_name: str):
        """Register all matching commands from a single resource.

        Loads the resource, discovers commands via commands_for(), applies
        the command filter, and registers each passing command as a tool.

        Args:
            resource_name: The duploctl resource name (e.g. "tenant").
        """
        resource = self.duplo.load(resource_name)
        commands = commands_for(resource_name)

        logger.info("")
        logger.info(f"--- {resource_name}")

        for method_name, command_info in commands.items():
            if not self.command_filter.fullmatch(method_name):
                logger.debug(f"    skip {resource_name}_{method_name} (command filter)")
                continue

            method = getattr(resource, method_name, None)
            if not method or not callable(method):
                logger.warning(f"    Method '{method_name}' not found or not callable")
                continue

            self.register_tool(resource_name, method_name, method, command_info)

    def register_tool(self, resource_name: str, method_name: str, method, command_info: dict):
        """Register a single duploctl method as an MCP tool.

        Orchestrates param building, wrapper building, and FastMCP registration.

        Args:
            resource_name: The resource name.
            method_name: The method name.
            method: The bound method reference.
            command_info: The command schema dict from commands_for().
        """
        tool_name = f"{resource_name}_{method_name}"
        doc = method.__doc__ or ""
        resolved_doc = resolve_docstring_template(doc, resource_name)

        params = self.build_params(method, command_info)
        wrapper = self.build_wrapper(method, tool_name, resolved_doc, params)

        self.mcp.tool(name=tool_name, description=resolved_doc)(wrapper)

        doc_summary = get_docstring_summary(resolved_doc)
        logger.info(f"    {tool_name}{doc_summary}")

    def build_params(self, method, command_info: dict) -> list[inspect.Parameter]:
        """Build inspect.Parameter list for a tool wrapper.

        Extracts Arg annotations from the method and creates Parameter objects
        with base Python types. When command_info has a "model" key and the
        parameter is named "body", loads the Pydantic model class and uses it
        as the annotation instead of dict.

        Args:
            method: The duploctl method.
            command_info: The command schema dict (may contain "model" key).

        Returns:
            A list of inspect.Parameter objects for the wrapper signature.
        """
        cliargs = extract_args(method)
        if not cliargs:
            return []

        sig = inspect.signature(method)

        # Resolve model class if the command has one
        model_name = command_info.get("model")
        model_cls = self.duplo.load_model(model_name) if model_name else None

        params = []
        for arg in cliargs:
            # The Arg's dest attribute (if set) maps to the actual Python
            # parameter name. E.g. BODY has __name__="file" but dest="body".
            param_name = arg.attributes.get("dest", arg.__name__)
            orig_param = sig.parameters.get(param_name)
            if not orig_param:
                continue

            # Use Pydantic model for body params when available,
            # otherwise fall back to dict for file-type args
            annotation = arg.__supertype__
            if model_cls and param_name == "body":
                annotation = model_cls
            elif param_name == "body":
                annotation = dict

            param = inspect.Parameter(
                name=param_name,
                kind=inspect.Parameter.POSITIONAL_OR_KEYWORD,
                default=(
                    orig_param.default
                    if orig_param.default is not inspect.Parameter.empty
                    else inspect.Parameter.empty
                ),
                annotation=annotation,
            )
            params.append(param)

        return params

    def build_wrapper(self, method, tool_name: str, doc: str, params: list[inspect.Parameter]):
        """Build a wrapper function for a duploctl method.

        Creates a closure that calls the original method, sets __name__,
        __doc__, __signature__, and __annotations__ for FastMCP introspection.

        Args:
            method: The duploctl method to wrap.
            tool_name: The name for the tool (e.g. "tenant_create").
            doc: The resolved docstring.
            params: The inspect.Parameter list from build_params.

        Returns:
            The wrapper function with proper metadata.
        """
        def wrapper(*args, **kwargs):
            return method(*args, **kwargs)

        wrapper.__name__ = tool_name
        wrapper.__doc__ = doc

        if params:
            wrapper.__annotations__ = {p.name: p.annotation for p in params}
            wrapper.__signature__ = inspect.Signature(params)
        else:
            sig = inspect.signature(method)
            wrapper.__signature__ = sig
            wrapper.__annotations__ = method.__annotations__

        return wrapper
