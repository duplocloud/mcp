# DuploCloud MCP Server

An emerging Model Context Protocol (MCP) server integration for DuploCloud. This project exposes DuploCloud operations and resources through the MCP interface so AI tooling and compatible clients can query infrastructure state and perform safe, auditable actions.

> Status: Project scaffolding & discovery phase. Implementation details, API surface, and safety constraints are not yet finalized.

## Overview

This project is a **FastMCP server** that acts as a wrapper for the `duplocloud-client` Python package (which powers `duploctl`). Its primary goal is to dynamically expose `duploctl` commands as MCP (Model-Context-Protocol) tools and resources. This allows AI agents and other MCP-compatible clients to interact with the DuploCloud platform programmatically.

The server discovers `duploctl` commands at runtime and registers them as MCP tools. Read-only operations (like `find`, `list`, `logs`) are also registered as MCP resources, enabling both action-taking and state-querying capabilities.

## Getting Started

1.  **Setup**: Run the `init` task in VS Code to create a virtual environment and install all necessary dependencies.
    ```
    Tasks: Run Task > init
    ```
2.  **Environment**: Ensure you have the following environment variables set, as the server uses them to authenticate with DuploCloud:
    - `DUPLO_HOST`
    - `DUPLO_TOKEN`
    - `DUPLO_TENANT`
3.  **Run the server**: Use the `start` task in VS Code to run the MCP server locally.
    ```
    Tasks: Run Task > start
    ```
    The server will be available at `http://localhost:8000`.

## MCP Configuration

To add this server to your MCP client configuration (e.g., in an `mcp.json` file), add the following entry to your `tools` array:

```json
{
  "tools": [
    {
      "name": "duplocloud",
      "url": "http://localhost:8000/mcp"
    }
  ]
}
```

This will allow your MCP client to discover and use the tools and resources exposed by this server.

## References

- duploctl (layout & conventions): https://github.com/duplocloud/duploctl
- Keep a Changelog: https://keepachangelog.com/en/1.1.0/
- Semantic Versioning: https://semver.org/spec/v2.0.0.html
- Model Context Protocol (spec draft): https://modelcontextprotocol.io/
- [Fast MCP](https://gofastmcp.com/getting-started/welcome) - The base framework used to build this server.
- [Duplocloud Generated Swagger File](https://github.com/duplocloud-internal/duplo/blob/master/ContainerManagement/generated/public/NodeStateDriverSwagger.json)
- [Awesome Copilot](https://github.com/github/awesome-copilot) - Example repo with all the copilot chatmodes and iunstructions that inspired this setup.
