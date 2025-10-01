# MCP Wheel Installation Research

**Version:** 1.0  
**Date:** 2025-10-01  
**Status:** Complete  

## Table of Contents
1. [Executive Summary](#executive-summary)
2. [Investigation Results](#investigation-results)
   - [Building the Wheel Package](#building-the-wheel-package)
   - [Installing the Package](#installing-the-package)
   - [Docker Containerization](#docker-containerization)
   - [Command-line Interface](#command-line-interface)
3. [Technical Constraints](#technical-constraints)
4. [External Resources](#external-resources)
5. [Decision/Recommendation](#decisionrecommendation)

## Executive Summary

This research explores how to package the DuploCloud MCP server as a wheel distribution for easy installation in various environments, including Docker containers. The findings indicate that a multi-stage Docker build provides the most efficient method for packaging and distributing the MCP server, following patterns similar to those used in the duploctl project.

## Investigation Results

### Building the Wheel Package

The DuploCloud MCP server can be built as a standard Python wheel package using the following methods:

#### Local Development Build

1. Clone the repository:

   ```bash
   git clone https://github.com/duplocloud/mcp.git
   cd mcp
   ```

2. Install build tools:

   ```bash
   pip install build
   ```

3. Build the package:

   ```bash
   python -m build
   ```

   This creates both source distribution (.tar.gz) and wheel (.whl) packages in the `dist/` directory.

#### Docker Build

The wheel can also be built using Docker:

```bash
docker build --target builder -t duplocloud-mcp-builder .
docker create --name mcp-build-container duplocloud-mcp-builder
docker cp mcp-build-container:/app/dist ./dist
docker rm mcp-build-container
```

This approach extracts the built packages to a local `dist/` directory.

### Installing the Package

#### From Local Build

```bash
pip install ./dist/duplocloud_mcp-*.whl
```

#### From PyPI (when published)

```bash
pip install duplocloud-mcp
```

### Docker Containerization

The project includes a multi-stage Dockerfile that:

1. Builds the wheel package in a build container
2. Installs the wheel in a minimal Python container
3. Sets the entry point to the `mcp-server` command

```dockerfile
ARG PY_VERSION=3.10

# Stage 1: Install dependencies and build tools
FROM python:$PY_VERSION AS setup

# Set the working directory in the container
WORKDIR /app

# Copy the source code, pyproject.toml, .git file to the container
COPY . .

# Install build dependencies
RUN <<EOF
pip install --no-cache-dir --upgrade pip
pip install --no-cache-dir build
EOF

# Build the package
FROM setup AS builder
RUN python -m build --no-isolation

# Stage 2: Install the package in a slimmer container
FROM python:$PY_VERSION-slim AS runner

# Set the working directory in the container
WORKDIR /app

# Copy the built package from the previous stage
COPY --from=builder /app/dist ./dist/

# Install the package using pip
RUN pip install --no-cache-dir ./dist/*.whl && \
    rm -rf ./dist

# Set the entrypoint command for the container
ENTRYPOINT ["mcp-server"]

CMD ["--help"]
```

The container can be built and run with:

```bash
docker build -t duplocloud/mcp-server .
docker run -it --rm duplocloud/mcp-server
```

### Command-line Interface

The MCP server exposes a command-line interface through the `mcp-server` entry point, which provides the following options:

- `--version`: Show the version and exit
- `-v, --verbose`: Enable verbose logging
- `--transport {stdio,http}`: Transport method to use (default: stdio)
- `--host HOST`: Host to bind to for HTTP transport (default: 127.0.0.1)
- `--port PORT`: Port to bind to for HTTP transport (default: 8000)

Example usage:

```bash
# Start with STDIO transport (default)
mcp-server

# Start with HTTP transport
mcp-server --transport http --host 0.0.0.0 --port 8080
```

## Technical Constraints

1. **Python Version:**
   - Requires Python 3.10 or newer as specified in pyproject.toml

2. **Dependencies:**
   - fastmcp>=2.0.0
   - pydantic>=2.0.0

3. **Entry Points:**
   - The package must expose the `mcp-server` entry point for CLI usage

## External Resources

1. **duploctl GitHub Repository:**
   - Reference implementation for Docker-based wheel packaging
   - https://github.com/duplocloud/duploctl

2. **Python Packaging User Guide:**
   - Official documentation for Python packaging
   - https://packaging.python.org/en/latest/

3. **FastMCP Documentation:**
   - Documentation for the FastMCP framework
   - https://gofastmcp.com/

## Decision/Recommendation

Based on the research findings, we recommend:

1. **Use Multi-stage Docker Build:**
   - Implement the multi-stage Docker build pattern as shown in the sample Dockerfile
   - This allows for efficient distribution and deployment in various environments

2. **Package Configuration:**
   - Configure the pyproject.toml to include necessary dependencies
   - Set up the mcp-server entry point script

3. **Distribution Strategy:**
   - Publish the wheel package to PyPI for easy installation
   - Provide the Docker image as an alternative deployment method

This approach ensures the MCP server can be easily installed and run in various environments, including containerized deployments, while maintaining a clean, minimal footprint.