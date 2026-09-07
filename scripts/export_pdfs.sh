#!/usr/bin/env bash
set -euo pipefail

repo_root="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
slug="${1:?Usage: export_pdfs.sh <application-slug>}"

exec python3 "${repo_root}/scripts/export_application_pdfs.py" "$slug"
