---
goal: "Create a basic 'Hello World' MCP server skeleton."
version: "1.0"
date_created: "2025-10-01"
last_updated: "2025-10-01"
owner: "GitHub Copilot"
status: 'Planned'
tags: ['feature', 'mcp', 'skeleton']
---

# Introduction

![Status: Planned](https://img.shields.io/badge/status-Planned-blue)

This plan outlines the steps to create a minimal "Hello World" Model Context Protocol (MCP) server. The goal is to establish a basic project structure with a single, simple tool that can be executed by an MCP client. This will serve as the foundation for further development, including Docker containerization and GitHub Actions setup.

## 1. Requirements & Constraints

- **REQ-001**: The implementation must result in a runnable, skeleton MCP server.
- **REQ-002**: The server should expose a simple "hello world" style tool.
- **REQ-003**: The plan must be detailed enough for an AI agent or human to execute without ambiguity.
- **REQ-004**: The project structure should use a flat layout where the package code resides in `duplocloud/mcp`.
- **CON-001**: Only create the minimum necessary files and code for a functional "hello world" server.

## 2. Implementation Steps

### Implementation Phase 1: Project Structure

- GOAL-001: Create the necessary directories and `__init__.py` files to define the Python package structure for the MCP server.

| Task | Description | Completed | Date |
|------|-------------|-----------|------|
| TASK-001 | Create the main package directory: `duplocloud/mcp/` | | |
| TASK-002 | Create an `__init__.py` file in `duplocloud/mcp/` to mark it as a package. | | |
| TASK-003 | Create a `tools` module directory: `duplocloud/mcp/tools/` | | |
| TASK-004 | Create an `__init__.py` file in `duplocloud/mcp/tools/` to mark it as a package. | | |

### Implementation Phase 2: Dependencies and Packaging

- GOAL-002: Update the `pyproject.toml` file to include the `fastmcp` framework as a dependency and configure project packaging.

| Task | Description | Completed | Date |
|------|-------------|-----------|------|
| TASK-005 | Add `fastmcp` to the `dependencies` list in `pyproject.toml`. | | |
| TASK-006 | Add `packages = ["duplocloud.mcp"]` to the `[tool.setuptools]` table in `pyproject.toml`. | | |

### Implementation Phase 3: "Hello World" Tool

- GOAL-003: Implement a simple "hello" tool that returns a greeting. This will be the first tool exposed by the MCP server.

| Task | Description | Completed | Date |
|------|-------------|-----------|------|
| TASK-007 | Create the file `duplocloud/mcp/tools/hello.py`. | | |
| TASK-008 | Add the following code to `duplocloud/mcp/tools/hello.py`: <br> ```python
from fastmcp import tool

@tool("hello")
def hello(name: str = "world") -> str:
    """
    Returns a greeting.

    Args:
        name: The name to greet.
    Returns:
        A greeting string.
    """
    return f"Hello, {name}!"
``` | | |

### Implementation Phase 4: Server Entrypoint

- GOAL-004: Create the main server file that initializes the FastMCP server and registers the "hello" tool.

| Task | Description | Completed | Date |
|------|-------------|-----------|------|
| TASK-009 | Create the file `duplocloud/mcp/server.py`. | | |
| TASK-010 | Add the following code to `duplocloud/mcp/server.py`: <br> ```python
from fastmcp import Server
from .tools.hello import hello

def create_server() -> Server:
    """
    Create the MCP server and register tools.
    """
    return Server(
        hello
    )
``` | | |

### Implementation Phase 5: Executable Module

- GOAL-005: Make the `duplocloud.mcp` package directly executable so it can be run with `python -m duplocloud.mcp`.

| Task | Description | Completed | Date |
|------|-------------|-----------|------|
| TASK-011 | Create the file `duplocloud/mcp/__main__.py`. | | |
| TASK-012 | Add the following code to `duplocloud/mcp/__main__.py`: <br> ```python
from .server import create_server

def main():
    """
    Main entry point for the MCP server.
    """
    server = create_server()
    server.run()

if __name__ == "__main__":
    main()
``` | | |

## 3. Alternatives

- **ALT-001**: Building a custom MCP server from scratch without using the `fastmcp` framework. This was rejected as it would significantly increase development time and complexity.

## 4. Dependencies

- **DEP-001**: `fastmcp`: The core framework for building the MCP server.

## 5. Files

- **FILE-001**: `duplocloud/mcp/`: Main package directory.
- **FILE-002**: `duplocloud/mcp/__init__.py`: Package initializer.
- **FILE-003**: `duplocloud/mcp/tools/`: Directory for MCP tools.
- **FILE-004**: `duplocloud/mcp/tools/__init__.py`: Tools module initializer.
- **FILE-005**: `duplocloud/mcp/tools/hello.py`: The "hello" tool implementation.
- **FILE-006**: `duplocloud/mcp/server.py`: Server creation and tool registration.
- **FILE-007**: `duplocloud/mcp/__main__.py`: Main executable entry point.
- **FILE-008**: `pyproject.toml`: To be modified to add dependencies and configure packaging.

## 6. Testing

- **TEST-001**: After implementation, run `pip install -e .` to install the package in editable mode.
- **TEST-002**: Run the server using the command `python -m duplocloud.mcp`.
- **TEST-003**: Verify that the server starts without errors and indicates that the "hello" tool is available.

## 7. Risks & Assumptions

- **ASSUMPTION-001**: The `fastmcp` library is installed and available in the Python environment.
- **ASSUMPTION-002**: The user has a working Python 3 environment.
- **RISK-001**: The `fastmcp` API could have breaking changes in the future, but this is a low risk for this initial skeleton.

## 8. Related Specifications / Further Reading

- [FastMCP Documentation](https://gofastmcp.com/getting-started/welcome)
- [Model Context Protocol Specification](https://modelcontextprotocol.io/)
