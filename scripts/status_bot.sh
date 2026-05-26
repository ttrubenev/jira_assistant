#!/usr/bin/env bash
set -euo pipefail

label="com.company.jira-assistant-bot"
domain="gui/$(id -u)"

launchctl print "$domain/$label"
