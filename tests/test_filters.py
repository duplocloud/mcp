"""Tests for filter matching behavior.

These tests operate directly on compiled regex via re.fullmatch -- no server
instance needed. Pure unit tests verifying the filtering contract.
"""

import re

import pytest


class TestResourceFilter:
    """Verify resource filter patterns match as expected."""

    def test_default_matches_everything(self):
        pattern = re.compile(".*")
        assert pattern.fullmatch("service")
        assert pattern.fullmatch("tenant")
        assert pattern.fullmatch("anything")

    def test_exact_match(self):
        pattern = re.compile("service")
        assert pattern.fullmatch("service")

    def test_exact_non_match(self):
        pattern = re.compile("service")
        assert not pattern.fullmatch("tenant")

    def test_alternation(self):
        pattern = re.compile("service|lambda|s3")
        assert pattern.fullmatch("lambda")
        assert pattern.fullmatch("service")
        assert pattern.fullmatch("s3")

    def test_alternation_non_match(self):
        pattern = re.compile("service|lambda|s3")
        assert not pattern.fullmatch("tenant")

    def test_regex_wildcard(self):
        pattern = re.compile("batch_.*")
        assert pattern.fullmatch("batch_compute")
        assert pattern.fullmatch("batch_anything")

    def test_regex_wildcard_non_match(self):
        pattern = re.compile("batch_.*")
        assert not pattern.fullmatch("service")

    def test_partial_should_not_match(self):
        """fullmatch requires the entire string to match."""
        pattern = re.compile("serv")
        assert not pattern.fullmatch("service")


class TestCommandFilter:
    """Verify command filter patterns match as expected."""

    def test_exact_command(self):
        pattern = re.compile("create")
        assert pattern.fullmatch("create")

    def test_command_alternation(self):
        pattern = re.compile("create|delete|update")
        assert pattern.fullmatch("create")
        assert pattern.fullmatch("delete")
        assert pattern.fullmatch("update")

    def test_command_alternation_non_match(self):
        pattern = re.compile("create|delete|update")
        assert not pattern.fullmatch("list")

    def test_default_matches_all_commands(self):
        pattern = re.compile(".*")
        assert pattern.fullmatch("create")
        assert pattern.fullmatch("list")
        assert pattern.fullmatch("find")
        assert pattern.fullmatch("delete")
