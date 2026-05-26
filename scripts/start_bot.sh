#!/usr/bin/env bash
set -euo pipefail

label="com.alfa.jira-bot"
domain="gui/$(id -u)"

launchctl kickstart -k "$domain/$label"
echo "Bot started: $label"
