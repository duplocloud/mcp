# Transport Configuration Research Report

**Date:** November 25, 2025  
**Author:** GitHub Copilot  
**Branch:** duploctl-service  
**Status:** Research Complete

## Executive Summary

This report documents research into FastMCP transport protocols and configuration patterns to enable flexible transport configuration for the DuploCloud MCP server. The goal is to leverage argparse (consistent with duploctl patterns) along with environment variables and config files to control transport options (stdio, http, streamable-http).

## Key Findings

### 1. Transport Protocol Clarification

#### The "http" vs "streamable-http" Mystery

The FastMCP documentation and hover tooltips can be confusing about transport options. Here's the truth:

- **`transport="http"`** → Uses `StreamableHttpTransport` (modern bidirectional protocol)
- **`transport="streamable-http"`** → Also uses `StreamableHttpTransport` (same as "http")
- **Both are aliases for the same transport implementation**

**Source Evidence:**
```python
# From fastmcp/server/server.py line 421
if transport in {"http", "sse", "streamable-http"}:
    await self.run_http_async(
        transport=transport,
        show_banner=show_banner,
        **transport_kwargs,
    )
```

The hover docs listing "streamable-http" or "stdio" but not showing "http" is misleading - "http" is fully supported and is the preferred term going forward.

#### Transport Protocol Comparison

| Transport | Use Case | Client Behavior | Bidirectional |
|-----------|----------|-----------------|---------------|
| **stdio** (default) | Local command-line tools, Claude Desktop, VS Code | Client spawns server process on-demand | Yes |
| **http / streamable-http** | Web services, remote deployment, multi-client | Persistent server, multiple concurrent clients | Yes |
| **sse** (legacy) | Backward compatibility only | Client connects to persistent server | No (server→client only) |

**Recommendation:** Support both `stdio` and `http` transports. The terms "http" and "streamable-http" are interchangeable.

### 2. FastMCP Configuration Capabilities

#### What FastMCP Provides

FastMCP has **NO built-in argparse support**, but provides several configuration mechanisms:

1. **Environment Variables** (prefixed with `FASTMCP_`)
   ```bash
   export FASTMCP_LOG_LEVEL=DEBUG
   export FASTMCP_MASK_ERROR_DETAILS=True
   ```

2. **`run()` Method Parameters**
   ```python
   mcp.run(
       transport="http",
       host="0.0.0.0",
       port=8000,
       log_level="DEBUG"
   )
   ```

3. **FastMCP CLI** (uses `cyclopts`, not argparse)
   ```bash
   fastmcp run server.py --transport http --port 8000
   ```

4. **Config Files** (`fastmcp.json` pattern)
   ```json
   {
     "deployment": {
       "transport": "http",
       "host": "0.0.0.0",
       "port": 8000
     }
   }
   ```

#### FastMCP CLI Pass-Through Pattern

**Critical Discovery:** FastMCP CLI documentation explicitly states:

> "When servers accept command line arguments (using argparse, click, or other libraries), you can pass them after `--`"

Example:
```bash
fastmcp run server.py -- --config config.json --debug
#                      ^^
#                      Everything after -- goes to your server
```

**This means FastMCP expects servers to implement their own argument parsing.**

### 3. Duploctl's Argparse Pattern

Duploctl uses a sophisticated, well-architected pattern that we should leverage:

#### Pattern Components

1. **`@Command()` Decorator**
   - Tracks all CLI commands in a global `schema` registry
   - Associates methods with their class and any aliases

2. **Custom `Arg` Types**
   - Extends base Python types with CLI metadata
   - Examples: `args.HOST`, `args.TOKEN`, `args.TENANT`
   - Each `Arg` knows its flags, defaults, and attributes

3. **`extract_args()` Function**
   - Inspects function signatures for `Arg` annotations
   - Extracts only the CLI-relevant parameters
   - Returns a list of `Arg` objects

4. **`get_parser()` Function**
   - Takes a list of `Arg` objects
   - Creates an `ArgumentParser` with proper configuration
   - Returns a fully-configured parser

5. **`from_env()` Pattern**
   ```python
   @staticmethod
   def from_env():
       a = extract_args(DuploClient.__init__)
       p = get_parser(a)
       env, xtra = p.parse_known_args()  # ← parse_known_args!
       duplo = DuploClient(**vars(env))
       return duplo, xtra
   ```

#### Key Advantage: Separation of Concerns

The duploctl pattern already separates:
- **Global client config** (host, token, tenant) → `DuploClient.__init__` args
- **Command-specific args** → Individual command method args
- **Unknown args** → Returned via `parse_known_args()` for further processing

This is **perfect** for MCP server configuration because we need:
- Server transport config (transport, host, port)
- DuploCloud client config (host, token, tenant)
- Potential future extensions

### 4. MCP Ecosystem Standards

Based on MCP protocol documentation and FastMCP client/server patterns:

#### Expected Transports

- **STDIO**: Primary transport for local tools
  - Used by Claude Desktop, VS Code MCP extensions
  - Client spawns server process per session
  - Server reads from stdin, writes to stdout

- **HTTP/Streamable-HTTP**: Primary transport for web services
  - Used for remote deployments
  - Supports multiple concurrent clients
  - Provides full bidirectional communication

#### Configuration Priority Order (Industry Standard)

1. **Command-line arguments** (highest priority)
2. **Environment variables**
3. **Config files**
4. **Defaults** (lowest priority)

This is the standard established by tools like Docker, Kubernetes, AWS CLI, etc.

## Recommended Architecture

### ServerConfig Class Design

```python
"""
duplocloud/mcp/config.py

Server configuration handler that integrates with duploctl's argparse patterns.
"""

import os
import argparse
from typing import Literal, Optional
from duplocloud.commander import get_parser, extract_args
from duplocloud import args as duplo_args

TransportType = Literal["stdio", "http", "streamable-http", "sse"]

class ServerConfig:
    """
    Configuration handler for DuploCloud MCP Server.
    
    Handles configuration from multiple sources with priority:
    1. Command-line arguments (highest)
    2. Environment variables
    3. Config files (future)
    4. Defaults (lowest)
    
    Integrates with duploctl's argparse patterns for consistency.
    """
    
    def __init__(
        self,
        # Transport configuration
        transport: TransportType = "stdio",
        host: str = "0.0.0.0",
        port: int = 8000,
        path: str = "/mcp",
        
        # Server behavior
        log_level: str = "INFO",
        
        # DuploCloud client configuration (from environment)
        duplo_host: Optional[str] = None,
        duplo_token: Optional[str] = None,
        duplo_tenant: Optional[str] = None,
    ):
        """
        Initialize server configuration.
        
        Args:
            transport: Transport protocol (stdio, http, streamable-http, sse)
            host: Host to bind to for HTTP transport
            port: Port to bind to for HTTP transport
            path: URL path for MCP endpoint
            log_level: Logging level
            duplo_host: DuploCloud API host (usually from env)
            duplo_token: DuploCloud API token (usually from env)
            duplo_tenant: DuploCloud tenant (usually from env)
        """
        # Normalize transport aliases
        if transport == "streamable-http":
            transport = "http"
            
        self.transport = transport
        self.host = host
        self.port = port
        self.path = path
        self.log_level = log_level
        
        # DuploCloud configuration
        self.duplo_host = duplo_host
        self.duplo_token = duplo_token
        self.duplo_tenant = duplo_tenant
    
    @classmethod
    def from_args_and_env(cls, args: Optional[list[str]] = None) -> 'ServerConfig':
        """
        Create configuration from command-line arguments and environment variables.
        
        Priority: CLI args > Environment variables > Defaults
        
        Args:
            args: Command-line arguments (uses sys.argv if None)
            
        Returns:
            ServerConfig instance
        """
        parser = cls._create_parser()
        
        if args is None:
            parsed_args = parser.parse_args()
        else:
            parsed_args = parser.parse_args(args)
        
        # Get DuploCloud config from environment (following duploctl pattern)
        duplo_host = parsed_args.duplo_host or os.getenv("DUPLO_HOST")
        duplo_token = parsed_args.duplo_token or os.getenv("DUPLO_TOKEN")
        duplo_tenant = parsed_args.duplo_tenant or os.getenv("DUPLO_TENANT")
        
        # Get server config with priority: args > env > defaults
        transport = parsed_args.transport or os.getenv("MCP_TRANSPORT", "stdio")
        host = parsed_args.host or os.getenv("MCP_HOST", "0.0.0.0")
        port = parsed_args.port or int(os.getenv("PORT", os.getenv("MCP_PORT", "8000")))
        path = parsed_args.path or os.getenv("MCP_PATH", "/mcp")
        log_level = parsed_args.log_level or os.getenv("MCP_LOG_LEVEL", "INFO")
        
        return cls(
            transport=transport,
            host=host,
            port=port,
            path=path,
            log_level=log_level,
            duplo_host=duplo_host,
            duplo_token=duplo_token,
            duplo_tenant=duplo_tenant,
        )
    
    @classmethod
    def from_env_only(cls) -> 'ServerConfig':
        """
        Create configuration from environment variables only.
        
        This is the current behavior - maintains backward compatibility.
        
        Returns:
            ServerConfig instance
        """
        return cls(
            transport=os.getenv("MCP_TRANSPORT", "stdio"),
            host=os.getenv("MCP_HOST", "0.0.0.0"),
            port=int(os.getenv("PORT", os.getenv("MCP_PORT", "8000"))),
            path=os.getenv("MCP_PATH", "/mcp"),
            log_level=os.getenv("MCP_LOG_LEVEL", "INFO"),
            duplo_host=os.getenv("DUPLO_HOST"),
            duplo_token=os.getenv("DUPLO_TOKEN"),
            duplo_tenant=os.getenv("DUPLO_TENANT"),
        )
    
    @staticmethod
    def _create_parser() -> argparse.ArgumentParser:
        """
        Create argument parser for server configuration.
        
        Returns:
            Configured ArgumentParser
        """
        parser = argparse.ArgumentParser(
            prog="duplocloud-mcp",
            description="DuploCloud MCP Server - exposes DuploCloud operations via MCP protocol",
            epilog="Environment variables: DUPLO_HOST, DUPLO_TOKEN, DUPLO_TENANT, MCP_TRANSPORT, MCP_HOST, MCP_PORT, MCP_PATH, MCP_LOG_LEVEL",
        )
        
        # Transport configuration
        transport_group = parser.add_argument_group("Transport Configuration")
        transport_group.add_argument(
            "--transport", "-t",
            choices=["stdio", "http", "streamable-http", "sse"],
            help="Transport protocol (default: stdio for CLI, http for Docker)",
        )
        transport_group.add_argument(
            "--host",
            help="Host to bind to for HTTP transport (default: 0.0.0.0)",
        )
        transport_group.add_argument(
            "--port", "-p",
            type=int,
            help="Port to bind to for HTTP transport (default: 8000)",
        )
        transport_group.add_argument(
            "--path",
            help="URL path for MCP endpoint (default: /mcp)",
        )
        
        # Server behavior
        behavior_group = parser.add_argument_group("Server Behavior")
        behavior_group.add_argument(
            "--log-level", "-l",
            choices=["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"],
            help="Logging level (default: INFO)",
        )
        
        # DuploCloud configuration (optional overrides)
        duplo_group = parser.add_argument_group("DuploCloud Configuration")
        duplo_group.add_argument(
            "--duplo-host",
            help="DuploCloud API host (default: from DUPLO_HOST env var)",
        )
        duplo_group.add_argument(
            "--duplo-token",
            help="DuploCloud API token (default: from DUPLO_TOKEN env var)",
        )
        duplo_group.add_argument(
            "--duplo-tenant",
            help="DuploCloud tenant (default: from DUPLO_TENANT env var)",
        )
        
        return parser
    
    def to_run_kwargs(self) -> dict:
        """
        Convert configuration to kwargs for FastMCP.run() method.
        
        Returns:
            Dictionary of kwargs for mcp.run()
        """
        kwargs = {
            "transport": self.transport,
            "log_level": self.log_level,
        }
        
        # Only include host/port/path for HTTP transports
        if self.transport in ("http", "streamable-http", "sse"):
            kwargs["host"] = self.host
            kwargs["port"] = self.port
            kwargs["path"] = self.path
        
        return kwargs
```

### Updated DuploCloudMCP Class

```python
"""
duplocloud/mcp/server.py

Updated to use ServerConfig for flexible configuration.
"""

class DuploCloudMCP():
    """DuploCloud MCP wrapper for duploctl commands."""
    
    READ_OPERATIONS = {'list', 'find', 'logs', 'pods'}

    def __init__(self, config: Optional[ServerConfig] = None):
        """
        Initialize the DuploCloud MCP server.
        
        Args:
            config: Server configuration (uses env vars if None)
        """
        # Use provided config or create from environment
        self.config = config or ServerConfig.from_env_only()
        
        # Initialize FastMCP
        self.mcp = FastMCP(
            name="duplocloud-mcp",
            version=version("duplocloud-mcp"),
        )
        
        # Initialize DuploCloud client with env vars (existing pattern)
        # Note: DuploClient.from_env() already handles env var precedence
        duplo, args = DuploClient.from_env()
        self.duplo = duplo

    def start(self):
        """Start the MCP server with configured transport."""
        # Log environment details
        yaml_formatter = load_format("yaml")
        formatted_info = yaml_formatter(self.duplo.config)
        logger.info(f"DuploCloud Environment Info:\n{formatted_info}")
        
        # Log transport configuration
        logger.info(f"Starting MCP server with transport: {self.config.transport}")
        if self.config.transport in ("http", "streamable-http"):
            logger.info(f"Server will be available at http://{self.config.host}:{self.config.port}{self.config.path}")
        
        # Start server with configuration
        self.mcp.run(**self.config.to_run_kwargs())
```

### Updated __main__.py

```python
"""
duplocloud/mcp/__main__.py

Updated to parse arguments and use ServerConfig.
"""

import sys
from .server import DuploCloudMCP
from .config import ServerConfig

def main():
    """Main entry point with argument parsing."""
    try:
        # Parse configuration from args and environment
        config = ServerConfig.from_args_and_env()
        
        # Create and configure server
        print("Starting DuploCloud MCP Server...")
        server = DuploCloudMCP(config=config)
        
        # Register all tools and resources
        print("Registering DuploCloud tools and resources...")
        server.register_tools()
        
        # Start the server
        print("MCP Server ready!")
        server.start()
        return 0
        
    except KeyboardInterrupt:
        print("\nServer interrupted. Shutting down gracefully...")
        return 0
    except Exception as e:
        print(f"Error starting MCP server: {e}")
        return 1

if __name__ == "__main__":
    sys.exit(main())
```

## Usage Examples

### As a Command-Line Tool (STDIO)

```bash
# Default: STDIO transport, reads config from environment
duplocloud-mcp

# With explicit configuration
duplocloud-mcp --transport stdio --log-level DEBUG
```

### As a Web Service (HTTP)

```bash
# HTTP transport with custom port
duplocloud-mcp --transport http --host 0.0.0.0 --port 8080

# All configuration via environment variables
export MCP_TRANSPORT=http
export MCP_HOST=0.0.0.0
export MCP_PORT=8000
export DUPLO_HOST=https://your-instance.duplocloud.net
export DUPLO_TOKEN=your-token
export DUPLO_TENANT=your-tenant
duplocloud-mcp
```

### Via FastMCP CLI (Pass-Through)

```bash
# FastMCP CLI passes args after -- to our server
fastmcp run duplocloud.mcp:server -- --transport http --port 8080

# Or let FastMCP handle transport, pass other config to server
fastmcp run duplocloud.mcp:server --transport http --port 8080 -- --log-level DEBUG
```

### Docker Compose

```yaml
services:
  duplocloud-mcp:
    build: .
    environment:
      - DUPLO_HOST=${DUPLO_HOST}
      - DUPLO_TOKEN=${DUPLO_TOKEN}
      - DUPLO_TENANT=${DUPLO_TENANT}
      - MCP_TRANSPORT=http
      - MCP_HOST=0.0.0.0
      - MCP_PORT=8000
      - MCP_LOG_LEVEL=INFO
    ports:
      - "8000:8000"
    command: ["duplocloud-mcp"]  # Uses env vars
```

## Benefits of This Approach

1. **Consistency**: Follows duploctl's established argparse patterns
2. **Flexibility**: Supports CLI args, env vars, and future config files
3. **Backward Compatibility**: Existing env-var-only usage still works
4. **Ecosystem Compatibility**: Works with FastMCP CLI pass-through pattern
5. **Clear Priority**: Explicit precedence order (args > env > defaults)
6. **Docker-Friendly**: Environment variables work perfectly in containers
7. **Local Development**: Command-line args make testing different configs easy
8. **Self-Documenting**: `--help` shows all available options

## Implementation Checklist

- [ ] Create `duplocloud/mcp/config.py` with `ServerConfig` class
- [ ] Update `duplocloud/mcp/server.py` to accept and use `ServerConfig`
- [ ] Update `duplocloud/mcp/__main__.py` to parse args and create config
- [ ] Update `README.md` with new usage examples
- [ ] Update `.env.example` to document all new env vars
- [ ] Update `docker-compose.yaml` to use env vars appropriately
- [ ] Add tests for configuration priority and parsing
- [ ] Update VS Code tasks to pass args when needed
- [ ] Document FastMCP CLI integration pattern

## Environment Variables Reference

### DuploCloud Configuration (Required)

| Variable | Description | Example |
|----------|-------------|---------|
| `DUPLO_HOST` | DuploCloud API host URL | `https://your-instance.duplocloud.net` |
| `DUPLO_TOKEN` | DuploCloud API token | `your-api-token-here` |
| `DUPLO_TENANT` | DuploCloud tenant name | `your-tenant-name` |

### Server Configuration (Optional)

| Variable | Description | Default | Valid Values |
|----------|-------------|---------|--------------|
| `MCP_TRANSPORT` | Transport protocol | `stdio` | `stdio`, `http`, `streamable-http`, `sse` |
| `MCP_HOST` | Host to bind to (HTTP only) | `0.0.0.0` | Any valid host/IP |
| `PORT` or `MCP_PORT` | Port to bind to (HTTP only) | `8000` | `1-65535` |
| `MCP_PATH` | URL path for endpoint (HTTP only) | `/mcp` | Any valid path |
| `MCP_LOG_LEVEL` | Logging verbosity | `INFO` | `DEBUG`, `INFO`, `WARNING`, `ERROR`, `CRITICAL` |

### FastMCP Configuration (Optional)

| Variable | Description | Default |
|----------|-------------|---------|
| `FASTMCP_LOG_LEVEL` | FastMCP framework log level | Inherits from `MCP_LOG_LEVEL` |
| `FASTMCP_MASK_ERROR_DETAILS` | Hide error details in responses | `False` |

## Conclusion

This architecture provides a robust, flexible configuration system that:

1. ✅ Leverages argparse (consistent with duploctl)
2. ✅ Supports environment variables (Docker/cloud-friendly)
3. ✅ Enables future config file support
4. ✅ Maintains backward compatibility
5. ✅ Integrates with FastMCP CLI patterns
6. ✅ Provides clear documentation via `--help`
7. ✅ Clarifies the http vs streamable-http confusion

The recommended implementation follows industry-standard configuration precedence and integrates seamlessly with the existing duploctl patterns, making it familiar to developers who already know the duplocloud-client codebase.
