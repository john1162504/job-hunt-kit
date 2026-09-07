#!/usr/bin/env bash
# Install a macOS LaunchAgent that pulls cloud job-scanner results onto this Mac.
# Schedule comes from config.json schedule.local_sync_window (default 15:45–18:45).
set -euo pipefail

repo="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
sync_script="${repo}/scripts/sync_cloud_results.sh"

if [[ "$(uname -s)" != "Darwin" ]]; then
  echo "This installer is for macOS only (uname=$(uname -s))." >&2
  exit 1
fi

if [[ ! -f "${repo}/config.json" ]]; then
  echo "Missing config.json. Copy config.example.json and run: python3 scripts/bootstrap.py" >&2
  exit 1
fi

label="$(python3 - <<PY
import sys
from pathlib import Path
sys.path.insert(0, str(Path("${repo}") / "scripts"))
from config_lib import launch_agent_label, load_config
print(launch_agent_label(load_config()))
PY
)"

plist="${HOME}/Library/LaunchAgents/${label}.plist"
log_dir="${HOME}/Library/Logs/job-hunt-kit"
stdout_log="${log_dir}/sync-cloud-results.out.log"
stderr_log="${log_dir}/sync-cloud-results.err.log"

if [[ ! -x "$sync_script" ]]; then
  chmod +x "$sync_script"
fi

mkdir -p "${HOME}/Library/LaunchAgents" "$log_dir"

launchctl bootout "gui/$(id -u)/${label}" 2>/dev/null || true
launchctl unload "$plist" 2>/dev/null || true

# Every 15 minutes from 15:45 through 18:45 local time.
intervals=""
for hour in 15 16 17 18; do
  for minute in 0 15 30 45; do
    if [[ "$hour" -eq 15 && "$minute" -lt 45 ]]; then
      continue
    fi
    intervals+="
    <dict>
      <key>Hour</key>
      <integer>${hour}</integer>
      <key>Minute</key>
      <integer>${minute}</integer>
    </dict>"
  done
done

user_path="/opt/homebrew/bin:/usr/local/bin:/usr/bin:/bin:/usr/sbin:/sbin"

cat > "$plist" <<EOF
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
  <key>Label</key>
  <string>${label}</string>
  <key>ProgramArguments</key>
  <array>
    <string>/bin/bash</string>
    <string>${sync_script}</string>
    <string>--today</string>
  </array>
  <key>WorkingDirectory</key>
  <string>${repo}</string>
  <key>EnvironmentVariables</key>
  <dict>
    <key>PATH</key>
    <string>${user_path}</string>
    <key>HOME</key>
    <string>${HOME}</string>
  </dict>
  <key>StartCalendarInterval</key>
  <array>${intervals}
  </array>
  <key>RunAtLoad</key>
  <false/>
  <key>StandardOutPath</key>
  <string>${stdout_log}</string>
  <key>StandardErrorPath</key>
  <string>${stderr_log}</string>
</dict>
</plist>
EOF

launchctl bootstrap "gui/$(id -u)" "$plist" 2>/dev/null || launchctl load "$plist"

echo "Installed LaunchAgent: ${plist}"
echo "Schedule: every 15 minutes from 3:45 PM–6:45 PM local time (macOS clock)."
echo "Logs:"
echo "  ${stdout_log}"
echo "  ${stderr_log}"
echo ""
echo "If pull fails with GitHub auth errors, run once in Terminal: gh auth login"
echo "Then test: ${sync_script} --today --open"
echo "Unload later with: launchctl bootout gui/\$(id -u)/${label}"
