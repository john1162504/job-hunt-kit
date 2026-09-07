#!/usr/bin/env bash
# Start the local job-application review UI.
set -euo pipefail

root="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
port="${1:-8765}"

cd "$root"
exec python3 review-ui/server.py "$port"
