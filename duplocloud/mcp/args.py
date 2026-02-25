"""MCP server argument definitions.

Declarative argument definitions for the DuploCloud MCP server CLI.
Each argument is a dict with argparse kwargs plus env var binding.
A builder function constructs an ArgumentParser from these definitions.

Env var naming follows duploctl's DUPLO_ prefix convention.
"""

import argparse
import os


# Argument definitions as a list of dicts.
# Each dict contains:
#   - flags: positional args for add_argument
#   - env: primary env var name (or list for fallback chain)
#   - All other keys are argparse kwargs
ARGUMENTS = [
    {
        "flags": ["--transport"],
        "choices": ["stdio", "http"],
        "default": "http",
        "help": "The transport protocol to use (default: http)",
        "env": "DUPLO_MCP_TRANSPORT",
    },
    {
        "flags": ["--port"],
        "type": int,
        "default": 8000,
        "help": "The port to listen on for HTTP transport (default: 8000)",
        "env": ["DUPLO_MCP_PORT", "PORT"],
    },
    {
        "flags": ["--resource-filter"],
        "default": ".*",
        "help": "Regex pattern for resource names to include (default: .*)",
        "env": "DUPLO_MCP_RESOURCE_FILTER",
    },
    {
        "flags": ["--command-filter"],
        "default": ".*",
        "help": "Regex pattern for command names to include (default: .*)",
        "env": "DUPLO_MCP_COMMAND_FILTER",
    },
    {
        "flags": ["--tool-mode"],
        "choices": ["expanded", "compact"],
        "default": "expanded",
        "help": "Tool registration mode: expanded (one tool per resource+command) or compact (one tool per verb) (default: expanded)",
        "env": "DUPLO_MCP_TOOL_MODE",
    },
]


def _resolve_env_default(arg_def: dict):
    """Resolve the default value from environment variables.

    Checks env vars in order (supports fallback chains).
    Returns the first non-None env value, cast to the arg's type if needed.
    Falls back to the declared default.

    Args:
        arg_def: An argument definition dict.

    Returns:
        The resolved default value.
    """
    env = arg_def.get("env")
    if not env:
        return arg_def.get("default")

    # Normalize to list for fallback chain
    env_vars = [env] if isinstance(env, str) else env

    for var in env_vars:
        val = os.getenv(var)
        if val is not None:
            # Cast to the declared type if one exists
            cast = arg_def.get("type")
            return cast(val) if cast else val

    return arg_def.get("default")


def build_parser() -> argparse.ArgumentParser:
    """Build an ArgumentParser from the argument definitions.

    Returns:
        A configured ArgumentParser instance.
    """
    parser = argparse.ArgumentParser(
        description="DuploCloud MCP Server",
        prog="duplocloud-mcp",
    )
    for arg_def in ARGUMENTS:
        kwargs = {
            k: v
            for k, v in arg_def.items()
            if k not in ("flags", "env")
        }
        kwargs["default"] = _resolve_env_default(arg_def)
        parser.add_argument(*arg_def["flags"], **kwargs)
    return parser
