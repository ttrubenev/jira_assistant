#!/usr/bin/env bash
set -euo pipefail

label="com.company.jira-assistant-bot"
domain="gui/$(id -u)"

launchctl kickstart -k "$domain/$label"
echo "Bot started: $label"
