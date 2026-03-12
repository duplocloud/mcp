# DuploCloud MCP Server

A [Model Context Protocol](https://modelcontextprotocol.io/) (MCP) server for DuploCloud. Dynamically discovers [`duploctl`](https://github.com/duplocloud/duploctl) commands and exposes them as MCP tools so AI agents and compatible clients can query infrastructure state and perform auditable actions.

Built on [FastMCP](https://gofastmcp.com) and the `duplocloud-client` Python package. Installs as a `duploctl` plugin — no separate command needed.

## Table of Contents

- [Features](#features)
- [Prerequisites](#prerequisites)
- [Installation](#installation)
- [Quick Start](#quick-start)
- [Configuration](#configuration)
  - [Environment Variables](#environment-variables)
  - [CLI Arguments](#cli-arguments)
- [Tool Modes](#tool-modes)
  - [Expanded Mode](#expanded-mode)
  - [Compact Mode](#compact-mode)
- [Filtering](#filtering)
  - [Resource Filter](#resource-filter)
  - [Command Filter](#command-filter)
  - [Combining Filters](#combining-filters)
- [MCP Client Configuration](#mcp-client-configuration)
- [Custom Tools and Routes](#custom-tools-and-routes)
- [Endpoints](#endpoints)
- [Docker](#docker)
- [Development](#development)
  - [Project Structure](#project-structure)
  - [Running Tests](#running-tests)
- [References](#references)

## Features

- **duploctl plugin** -- registers as a `duploctl` resource via entry points; run with `duploctl mcp`
- **Automatic tool discovery** -- all `duploctl` `@Command` methods are registered as MCP tools at startup
- **Resource and command filtering** -- regex-based filters to control which tools are exposed
- **Pydantic model integration** -- commands with models get typed input schemas instead of raw dicts
- **Config display** -- built-in `config` tool and `GET /config` route showing live server state
- **Custom tool/route framework** -- `@custom_tool` and `@custom_route` decorators with context injection
- **Dual transport** -- stdio (default) or HTTP for persistent servers

## Prerequisites

- Python 3.10+
- DuploCloud credentials (`DUPLO_HOST`, `DUPLO_TOKEN`)
- A DuploCloud tenant (`DUPLO_TENANT`)

## Installation

```bash
pip install duplocloud-mcp
```

For development:

```bash
git clone https://github.com/duplocloud/mcp.git
cd mcp
pip install -e ".[test]"
```

## Quick Start

Set your DuploCloud credentials and start the server:

```bash
export DUPLO_HOST="https://your-portal.duplocloud.net"
export DUPLO_TOKEN="your-token"
export DUPLO_TENANT="your-tenant"

duploctl mcp
```

By default the server starts in stdio transport with compact mode (3 tools). To use HTTP:

```bash
duploctl mcp --transport http
```

Verify it's running:

```bash
curl http://localhost:8000/health
# {"status":"healthy","service":"duplocloud-mcp"}

curl http://localhost:8000/config
# Full server configuration including registered tools
```

## Configuration

Every setting can be provided as a CLI argument or an environment variable. CLI arguments take precedence.

### Environment Variables

| Variable | Default | Description |
|---|---|---|
| `DUPLO_HOST` | -- | DuploCloud portal URL (required) |
| `DUPLO_TOKEN` | -- | Authentication token (required) |
| `DUPLO_TENANT` | -- | Tenant name (optional but recommended) |
| `DUPLO_MCP_TRANSPORT` | `stdio` | Transport protocol (`stdio` or `http`) |
| `DUPLO_MCP_PORT` | `8000` | Port for HTTP transport |
| `DUPLO_MCP_RESOURCE_FILTER` | `.*` | Regex filter for resource names |
| `DUPLO_MCP_COMMAND_FILTER` | `.*` | Regex filter for command names |
| `DUPLO_MCP_TOOL_MODE` | `compact` | Tool registration mode (`compact` or `expanded`) |

### CLI Arguments

```
duploctl mcp [--transport {stdio,http}]
             [--port PORT]
             [--resource-filter PATTERN]
             [--command-filter PATTERN]
             [--tool-mode {expanded,compact}]
```

All `duploctl` global arguments (`-H`, `-t`, `-T`, etc.) are also accepted and passed through to the DuploCloud client.

## Tool Modes

The `--tool-mode` flag controls how duploctl commands are exposed as MCP tools.

### Expanded Mode

Registers one tool per resource+command combination.

```bash
duploctl mcp --tool-mode expanded
```

Produces tools like `tenant_create`, `tenant_find`, `service_list`, etc. Each tool has its own input schema -- commands with Pydantic models (e.g. `tenant_create`) get full field-level schemas so the LLM sees every field name, type, and constraint.

- **Pro:** Precise schemas, easy for the LLM to call correctly
- **Con:** Many tools (potentially hundreds), may overwhelm tool selection

### Compact Mode

**Default.** Registers four tools total, inspired by the [duploctl bitbucket pipe](https://github.com/duplocloud/duploctl-pipe).

```bash
duploctl mcp --tool-mode compact
```

| Tool | Purpose |
|---|---|
| `resources` | List available resources (filtered) |
| `explain_resource` | List commands available on a resource |
| `explain_command` | Show arguments and body model schema for a specific command |
| `execute` | Run any duploctl command |

The intended LLM workflow:

1. **`resources`** -- get the list of available resources
2. **`explain_resource(resource)`** -- see what commands are available
3. **`explain_command(resource, command)`** -- see argument details and body schema
4. **`execute(resource, command, ...)`** -- run the command

The `execute` tool accepts `name`, `args`, `body`, `query`, and `wait` parameters. It dispatches through the same `DuploClient` path as the CLI, so model validation, filtering, and formatting all work the same way.

- **Pro:** Only 4 tools, works well with tool-count-limited clients
- **Con:** LLM needs multiple calls to discover schemas

## Filtering

Filters use Python regex with `fullmatch` semantics -- the entire name must match the pattern.

### Resource Filter

Expose only specific resource types:

```bash
# Only tenant tools
duploctl mcp --resource-filter "tenant"

# Tenant and service tools
duploctl mcp --resource-filter "tenant|service"

# Everything related to batch
duploctl mcp --resource-filter "batch_.*"

# All resources (default)
duploctl mcp --resource-filter ".*"
```

Via environment variable:

```bash
export DUPLO_MCP_RESOURCE_FILTER="tenant|service|s3"
duploctl mcp
```

### Command Filter

Expose only specific operations across all resources:

```bash
# Read-only -- only list and find commands
duploctl mcp --command-filter "list|find"

# Only create and delete
duploctl mcp --command-filter "create|delete"
```

### Combining Filters

Filters compose as an intersection. This exposes only list and find for tenant and service:

```bash
duploctl mcp \
  --resource-filter "tenant|service" \
  --command-filter "list|find"
```

Result: `tenant_list`, `tenant_find`, `service_list`, `service_find`.

## MCP Client Configuration

### stdio Transport (Default)

For most MCP clients (Claude Code, VS Code, etc.), use stdio transport. Add to your `.mcp.json` (project root) or `.vscode/mcp.json`:

```json
{
  "mcpServers": {
    "duploctl": {
      "command": "duploctl",
      "args": ["mcp"],
      "env": {
        "DUPLO_HOST": "https://your-portal.duplocloud.net",
        "DUPLO_TOKEN": "your-token",
        "DUPLO_TENANT": "your-tenant"
      }
    }
  }
}
```

### HTTP Transport

For clients that connect over HTTP (persistent server):

```bash
duploctl mcp --transport http
```

```json
{
  "mcpServers": {
    "duploctl": {
      "url": "http://localhost:8000/mcp",
      "type": "http"
    }
  }
}
```

### With Filters

```json
{
  "mcpServers": {
    "duploctl": {
      "command": "duploctl",
      "args": ["mcp", "--resource-filter", "tenant|service"],
      "env": {
        "DUPLO_HOST": "https://your-portal.duplocloud.net",
        "DUPLO_TOKEN": "your-token",
        "DUPLO_TENANT": "your-tenant"
      }
    }
  }
}
```

## Custom Tools and Routes

The `@custom_tool` and `@custom_route` decorators let you add ad-hoc tools and HTTP routes that receive a `Ctx` object with the DuploCloud client and server config injected.

```python
from duplocloud.mcp.ctx import Ctx, custom_tool, custom_route
from starlette.requests import Request
from starlette.responses import JSONResponse

# A plain function that does the work
def get_status(ctx: Ctx) -> dict:
    tenants = ctx.duplo.load("tenant").list()
    return {
        "tenant_count": len(tenants),
        "tools": ctx.tools,
    }

# Expose as an MCP tool
@custom_tool(name="status", description="Get environment status.")
def status_tool(ctx: Ctx) -> dict:
    return get_status(ctx)

# Expose the same logic as an HTTP route
@custom_route("/status", methods=["GET"])
async def status_route(ctx: Ctx, request: Request):
    return JSONResponse(get_status(ctx))
```

The `ctx` parameter is injected automatically and hidden from the tool's input schema -- MCP clients never see it.

### Mode Selector

Decorators accept an optional `mode` parameter to conditionally register based on server mode:

```python
@custom_tool(name="debug_info", mode="debug")
def debug_info(ctx: Ctx) -> dict:
    """Only registered when the server runs in debug mode."""
    return {"config": ctx.config}
```

## Endpoints

| Endpoint | Method | Description |
|---|---|---|
| `/mcp` | POST | MCP protocol endpoint (StreamableHTTP) |
| `/health` | GET | Health check for load balancers |
| `/config` | GET | Live server configuration and registered tools |

## Docker

The Docker image uses `duploctl mcp` as its entrypoint. Pass arguments via `CMD` or at runtime:

```bash
# Default (stdio transport, compact mode)
docker run -e DUPLO_HOST=... -e DUPLO_TOKEN=... -e DUPLO_TENANT=... duplocloud-mcp

# HTTP transport
docker run -e DUPLO_HOST=... -e DUPLO_TOKEN=... -e DUPLO_TENANT=... duplocloud-mcp --transport http

# Expanded mode with filters
docker run -e DUPLO_HOST=... -e DUPLO_TOKEN=... -e DUPLO_TENANT=... duplocloud-mcp \
  --tool-mode expanded --resource-filter "tenant|service"
```

## Development

### Project Structure

```
duplocloud/mcp/
  __main__.py        # Legacy entrypoint (use duploctl mcp instead)
  app.py             # FastMCP instance and health route
  args.py            # Declarative CLI argument definitions (legacy)
  ctx.py             # Ctx dataclass, @custom_tool, @custom_route
  config_display.py  # Built-in config tool and route
  server.py          # DuploCloudMCP resource plugin and lifecycle coordinator
  tools.py           # ToolRegistrar (duploctl -> MCP tool conversion)
  compact_tools.py   # Compact mode tools (execute, explain, resources)
  utils.py           # Docstring template resolution
tests/
  conftest.py        # Shared fixtures
  test_args.py       # Argument parsing and env var binding
  test_ctx.py        # Ctx, decorators, drain functions
  test_custom.py     # Context injection, register_custom, build_config
  test_filters.py    # Regex filter matching behavior
  test_server.py     # DuploCloudMCP init, filter application, self-exclusion
  test_modes.py      # Expanded and compact mode tests
  test_tools.py      # ToolRegistrar param building and wrapper construction
```

### Running Tests

```bash
pip install -e ".[test]"
pytest
```

## References

- [duploctl](https://github.com/duplocloud/duploctl) -- CLI and Python client for DuploCloud
- [Model Context Protocol](https://modelcontextprotocol.io/) -- MCP specification
- [FastMCP](https://gofastmcp.com) -- Framework powering this server
- [Keep a Changelog](https://keepachangelog.com/en/1.1.0/)
- [Semantic Versioning](https://semver.org/spec/v2.0.0.html)
