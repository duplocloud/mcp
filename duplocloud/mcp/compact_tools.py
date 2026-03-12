"""Compact-mode tools.

These custom tools only register when the server runs in compact mode.
Inspired by the duploctl bitbucket pipe pattern, compact mode exposes
four tools instead of one tool per resource+command:

- **resources**: List available resources matching the server's filter.
- **explain_resource**: List commands available on a resource.
- **explain_command**: Show arguments and body model schema for a command.
- **execute**: Run any duploctl command via DuploClient dispatch.

LLM workflow: resources → explain_resource → explain_command → execute.
"""

import re
from duplocloud.commander import commands_for, extract_args
from .ctx import Ctx, custom_tool


# Args that are first-class params in execute() and should be skipped
EXECUTE_FIRST_CLASS_ARGS = frozenset({"name", "body"})


@custom_tool(name="resources", mode="compact")
def resources(ctx: Ctx) -> list[str]:
    """List available DuploCloud resources.

    Returns the names of all resources that match the server's resource filter.
    Use these names with the explain_resource and execute tools.
    """
    return ctx.resources


@custom_tool(name="explain_resource", mode="compact")
def explain_resource(ctx: Ctx, resource: str) -> dict:
    """List all commands available on a DuploCloud resource.

    Returns each command name with a summary and aliases.
    Use the command names with explain_command for detailed argument info,
    or directly with execute.

    Use the resources tool to see all available resources.

    Args:
        resource: The resource name (e.g. "tenant", "service").
    """
    duplo = ctx.duplo

    if resource not in ctx.resources:
        return {"error": f"Resource '{resource}' is not available."}

    try:
        resource_obj = duplo.load(resource)
    except Exception as e:
        return {"error": f"Resource '{resource}' not found: {e}"}

    try:
        cmds = commands_for(resource)
    except Exception as e:
        return {"error": f"Commands not found for resource '{resource}': {e}"}

    result = {"resource": resource, "commands": {}}
    for cmd_name, cmd_info in cmds.items():
        method = getattr(resource_obj, cmd_name, None)
        summary = ""
        if method and method.__doc__:
            summary = method.__doc__.strip().split('\n')[0]

        result["commands"][cmd_name] = {
            "summary": summary,
            "aliases": cmd_info.get("aliases", []),
        }
    return result


@custom_tool(name="explain_command", mode="compact")
def explain_command(ctx: Ctx, resource: str, command: str) -> dict:
    """Explain a specific command's arguments and body schema.

    Returns detailed argument info and a JSON schema for the body when a
    Pydantic model is defined. Use this to understand what arguments the
    execute tool expects.

    Use the explain_resource tool to see available commands for a resource. 

    Args:
        resource: The resource name (e.g. "tenant", "service").
        command: The command name (e.g. "create", "find", "update_image").
    """
    duplo = ctx.duplo

    if resource not in ctx.resources:
        return {"error": f"Resource '{resource}' is not available."}

    # Load the resource first so the @Resource decorator fires and
    # populates the commander's `resources` registry before commands_for().
    try:
        resource_obj = duplo.load(resource)
    except Exception as e:
        return {"error": f"Resource '{resource}' not found: {e}"}

    try:
        cmds = commands_for(resource)
    except Exception as e:
        return {"error": f"Commands not found for resource '{resource}': {e}"}

    if command not in cmds:
        return {
            "error": f"Command '{command}' not found on resource '{resource}'.",
            "available": list(cmds.keys()),
        }

    cmd_info = cmds[command]
    method = getattr(resource_obj, command, None)
    if not method:
        return {"error": f"Method '{command}' not callable on resource '{resource}'."}

    # Build args schema, skipping first-class execute params (name, body)
    # Arg class provides: type_name, positional, default, attributes
    TYPE_MAP = {"str": "string", "int": "integer", "float": "number", "bool": "boolean"}
    args_properties = {}
    for arg in extract_args(method):
        param_name = arg.attributes.get("dest", arg.__name__)
        if param_name in EXECUTE_FIRST_CLASS_ARGS:
            continue
        prop = {"type": TYPE_MAP.get(arg.type_name, "string")}
        if arg.attributes.get("help"):
            prop["description"] = arg.attributes["help"]
        if arg.default is not None:
            prop["default"] = arg.default
        args_properties[param_name] = prop

    result = {
        "resource": resource,
        "command": command,
        "aliases": cmd_info.get("aliases", []),
        "args_schema": {
            "type": "object",
            "description": "Key-value pairs for the 'args' parameter in execute.",
            "properties": args_properties,
        },
        "docstring": method.__doc__ or "",
    }

    # Add model JSON schema when present
    model_name = cmd_info.get("model")
    if model_name:
        result["model"] = model_name
        model_cls = duplo.load_model(model_name)
        if model_cls and hasattr(model_cls, "model_json_schema"):
            result["body_schema"] = model_cls.model_json_schema(by_alias=True)

    return result


@custom_tool(name="execute", mode="compact")
def execute(
    ctx: Ctx,
    resource: str,
    command: str,
    name: str | None = None,
    args: dict = None,
    body: dict = None,
    query: str = None,
    wait: bool = False,
):
    """Execute a DuploCloud command. Use the explain_command tool first to
    understand what arguments a command expects.

    Dispatches through the DuploClient just like the CLI . 
    Commands that accept a body will automatically validate
    against the resource's model schema when available.

    Args:
        resource: The resource kind (e.g. "tenant", "service", "asg").
        command: The command to run (e.g. "create", "find", "list", "update").
        name: The resource name for commands that target a specific resource
            (e.g. find, delete, update). Most commands accept this.
        args: A map of additional command arguments as key-value pairs.
            The keys correspond to the argument names returned by the
            explain_command tool. For example: {"image": "nginx:latest"}.
        body: A dict payload for create/update commands. The schema depends
            on the resource — use explain_command to see the expected model
            fields.
        query: A jmespath expression to filter the command output.
        wait: Wait for the operation to complete before returning. Useful
            for create/update/delete commands that are asynchronous.
    """
    duplo = ctx.duplo

    if resource not in ctx.resources:
        return f"Error: Resource '{resource}' is not allowed by the resource filter."
    command_filter = re.compile(ctx.config.get("command_filter", ".*"))
    if not command_filter.fullmatch(command):
        return f"Error: Command '{command}' is not allowed by the command filter."

    duplo.wait = wait

    kwargs = dict(args) if args else {}
    if name is not None:
        kwargs["name"] = name
    if body is not None:
        kwargs["body"] = body

    try:
        return duplo(resource, command, query=query, **kwargs)
    except Exception as e:
        return f"Error: {e}"
