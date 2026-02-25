"""Tests for the ToolRegistrar class.

Uses mocks for DuploClient and duploctl internals to test registration
mechanics in isolation.
"""

import inspect
import re
from unittest.mock import MagicMock, patch

import pytest
from fastmcp import FastMCP

from duplocloud.mcp.tools import ToolRegistrar


# Minimal mock Arg that mimics duploctl's Arg type
class MockArg:
    def __init__(self, name, supertype=str, dest=None):
        self.__name__ = name
        self.__supertype__ = supertype
        self.attributes = {"dest": dest} if dest else {}


class MockModel:
    """Minimal Pydantic model stand-in for testing."""
    pass


@pytest.fixture
def mock_duplo():
    duplo = MagicMock()
    duplo.load_model.return_value = None
    return duplo


@pytest.fixture
def registrar(mcp_instance, mock_duplo, default_command_filter):
    return ToolRegistrar(mcp_instance, mock_duplo, default_command_filter)


class TestBuildParams:
    """Tests for ToolRegistrar.build_params."""

    def test_params_from_method_with_args(self, registrar):
        """Extract params from a method with Arg annotations."""
        def method(self, name="default"):
            pass

        mock_args = [MockArg("name", str)]

        with patch("duplocloud.mcp.tools.extract_args", return_value=mock_args):
            params = registrar.build_params(method, {})

        assert len(params) == 1
        assert params[0].name == "name"
        assert params[0].annotation is str
        assert params[0].default == "default"

    def test_params_from_method_with_no_args(self, registrar):
        """Method with no Arg annotations returns empty params."""
        def method(self):
            pass

        with patch("duplocloud.mcp.tools.extract_args", return_value=[]):
            params = registrar.build_params(method, {})

        assert params == []

    def test_model_annotation_replaces_dict_on_body(self, registrar):
        """When command_info has model, body param gets Pydantic class."""
        registrar.duplo.load_model.return_value = MockModel

        def method(self, body=None):
            pass

        mock_args = [MockArg("file", dict, dest="body")]

        with patch("duplocloud.mcp.tools.extract_args", return_value=mock_args):
            params = registrar.build_params(method, {"model": "SomeModel"})

        assert len(params) == 1
        assert params[0].annotation is MockModel

    def test_model_not_found_degrades_to_dict(self, registrar):
        """When load_model returns None, body stays as dict."""
        registrar.duplo.load_model.return_value = None

        def method(self, body=None):
            pass

        mock_args = [MockArg("file", dict, dest="body")]

        with patch("duplocloud.mcp.tools.extract_args", return_value=mock_args):
            params = registrar.build_params(method, {"model": "MissingModel"})

        assert len(params) == 1
        assert params[0].annotation is dict

    def test_model_only_applies_to_body_param(self, registrar):
        """Non-body params keep their original type even when model exists."""
        registrar.duplo.load_model.return_value = MockModel

        def method(self, name="test", body=None):
            pass

        mock_args = [MockArg("name", str), MockArg("file", dict, dest="body")]

        with patch("duplocloud.mcp.tools.extract_args", return_value=mock_args):
            params = registrar.build_params(method, {"model": "SomeModel"})

        assert params[0].name == "name"
        assert params[0].annotation is str
        assert params[1].name == "body"
        assert params[1].annotation is MockModel


class TestBuildWrapper:
    """Tests for ToolRegistrar.build_wrapper."""

    def test_wrapper_preserves_name(self, registrar):
        def method():
            return "result"

        wrapper = registrar.build_wrapper(method, "tenant_create", "Create a tenant", [])
        assert wrapper.__name__ == "tenant_create"

    def test_wrapper_preserves_docstring(self, registrar):
        def method():
            return "result"

        doc = "Create a new tenant."
        wrapper = registrar.build_wrapper(method, "tenant_create", doc, [])
        assert wrapper.__doc__ == doc

    def test_wrapper_signature_matches_params(self, registrar):
        def method(name="test"):
            return name

        params = [
            inspect.Parameter(
                "name",
                inspect.Parameter.POSITIONAL_OR_KEYWORD,
                default="test",
                annotation=str,
            )
        ]
        wrapper = registrar.build_wrapper(method, "tenant_find", "Find", params)

        sig = inspect.signature(wrapper)
        assert "name" in sig.parameters
        assert sig.parameters["name"].annotation is str

    def test_wrapper_calls_original(self, registrar):
        called = {}

        def method(name="world"):
            called["name"] = name
            return f"hello {name}"

        wrapper = registrar.build_wrapper(method, "test_tool", "Test", [])
        result = wrapper(name="duplo")
        assert result == "hello duplo"
        assert called["name"] == "duplo"


class TestRegisterResource:
    """Tests for ToolRegistrar.register_resource."""

    def test_command_filter_applied(self, mcp_instance, mock_duplo):
        """Only commands matching the filter get registered."""
        command_filter = re.compile("create|update")
        registrar = ToolRegistrar(mcp_instance, mock_duplo, command_filter)

        mock_resource = MagicMock()
        mock_resource.create = MagicMock(__doc__="Create")
        mock_resource.list = MagicMock(__doc__="List")
        mock_resource.delete = MagicMock(__doc__="Delete")
        mock_duplo.load.return_value = mock_resource

        commands = {
            "create": {"method": "create", "aliases": [], "model": None},
            "list": {"method": "list", "aliases": [], "model": None},
            "delete": {"method": "delete", "aliases": [], "model": None},
        }

        with patch("duplocloud.mcp.tools.commands_for", return_value=commands), \
             patch.object(registrar, "register_tool") as mock_register:
            registrar.register_resource("test_resource")

        # Only "create" matches the filter; "list" and "delete" do not
        registered_methods = [call.args[1] for call in mock_register.call_args_list]
        assert "create" in registered_methods
        assert "list" not in registered_methods
        assert "delete" not in registered_methods


class TestRegister:
    """Tests for ToolRegistrar.register (top-level)."""

    def test_errors_per_resource_dont_block_others(self, mcp_instance, mock_duplo, default_command_filter):
        """One resource failing doesn't prevent others from registering."""
        registrar = ToolRegistrar(mcp_instance, mock_duplo, default_command_filter)

        call_log = []

        def mock_register_resource(name):
            call_log.append(name)
            if name == "bad_resource":
                raise Exception("boom")

        with patch.object(registrar, "register_resource", side_effect=mock_register_resource):
            registrar.register(["good_resource", "bad_resource", "another_good"])

        assert call_log == ["good_resource", "bad_resource", "another_good"]
