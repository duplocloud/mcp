# Research Report: MCP Server Implementation for DuploCloud

**Version:** 1.0  
**Date:** 2024-07-01  
**Status:** Complete  

## Table of Contents
1. [Executive Summary](#executive-summary)
2. [Project Overview](#project-overview)
3. [Investigation Results](#investigation-results)
   - [Model Context Protocol (MCP)](#model-context-protocol-mcp)
   - [FastMCP Framework](#fastmcp-framework)
   - [DuploCloud API Integration](#duplocloud-api-integration)
   - [MCP Client Implementation](#mcp-client-implementation)
4. [Technical Constraints](#technical-constraints)
5. [Prototype/Testing Notes](#prototypetesting-notes)
6. [External Resources](#external-resources)
7. [Decision/Recommendation](#decisionrecommendation)

## Executive Summary

This research explores the implementation of a Model Context Protocol (MCP) server for DuploCloud. The goal is to expose DuploCloud operations and resources through the MCP interface, allowing AI tools and compatible clients to query infrastructure state and perform safe, auditable actions. The research focuses on understanding the MCP specification, FastMCP framework, and how to integrate DuploCloud's API into an MCP server.

The findings indicate that FastMCP provides a solid foundation for building an MCP server with tools, resources, and prompts as key abstractions. The implementation will need to wrap DuploCloud's API endpoints (defined in the OpenAPI specification) into MCP tools and resources. Authentication and security measures will be critical for safe operation.

## Project Overview

The DuploCloud MCP Server project aims to build an interface between DuploCloud operations and AI assistants using the Model Context Protocol. This will enable AI tools to:
1. Query DuploCloud infrastructure state
2. Perform controlled actions with proper authentication and audit trails
3. Access DuploCloud resources in a standardized way

The project is currently in the scaffolding and discovery phase, with implementation details, API surface, and safety constraints not yet finalized. This research report aims to provide comprehensive information for planning the implementation.

## Investigation Results

### Model Context Protocol (MCP)

MCP is a standardized protocol for AI model-to-tool communication, defining how models access external data and execute actions.

**Key Components:**

1. **Server Architecture:**
   - Servers expose tools, resources, and prompts to clients
   - Communications via STDIO (default), HTTP, or SSE transports
   - Standardized request/response formats for tool execution

2. **Protocol Specifications:**
   - Server initialization
   - Tool discovery and execution
   - Resource access patterns
   - Authentication mechanisms
   - Error handling

3. **Core Abstractions:**
   - **Tools:** Functions that perform actions (e.g., create/update/delete operations)
   - **Resources:** Data objects that represent state (e.g., infrastructure components)
   - **Prompts:** Templated text for consistent AI interactions

### FastMCP Framework

FastMCP is a Python framework for building MCP servers, providing abstractions and utilities to implement the protocol.

**Key Features:**

1. **Server Implementation:**
   - Composition pattern for server creation with `fastmcp.Server` class
   - Transport configuration (STDIO/HTTP/SSE)
   - Authentication mechanisms (API keys, OAuth)
   - Error handling and logging

2. **Tool Registration:**
   - Function decorators for defining tools
   - Input validation via JSON Schema
   - Dependency injection for authenticated operations
   - Error handling and return type validation

3. **Resource Management:**
   - Resource class pattern for data representation
   - CRUD operations on resources
   - Schema validation for resource fields
   - Resource relationships and nested access

4. **Exception Handling:**
   - Custom exceptions for various error types
   - Validation errors for schema compliance
   - Tool and resource operation errors
   - Authentication and authorization errors

### DuploCloud API Integration

The DuploCloud API, defined in the OpenAPI specification (openapi.json), provides endpoints for infrastructure management that need to be exposed via MCP.

**Key Integration Points:**

1. **API Structure:**
   - RESTful API with operations grouped by resource types
   - Authentication via API keys or tokens
   - JSON request/response formats

2. **Endpoint Organization:**
   - ContainersAdminApi
   - Other API groups (detailed analysis needed)

3. **OpenAPI Schema:**
   - Comprehensive endpoint documentation
   - Request/response schemas
   - Authentication requirements
   - Error response formats

### MCP Client Implementation

Understanding how clients will interact with the MCP server is essential for effective implementation.

**Key Client Patterns:**

1. **Client Connection:**
   ```python
   async def connect_to_server(self, server_script_path: str):
       server_params = StdioServerParameters(
           command="python",
           args=[server_script_path],
           env=None
       )
       stdio_transport = await self.exit_stack.enter_async_context(stdio_client(server_params))
       self.session = await self.exit_stack.enter_async_context(ClientSession(self.stdio, self.write))
       await self.session.initialize()
   ```

2. **Tool Discovery:**
   ```python
   response = await self.session.list_tools()
   tools = response.tools
   ```

3. **Tool Execution:**
   ```python
   result = await self.session.call_tool(tool_name, tool_args)
   ```

## Technical Constraints

1. **Python Version:**
   - Requires Python 3.10 or newer as specified in pyproject.toml
   - Compatible with FastMCP framework requirements

2. **Authentication:**
   - Must maintain DuploCloud API authentication requirements
   - May need to implement token refreshing mechanisms
   - Should support API key authentication at minimum

3. **Error Handling:**
   - Need to translate DuploCloud API errors to MCP-compatible formats
   - Must handle network errors gracefully
   - Should provide meaningful error messages for debugging

4. **Performance:**
   - Response time expectations for AI assistant integration
   - Potential for concurrent requests
   - Caching strategies for frequently accessed resources

5. **Security:**
   - Access control to prevent unauthorized operations
   - Input validation to prevent injection attacks
   - Audit logging for security monitoring

## Prototype/Testing Notes

No prototype has been developed yet as this is a research phase report. Testing will be essential for:

1. Tool execution flows with DuploCloud API
2. Authentication mechanisms
3. Error handling scenarios
4. Performance under various loads
5. Client integration patterns

## External Resources

1. **MCP Specification:**
   - [Model Context Protocol](https://modelcontextprotocol.io/)
   - [MCP Client Implementation Guide](https://modelcontextprotocol.io/docs/develop/build-client)

2. **FastMCP Framework:**
   - [FastMCP Documentation](https://gofastmcp.com/)
   - [FastMCP Server Implementation](https://gofastmcp.com/getting-started/server)
   - [FastMCP Tools](https://gofastmcp.com/components/tools)
   - [FastMCP Resources](https://gofastmcp.com/components/resources)
   - [GitHub Repository](https://github.com/jlowin/fastmcp)

3. **DuploCloud Resources:**
   - [DuploCloud API Swagger](https://github.com/duplocloud-internal/duplo/blob/master/ContainerManagement/generated/public/NodeStateDriverSwagger.json)
   - [duploctl](https://github.com/duplocloud/duploctl) (for layout & conventions)

## Decision/Recommendation

Based on the research findings, we recommend the following approach for implementing the DuploCloud MCP server:

1. **Framework Selection:**
   - Use FastMCP as the base framework due to its comprehensive implementation of the MCP specification and Python compatibility

2. **Project Structure:**
   - Follow duploctl conventions for code organization
   - Create modular components for tools, resources, and server configuration

3. **Implementation Strategy:**
   - Map DuploCloud API endpoints to MCP tools and resources
   - Implement proper authentication and error handling
   - Create comprehensive test suite for validation

4. **Development Phases:**
   1. Setup project structure and dependencies
   2. Create core server implementation with FastMCP
   3. Implement authentication mechanisms
   4. Map high-priority API endpoints to MCP tools
   5. Define key resources for state representation
   6. Develop error handling and logging
   7. Create test suite and validation procedures
   8. Document API surface and usage patterns

This implementation strategy provides a clear path forward while maintaining compatibility with both the MCP specification and DuploCloud's existing API patterns.