---
description: 'Python coding conventions and guidelines'
applyTo: '**/*.yaml, **/*.yml'
---

# YAML Coding Conventions

Use yaml best practices to format yaml files corectly.

## General Instructions

- yaml arrays should be aligned with the parent key versus two spaces in
  - Example:
    ```yaml
    fruits:
    - apple
    - banana
    - cherry
    ```
- Use spaces instead of tabs for indentation (2 spaces per level).
- Maintain consistent indentation throughout the file.
- Use lowercase letters for keys and separate words with underscores or hyphens.
- don't use double or single quotes unless the string has special characters or starts with a number
- Use comments (`#`) to explain complex sections or provide context.
