# MCP Server CLI Implementation Research

## Research Question
How to implement the MCP server as a CLI command that can be run by simply executing `duplocloud-mcp` from the command line?

## Investigation Plan
1. Research duploctl repository structure and CLI implementation
2. Analyze duploctl pyproject.toml for CLI configuration
3. Examine current MCP server implementation
4. Research Python entrypoints specification
5. Compare MCP with duploctl implementation
6. Document implementation recommendations

## Investigation Results

### Initial Research
The MCP server needs to be implemented as a CLI command that can be run by executing `duplocloud-mcp` from the command line. The current implementation has a server structure but lacks the CLI command entry point configuration.

### Python Entrypoints Documentation

Python entry points are a mechanism for an installed distribution to advertise components it provides to be discovered and used by other code. For CLI commands, the `console_scripts` entry point group is used to create command-line wrappers when a package is installed.

Key points from the documentation:
- Entry points are defined in the `pyproject.toml` file under the `[project.scripts]` section
- The format is `command_name = module.path:function_name`
- For console scripts, the specified function should be callable with no arguments and can return an integer as exit code
- Entry points allow packages to be run directly from the command line without invoking Python explicitly

The function referenced by a console script entry point will be called when the command is run, and the system will create a wrapper script similar to:

```python
import sys
from mymod import main
sys.exit(main())
```

### Duploctl CLI Implementation

The duploctl repository implements CLI commands through:

1. **Entry point configuration in pyproject.toml**:
   ```toml
   [project.scripts]
   duploctl = "duplocloud.cli:main"
   ```

2. **Main CLI function implementation**:
   ```python
   # In duplocloud.cli module
   def main():
     try:
       duplo, args = DuploClient.from_env()
       o = duplo(*args)
       if o:
         print(o)
     except DuploError as e:
       print(e)
       exit(e.code)
     except Exception as e:
       print(f"An unexpected error occurred: {e}")
       exit(1)
   ```

3. **Entry points for resource types**:
   The duploctl repository also defines custom entry points for various resource types under `[project.entry-points."duplocloud.net"]`, which are used by the CLI for handling different resource types.

### MCP Current Structure

The current MCP project structure includes:

1. **Server implementation** in `duplocloud/mcp/server.py`:
   ```python
   from fastmcp import FastMCP

   mcp = FastMCP(
       "duplocloud-mcp",
   )

   @mcp.tool
   def hello(name: str = "world") -> str:
       """
       Returns a greeting.

       Args:
           name: The name to greet.
       Returns:
           A greeting string.
       """
       return f"Hello, {name}!"

   def create_server() -> FastMCP:
       """
       Create the MCP server and register tools.
       """
       return mcp
   ```

2. **Main entry point** in `duplocloud/mcp/__main__.py`:
   ```python
   from .server import create_server

   def main():
       """
       Main entry point for the MCP server.
       """
       server = create_server()
       server.run()

   if __name__ == "__main__":
       main()
   ```

3. **Project configuration** in `pyproject.toml`:
   ```toml
   [project]
   name = "duplocloud-mcp"
   description = "Model Context Protocol (MCP) server for DuploCloud."
   # ...
   dependencies = ["fastmcp"]
   
   [tool.setuptools]
   packages = ["duplocloud.mcp"]
   ```

However, the project is missing the `[project.scripts]` section in `pyproject.toml` that would define the CLI command.

### Comparison and Gap Analysis

Comparing the current MCP implementation with the duploctl implementation, the following gaps were identified:

1. **Missing Entry Point Configuration**:
   - MCP lacks the `[project.scripts]` section in `pyproject.toml` that would register the command
   - Without this configuration, the package cannot be invoked as a CLI command

2. **CLI Interface Structure**:
   - The duploctl has a dedicated `duplocloud.cli` module for the CLI entry point
   - MCP has a main function in `__main__.py` but it's not connected to a CLI entry point

3. **Command Execution Flow**:
   - duploctl has proper error handling and output formatting in its CLI main function
   - MCP's main function simply creates and runs the server without CLI-specific handling

4. **Package Configuration**:
   - MCP's package name is "duplocloud-mcp" but there's no association between this name and a CLI command

## Prototype/Testing Notes
No prototyping has been performed yet. The implementation would require:
1. Updating the `pyproject.toml` file to include the `[project.scripts]` section
2. Ensuring the main function in `__main__.py` or a dedicated CLI module properly handles CLI arguments and execution

## External Resources
- Python Entry Points Documentation: https://packaging.python.org/en/latest/specifications/entry-points/
- Duploctl Repository: https://github.com/duplocloud/duploctl
- Duploctl pyproject.toml: https://github.com/duplocloud/duploctl/blob/main/pyproject.toml
- Python Entry Points Reference: https://packaging.python.org/en/latest/guides/creating-and-discovering-plugins/

## Decision/Recommendation

Based on the research, here are the recommended changes to implement the MCP server as a CLI command:

1. **Update pyproject.toml**:
   Add the `[project.scripts]` section to define the `duplocloud-mcp` command:
   ```toml
   [project.scripts]
   duplocloud-mcp = "duplocloud.mcp.__main__:main"
   ```

2. **Enhance the Main Function**:
   Improve the `main()` function in `__main__.py` to better handle command-line invocation:
   ```python
   from .server import create_server
   import sys

   def main():
       """
       Main entry point for the MCP server when invoked as a CLI command.
       """
       try:
           server = create_server()
           server.run()
           return 0
       except Exception as e:
           print(f"Error starting MCP server: {e}", file=sys.stderr)
           return 1
           
   if __name__ == "__main__":
       sys.exit(main())
   ```

3. **Optional: Create a Dedicated CLI Module**:
   For more complex CLI handling, consider creating a dedicated `duplocloud.mcp.cli` module similar to duploctl.

4. **Re-install Package**:
   After making these changes, reinstall the package using:
   ```bash
   pip install -e .
   ```
   This will register the `duplocloud-mcp` command in the environment.

These changes will allow the MCP server to be run directly using the `duplocloud-mcp` command from any terminal.

## Status History
- Started: October 1, 2025
- Completed: October 1, 2025