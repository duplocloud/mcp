# Contributing

Follow these steps to be proper. There is a lot of very specific
steps and automations, please read this entire document before starting. Many
questions will be answered by simply getting everything setup exactly the same
way in the instructions.

## Clone the Repo

Clone the repo from Github.

```sh
git clone git@github.com:duplocloud/mcp.git
```

## Installation

To get your development environment set up, you'll want to create a virtual environment and install the project dependencies. This can be done manually, by using the provided script, or with a VSCode Task.

### Manual Setup

First, create and activate a Python virtual environment. This keeps your project dependencies isolated.

```sh
python3 -m venv .venv
source .venv/bin/activate
```

Now, install dependencies in editable mode so you can use step through debugging. All of the optional dependencies are included within the square brackets. You can see what they all are in the [`pyproject.toml`](pyproject.toml) file.

```sh
pip install --editable '.[test]'
```

### Scripted Setup

Alternatively, you can just run the `init.sh` script to do all of this for you.

```sh
./scripts/init.sh
```

### VSCode Task

If you are using VSCode, you can run the `init` task to set up your environment.

1.  Open the Command Palette (`Ctrl+Shift+P` or `Cmd+Shift+P`).
2.  Type "Tasks: Run Task".
3.  Select the `init` task from the list.

## Running the Application

Once your environment is set up, you can run the MCP server using the unified `Up` task in VSCode or by running the `up.sh` script directly.

### VSCode Task

If you are using VSCode, you can run the `Up` task to start the application.

1.  Open the Command Palette (`Ctrl+Shift+P` or `Cmd+Shift+P`).
2.  Type "Tasks: Run Task".
3.  Select the `Up` task from the list.
4.  You will be prompted to select a run mode (`local` or `docker`).
5.  You will be prompted whether to rebuild the Docker image if you chose `docker` mode.

This will start the server based on your selections.

### Manual Script

You can also run the `up.sh` script from your terminal.

```sh
# Run locally
./scripts/up.sh --mode local

# Run with Docker and rebuild the image
./scripts/up.sh --mode docker --build true
```

This provides a consistent way to start the server in different environments.


## Building the Application

### Docker Image

You can build the Docker image using a VSCode task or by running the command manually.

#### VSCode Task

1.  Open the Command Palette (`Ctrl+Shift+P` or `Cmd+Shift+P`).
2.  Type "Tasks: Run Task".
3.  Select the `build image` task from the list.

#### Manual Command

```sh
docker buildx bake
```

## Running Tests

The unit tests are a good starting place for development.

### VSCode Task

1.  Open the Command Palette (`Ctrl+Shift+P` or `Cmd+Shift+P`).
2.  Type "Tasks: Run Task".
3.  Select the `test` task from the list.

### Manual Command

```sh
pytest
```

## Docstrings

The convention for docs in code is [Google style docstrings](https://google.github.io/styleguide/pyguide.html).

Here is an example of the docstring format.

```python
def my_function(param1, param2) -> dict:
    """This is a function that does something.

    Args:
      param1: The first parameter.
      param2: The second parameter.

    Returns:
      A dictionary with a message.

    Raises:
      ValueError: If the value is not correct.
"""
    if not param1:
        raise ValueError("param1 is required")
    return {"message": f"Hello {param2}"}
```

## Changelog

Make sure to take note of your changes in the changelog. This is done by updating the `CHANGELOG.md` file. Add any new details under the `## [Unreleased]` section.
When a new version is published, the word `Unreleased` will be replaced with the version number and the date. The section will also be the detailed release notes under releases in Github. The checks on the PR will fail if you don't add any notes in the changelog.

## Signed Commits

This is a public repo, one cannot simply trust that a commit came from who it says it did. To ensure the integrity of the commits, all commits must be signed. Your commits and PR will be rejected if they are not signed. Please read more about how to do this here if you do not know how: [Github Signing Commits](https://docs.github.com/en/github/authenticating-to-github/managing-commit-signature-verification/signing-commits). Ideally, if you have 1password, please follow these instructions: [1Password Signing Commits](https://blog.1password.com/git-commit-signing/).

## Version Bump

Get the current version:

```sh
python -m setuptools_scm
```

When building the artifact the setuptools scm tool will use the a snazzy semver logic to determine version.

_ref:_ [SetupTools SCM](https://pypi.org/project/setuptools-scm/)

When Ready to publish a new version live, a maintainer will trigger the publish workflow. This will bump the version, build the artifact, and push the new version to pypi.

## VSCode Setup

To be helpful as possible, all of the sweet spot configurations for VSCode are included in the `.vscode` folder. Although these files are committed they have been ignored from the working tree, so feel free to update them as you see fit and they will not be committed.

Here is how git is ignoring the files.

```sh
git update-index --skip-worktree .vscode/settings.json
```

### Tasks

All of the commands described above have been implemented as VSCode tasks in the `.vscode/tasks.json`. This goes well with the [spmeesseman.vscode-taskexplorer](https://marketplace.visualstudio.com/items?itemName=spmeesseman.vscode-taskexplorer) extension which gives you a nice little button to run the tasks.

### Devcontainer

The `.devcontainer.json` file is included for quickly spinning up a working environment. This is a good way to ensure that all of the dependencies are installed and the correct version of python is being used without fighting with any nuances present in your local environment. It is highly recommended to use this as there will be the least amount of issues setting up the environment as well as getting better results when using Copilot.

Before starting, you must create a `.env` file by copying `.env.example` and filling in your credentials. This file is critical for the application to run.

The devcontainer automatically loads the `.env` file, making the variables available to your shell. VS Code is also configured to use this as an `envFile` for the Python extension, so debugging and terminal sessions have the correct environment. The tasks in `.vscode/tasks.json` (like `start`) rely on these environment variables to connect to DuploCloud.

## Using GitHub Copilot

This repository is optimized for development with GitHub Copilot.

-   **Pre-configured**: The project includes instructions and prompts in the `.github/` directory to guide Copilot in understanding the codebase and development patterns.
-   **Devcontainer/Codespaces Recommended**: It is highly recommended to use the provided Devcontainer or GitHub Codespaces. This ensures that Copilot has the correct context of the isolated Python environment, dependencies, and VS Code setup, leading to more accurate and helpful suggestions while avoiding conflicts with your local machine's configuration.
