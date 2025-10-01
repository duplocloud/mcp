#!/bin/bash
set -e

# Create a virtual environment
python3 -m venv .venv

# Activate the virtual environment and install dependencies
source .venv/bin/activate
pip install -e .
