# GitHub Copilot Instructions for the DuploCloud MCP Server

This document provides instructions for GitHub Copilot to effectively assist with development in this repository.

## Project Overview

This project is a **FastMCP server** that acts as a wrapper for the `duplocloud-client` Python package (which powers `duploctl`). Its primary goal is to dynamically expose `duploctl` commands as MCP (Model-Context-Protocol) tools and resources. This allows AI agents and other MCP-compatible clients to interact with the DuploCloud platform programmatically.

The core logic for this wrapping and registration is in `duplocloud/mcp/server.py`.

## Key Concepts & Architecture

### 1. Dynamic `duploctl` Command Registration

The central feature of this server is its ability to dynamically discover and register `duploctl` commands.

-   **Source of Commands**: Commands are defined in the `duplocloud-client` library using the `@Command` decorator.
-   **Discovery Mechanism**: The server uses the `schema` object from `duplocloud.commander` to get a registry of all available commands.
-   **Registration Logic**: The `_register_resource_commands` method in `duplocloud/mcp/server.py` iterates through this schema and registers each command as an MCP tool. Read-only operations are also marked for registration as MCP resources.

### 2. Important `duplocloud-client` Modules

When working on this project, you will frequently need to reference the source code of the `duplocloud-client` package. It is installed in the virtual environment.

-   **Path**: `/workspaces/mcp/.venv/lib/python3.13/site-packages/duplocloud/`
-   **`commander.py`**: This file is critical. It contains the `@Command` and `@Resource` decorators and maintains the `schema` dictionary, which is the source of truth for all registered commands.
-   **`client.py`**: This is the main entry point for the `duplocloud-client`. The `DuploClient` class handles configuration, authentication, and loading resources. The MCP server instantiates this client to execute commands.

### 3. Prefer VS Code Tasks Over Direct CLI Commands

This workspace is configured with predefined tasks in `.vscode/tasks.json` for common operations. AI agents and modes should **always prefer using these tasks** instead of attempting to run shell commands directly.

-   **`start`**: Runs the MCP server locally for development. It correctly sets up the Python interpreter and environment variables.
-   **`init`**: Sets up the virtual environment and installs dependencies.
-   **`Lint`**: Runs the linter.
-   **`Up`**: Starts the server via Docker Compose.

**Example**: To start the server, do not run `python -m duplocloud.mcp.server`. Instead, use the `start` task. This ensures the correct environment and settings are applied.

## Development Workflow

1.  **Activate Environment**: Always ensure the virtual environment is active: `source .venv/bin/activate`.
2.  **Run the Server**: Use the `start` task in VS Code to run the MCP server.
3.  **Modify Registration**: To change how tools or resources are registered, edit `duplocloud/mcp/server.py`.
4.  **Test**: Interact with the running MCP server via its endpoints to test new tools or resources.
