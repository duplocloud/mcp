---
goal: Implement MCP server as a CLI command for execution via "duplocloud-mcp"
version: 1.0
date_created: 2025-10-01
last_updated: 2025-10-01
owner: DuploCloud Team
status: 'Completed'
tags: ['feature', 'cli', 'usability']
---

# Introduction

![Status: Completed](https://img.shields.io/badge/status-Completed-brightgreen)

This plan outlines the implementation steps required to make the MCP server executable as a CLI command by simply running `duplocloud-mcp` from the command line. The implementation follows Python packaging best practices for entry points and command-line interfaces, aligning with patterns established in the duploctl project.

## 1. Requirements & Constraints

- **REQ-001**: Users must be able to launch the MCP server by typing `duplocloud-mcp` in a terminal
- **REQ-002**: The CLI command must provide appropriate exit codes based on success/failure
- **REQ-003**: The CLI command must handle and display errors appropriately
- **REQ-004**: The implementation must follow Python packaging standards for entry points
- **REQ-005**: The CLI command structure should be consistent with other DuploCloud tooling

- **CON-001**: Must maintain compatibility with the existing project structure
- **CON-002**: Implementation must work with the current FastMCP server implementation
- **CON-003**: Must follow the same entry point patterns established in duploctl

- **PAT-001**: Follow the pattern established in duploctl for CLI implementation
- **PAT-002**: Use Python's entry point mechanism for CLI command registration

## 2. Implementation Steps

### Implementation Phase 1: Update Project Configuration

- GOAL-001: Configure the project's pyproject.toml to support CLI command execution

| Task | Description | Completed | Date |
|------|-------------|-----------|------|
| TASK-001 | Add `[project.scripts]` section to pyproject.toml | ✅ | 2025-10-01 |
| TASK-002 | Configure entry point for `duplocloud-mcp` command | ✅ | 2025-10-01 |
| TASK-003 | Verify the project configuration for packaging correctness | ✅ | 2025-10-01 |

### Implementation Phase 2: Enhance Main Entry Point

- GOAL-002: Improve the main function to handle CLI execution properly

| Task | Description | Completed | Date |
|------|-------------|-----------|------|
| TASK-004 | Update `__main__.py` with proper error handling | ✅ | 2025-10-01 |
| TASK-005 | Add system exit code handling to main function | ✅ | 2025-10-01 |
| TASK-006 | Add command line argument support (if needed) | ✅ | 2025-10-01 |

### Implementation Phase 3: Testing and Verification

- GOAL-003: Verify the CLI command works correctly

| Task | Description | Completed | Date |
|------|-------------|-----------|------|
| TASK-007 | Reinstall the package with `pip install -e .` | ✅ | 2025-10-01 |
| TASK-008 | Test the `duplocloud-mcp` command execution | ✅ | 2025-10-01 |
| TASK-009 | Verify error handling works correctly | ✅ | 2025-10-01 |
| TASK-010 | Ensure server functionality is maintained | ✅ | 2025-10-01 |

## 3. Alternatives

- **ALT-001**: Create a separate CLI module (e.g., `duplocloud.mcp.cli`) for more complex CLI handling instead of using `__main__.py` directly
- **ALT-002**: Use a dedicated CLI framework like Click or Typer for more advanced command line interface features
- **ALT-003**: Create a separate executable script instead of using entry points (less preferred, as it doesn't align with Python standards)

## 4. Dependencies

- **DEP-001**: Python setuptools for entry point handling
- **DEP-002**: FastMCP package for server implementation
- **DEP-003**: Development environment with pip for installing the package locally

## 5. Files

- **FILE-001**: `pyproject.toml` - Update to add scripts section
- **FILE-002**: `duplocloud/mcp/__main__.py` - Enhance for proper CLI handling
- **FILE-003**: `duplocloud/mcp/server.py` - No changes required unless adding CLI-specific functionality
- **FILE-004**: `Dockerfile` - Update to use CLI command as entrypoint

## 6. Testing

- **TEST-001**: Verify that running `duplocloud-mcp` launches the server correctly
- **TEST-002**: Verify that server errors are reported to the console with appropriate exit codes
- **TEST-003**: Test installation in a clean environment to ensure the command works
- **TEST-004**: Test error handling by simulating server startup failures

## 7. Risks & Assumptions

- **RISK-001**: If the server requires specific environment setup, simply running the command might not be sufficient
- **RISK-002**: Server exceptions might not be properly captured with the current implementation
- **RISK-003**: Command might conflict with other installed packages that define similar commands

- **ASSUMPTION-001**: The current `main()` function in `__main__.py` is sufficient for running the server
- **ASSUMPTION-002**: No additional CLI parameters are needed for basic server operation
- **ASSUMPTION-003**: The FastMCP framework handles its own signal handling and shutdown procedures

## 8. Related Specifications / Further Reading

- [Python Entry Points Documentation](https://packaging.python.org/en/latest/specifications/entry-points/)
- [Duploctl pyproject.toml](https://github.com/duplocloud/duploctl/blob/main/pyproject.toml)
- [Python Packaging User Guide](https://packaging.python.org/en/latest/guides/creating-and-discovering-plugins/)
- [MCP CLI Implementation Research](/workspaces/mcp/.github/reports/mcp-cli-1.research.md)

## 9. Docker Integration

### Implementation Phase 4: Docker Configuration

- GOAL-004: Update Docker configuration to use the CLI command

| Task | Description | Completed | Date |
|------|-------------|-----------|------|
| TASK-011 | Review current Dockerfile configuration | ✅ | 2025-10-01 |
| TASK-012 | Update Dockerfile to use the CLI command as entrypoint | ✅ | 2025-10-01 |
| TASK-013 | Test Docker image build | ✅ | 2025-10-01 |
| TASK-014 | Verify Docker container execution | ✅ | 2025-10-01 |

## 10. Implementation Summary

The implementation of the MCP server as a CLI command has been successfully completed. The following changes were made:

1. **Updated `pyproject.toml`**:
   - Added the `[project.scripts]` section
   - Configured the `duplocloud-mcp` entry point to map to `duplocloud.mcp.__main__:main`

2. **Enhanced `__main__.py`**:
   - Added proper error handling with try-except block
   - Added system exit code handling
   - Added a startup message for better user experience
   - Added keyboard interrupt handling

3. **Updated Dockerfile**:
   - Changed the CMD instruction to use the new CLI command
   - Replaced `CMD ["python", "-m", "duplocloud.mcp"]` with `CMD ["duplocloud-mcp"]`

4. **Verified Installation and Functionality**:
   - Successfully installed the package with `pip install -e .`
   - Verified that the `duplocloud-mcp` command is available in the PATH
   - Tested the command execution and confirmed it launches the server
   - Confirmed that the server shows proper startup information

These changes allow users to launch the MCP server by simply typing `duplocloud-mcp` in the terminal, providing a more streamlined user experience consistent with other DuploCloud tools. The Docker container now uses the same standardized command interface.