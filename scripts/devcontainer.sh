#!/bin/bash
set -e

op_prefix=""
if [ -f "./op.env" ]; then
  op_prefix="op run --env-file=./op.env --"
  echo "[DEBUG] op.env found, using 1Password" >&2
else
  echo "[DEBUG] no op.env file found" >&2
fi

$op_prefix devcontainer up --workspace-folder . && code --folder-uri="vscode-remote://dev-container+$(pwd | tr -d '\n' | xxd -c 256 -p)/workspaces/$(basename "$(pwd)")"
