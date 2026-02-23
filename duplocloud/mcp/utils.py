"""Utility functions for the DuploCloud MCP server."""

from jinja2 import Template


def resolve_docstring_template(docstring: str, resource_name: str) -> str:
    """Resolve Jinja template variables in a docstring.

    The duploctl resource classes use Jinja templates in docstrings to make them
    more generic and reusable across different resource types. This function
    resolves those templates with the actual resource kind.

    Args:
        docstring: The docstring with Jinja template variables.
        resource_name: The name of the resource (e.g., "service", "pod", "tenant").

    Returns:
        The resolved docstring with template variables replaced.

    Example:
        >>> doc = "List all {{kind}} resources"
        >>> resolve_docstring_template(doc, "service")
        'List all service resources'
    """
    if not docstring:
        return docstring

    # Create a Jinja template from the docstring
    template = Template(docstring)

    # Render the template with the resource kind
    # The 'kind' variable is used in the templates as {{kind}} or {{kind | lower}}
    result = template.render(kind=resource_name)

    # if has_jinja:
    #     print(f"     Output docstring (first 400 chars): {result[:400]}")

    return result


def get_docstring_summary(docstring: str) -> str:
    """Extract subject from a docstring.

    Args:
        docstring: The docstring to parse.

    Returns:
        A formatted string containing the subject.
    """
    if not docstring:
        return ""

    # Split by double newlines to separate paragraphs
    # 1. Subject
    # 2. Description
    # 3. ... (Args, etc.)
    parts = docstring.strip().split('\n\n')

    if not parts:
        return ""

    subject = parts[0].replace('\n', ' ').strip()

    if subject:
        return f" - {subject}"

    return ""
