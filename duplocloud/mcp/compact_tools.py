"""Compact-mode tools.

These custom tools only register when the server runs in compact mode.
Inspired by the duploctl bitbucket pipe pattern, compact mode exposes
three tools instead of one tool per resource+command:

- **resources**: List available resources matching the server's filter.
- **explain**: Show commands for a resource with args, body model, and docs.
- **execute**: Run any duploctl command via DuploClient dispatch.

LLM workflow: resources → explain → execute.
"""

import re
import typing
from typing import get_args, get_origin

from pydantic import BaseModel
from duplocloud.commander import commands_for, extract_args

from .ctx import Ctx, custom_tool


def _friendly_type(annotation) -> str:
    """Simplify a typing annotation into a readable string.
    
    Examples:
        typing.Optional[typing.Annotated[str, Strict(strict=True)]] -> "str (optional)"
        typing.Optional[V1ObjectMeta] -> "V1ObjectMeta (optional)"
        typing.Dict[str, str] -> "dict[str, str]"
    """
    if annotation is None:
        return "any"
    
    origin = get_origin(annotation)
    args = get_args(annotation)
    
    # Optional[X] is Union[X, None]
    if origin is typing.Union:
        non_none = [a for a in args if a is not type(None)]
        if len(non_none) == 1:
            return f"{_friendly_type(non_none[0])} (optional)"
        return " | ".join(_friendly_type(a) for a in non_none)
    
    # Annotated[X, ...] — unwrap to just X
    if origin is typing.Annotated or str(origin) == "typing.Annotated":
        return _friendly_type(args[0]) if args else str(annotation)
    
    # Generic types like Dict, List
    if origin is dict:
        if args:
            return f"dict[{_friendly_type(args[0])}, {_friendly_type(args[1])}]"
        return "dict"
    if origin is list:
        if args:
            return f"list[{_friendly_type(args[0])}]"
        return "list"
    
    # Plain types
    if hasattr(annotation, "__name__"):
        return annotation.__name__
    
    return str(annotation)


def _describe_model_fields(model_cls, duplo) -> dict:
    """Extract field descriptions from a Pydantic model, recursing into nested models."""
    if not hasattr(model_cls, "model_fields"):
        return {}
    fields = {}
    for field_name, field_info in model_cls.model_fields.items():
        field_entry = {}
        if field_info.annotation is not None:
            field_entry["type"] = _friendly_type(field_info.annotation)
        if field_info.is_required():
            field_entry["required"] = True
        if field_info.description:
            field_entry["description"] = field_info.description
        if field_info.alias:
            field_entry["alias"] = field_info.alias
        
        # Recurse into nested Pydantic models
        inner = field_info.annotation
        # Unwrap Optional/Annotated to find the core type
        while get_origin(inner) in (typing.Union, typing.Annotated) or str(get_origin(inner)) == "typing.Annotated":
            inner_args = get_args(inner)
            non_none = [a for a in inner_args if a is not type(None)]
            inner = non_none[0] if non_none else inner
            if get_origin(inner) is not typing.Union:
                # For Annotated, take first arg
                if get_origin(inner) is typing.Annotated or str(get_origin(inner)) == "typing.Annotated":
                    inner = get_args(inner)[0] if get_args(inner) else inner
                else:
                    break
        
        if isinstance(inner, type) and issubclass(inner, BaseModel) and hasattr(inner, "model_fields"):
            field_entry["fields"] = _describe_model_fields(inner, duplo)
        
        fields[field_name] = field_entry
    return fields


@custom_tool(name="resources", mode="compact")
def resources(ctx: Ctx) -> dict:
    """List available DuploCloud resources.

    Returns the names of all resources that match the server's resource filter.
    Use these names with the explain and execute tools.
    """
    return {"resources": ctx.resources}


@custom_tool(name="explain", mode="compact")
def explain(ctx: Ctx, resource: str, command: str = None) -> dict:
    """Explain a DuploCloud resource's commands, arguments, and body schema.

    Without a command, returns all commands available on the resource.
    With a command, returns detailed argument info including body model
    fields when a Pydantic model is defined. Use this to understand what
    arguments the execute tool expects for a given resource and command.

    Args:
        resource: The resource name (e.g. "tenant", "service").
        command: Optional specific command to get detailed argument info for.
    """
    duplo = ctx.duplo
    
    # Load resource first to ensure it's imported and registered
    try:
        resource_obj = duplo.load(resource)
    except Exception as e:
        return {"error": f"Resource '{resource}' not found: {e}"}
    
    try:
        cmds = commands_for(resource)
    except Exception as e:
        return {"error": f"Commands not found for resource '{resource}': {e}"}

    if command is None:
        # Resource-level explanation: list commands with summary lines
        result = {"resource": resource, "commands": {}}
        for cmd_name, cmd_info in cmds.items():
            method = getattr(resource_obj, cmd_name, None)
            # Extract first line of docstring as summary
            summary = ""
            if method and method.__doc__:
                summary = method.__doc__.strip().split('\n')[0]
            
            result["commands"][cmd_name] = {
                "summary": summary,
                "aliases": cmd_info.get("aliases", []),
            }
        return result

    if command not in cmds:
        return {
            "error": f"Command '{command}' not found on resource '{resource}'.",
            "available": list(cmds.keys()),
        }

    cmd_info = cmds[command]
    resource_obj = duplo.load(resource)
    method = getattr(resource_obj, command, None)
    if not method:
        return {"error": f"Method '{command}' not callable on resource '{resource}'."}

    cliargs = extract_args(method)
    args_info = []
    model_name = cmd_info.get("model")
    
    for arg in cliargs:
        param_name = arg.attributes.get("dest", arg.__name__)
        
        # Special case for body parameter when a model is defined
        if param_name == "body" and model_name:
            info = {
                "name": param_name,
                "type": model_name,
                "help": "See model fields below for schema details",
            }
        else:
            # Get type name safely - some types like FileType don't have __name__
            supertype = getattr(arg, "__supertype__", str)
            try:
                type_name = supertype.__name__
            except AttributeError:
                type_name = str(supertype)
            
            info = {
                "name": param_name,
                "type": type_name,
                "help": arg.attributes.get("help", ""),
            }
        
        if "default" in arg.attributes:
            info["default"] = str(arg.attributes["default"])
        args_info.append(info)

    result = {
        "resource": resource,
        "command": command,
        "aliases": cmd_info.get("aliases", []),
        "args": args_info,
        "docstring": method.__doc__ or "",
    }

    if model_name:
        result["model"] = model_name
        model_cls = duplo.load_model(model_name)
        if model_cls:
            result["model_fields"] = _describe_model_fields(model_cls, duplo)

    return result


@custom_tool(name="execute", mode="compact")
def execute(
    ctx: Ctx,
    resource: str,
    command: str,
    name: str = None,
    args: list[str] = None,
    body: dict = None,
    query: str = None,
    output: str = None,
    wait: bool = False,
) -> str:
    """Execute a DuploCloud command. Use the explain tool first to understand
    what arguments a command expects.

    Dispatches through the DuploClient just like the CLI and the duploctl
    bitbucket pipe. Commands that accept a body will automatically validate
    against the resource's model schema when available.

    Args:
        resource: The resource kind (e.g. "tenant", "service", "asg").
        command: The command to run (e.g. "create", "find", "list", "update").
        name: The resource name. Optional even when the command requires it
            because some commands can infer the name from the body object.
            For example, find requires a name, but create may not.
        args: Additional positional arguments as a list of strings. Most
            commands do not need this. Use explain to check.
        body: A dict payload for create/update commands. The schema depends
            on the resource — use explain to see the expected model fields.
        query: A jmespath expression to filter the command output.
        output: Output format override — "json", "yaml", or "string".
        wait: Wait for the operation to complete before returning. Useful
            for create/update/delete commands that are asynchronous.
    """
    duplo = ctx.duplo

    if resource not in ctx.resources:
        return f"Error: Resource '{resource}' is not allowed by the resource filter."
    command_filter = re.compile(ctx.config.get("command_filter", ".*"))
    if not command_filter.fullmatch(command):
        return f"Error: Command '{command}' is not allowed by the command filter."

    # Save and temporarily override global options
    orig_query = duplo.query
    orig_output = duplo.output
    orig_wait = duplo.wait
    try:
        if query is not None:
            duplo.query = query
        if output is not None:
            duplo.output = output
        if wait:
            duplo.wait = True

        if body is not None:
            # For commands with body, dispatch through resource.command()
            # which handles arg parsing and model validation.
            resource_obj = duplo.load(resource)
            cmd_fn = resource_obj.command(command)
            result = cmd_fn(body=body)
            if result is not None:
                result = duplo.filter(result)
                return duplo.format(result)
            return ""

        # Build the positional args list like the pipe does:
        # duplo(resource, command, name, *args)
        call_args = [command]
        if name is not None:
            call_args.append(name)
        if args:
            call_args.extend(args)

        result = duplo(resource, *call_args)
        return result if result is not None else ""
    except Exception as e:
        return f"Error: {e}"
    finally:
        duplo.query = orig_query
        duplo.output = orig_output
        duplo.wait = orig_wait
