"""Shared fixtures for MCP server tests."""

import re

import pytest
from fastmcp import FastMCP


@pytest.fixture
def mcp_instance():
    """A fresh FastMCP instance for testing (no global state leakage)."""
    return FastMCP(name="test-mcp", version="0.0.0")


@pytest.fixture
def default_command_filter():
    """Default command filter that matches everything."""
    return re.compile(".*")
