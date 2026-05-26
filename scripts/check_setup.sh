#!/usr/bin/env bash
set -euo pipefail

cd "$(dirname "$0")/.."

PYTHONPATH=src .venv/bin/python -m jira_assistant_bot.discover
