#!/usr/bin/env bash
set -euo pipefail

cd "$(dirname "$0")/.."

label="com.company.jira-assistant-bot"
app_dir="${JIRA_ASSISTANT_BOT_HOME:-$HOME/.jira-assistant-bot}"
domain="gui/$(id -u)"
plist_dir="$HOME/Library/LaunchAgents"
plist_path="$plist_dir/$label.plist"

if [[ ! -d ".venv" ]]; then
  echo "Missing .venv. Run: python3 -m venv .venv && .venv/bin/python -m pip install ." >&2
  exit 1
fi

if [[ ! -f ".env" ]]; then
  echo "Missing .env. Configure it before installing the service." >&2
  exit 1
fi

mkdir -p "$app_dir" "$app_dir/logs" "$plist_dir"

/usr/bin/rsync -a \
  --exclude '__pycache__' \
  --exclude '*.pyc' \
  src pyproject.toml .env .env.example .venv \
  "$app_dir/"

chmod 700 "$app_dir"
chmod 600 "$app_dir/.env"

cat > "$plist_path" <<PLIST
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN"
  "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
  <key>Label</key>
  <string>$label</string>

  <key>WorkingDirectory</key>
  <string>$app_dir</string>

  <key>EnvironmentVariables</key>
  <dict>
    <key>PYTHONPATH</key>
    <string>$app_dir/src</string>
  </dict>

  <key>ProgramArguments</key>
  <array>
    <string>$app_dir/.venv/bin/python</string>
    <string>-m</string>
    <string>jira_assistant_bot</string>
  </array>

  <key>RunAtLoad</key>
  <true/>

  <key>KeepAlive</key>
  <true/>

  <key>StandardOutPath</key>
  <string>$app_dir/logs/bot.out.log</string>

  <key>StandardErrorPath</key>
  <string>$app_dir/logs/bot.err.log</string>
</dict>
</plist>
PLIST

chmod 644 "$plist_path"

launchctl bootout "$domain" "$plist_path" >/dev/null 2>&1 || true
launchctl bootstrap "$domain" "$plist_path"
launchctl kickstart -k "$domain/$label"

echo "Installed and started $label"
echo "Runtime: $app_dir"
echo "Logs: $app_dir/logs/bot.out.log and $app_dir/logs/bot.err.log"
