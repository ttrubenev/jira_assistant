#!/usr/bin/env bash
set -euo pipefail

label="com.alfa.jira-bot"
domain="gui/$(id -u)"
plist="$HOME/Library/LaunchAgents/$label.plist"

launchctl bootout "$domain" "$plist" >/dev/null 2>&1 || true
echo "Bot stopped: $label"
