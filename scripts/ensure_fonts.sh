#!/usr/bin/env bash
set -euo pipefail

script_dir="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
skill_dir="$(cd "${script_dir}/.." && pwd)"
venv_python="${skill_dir}/.venv/bin/python"

if [[ ! -x "$venv_python" ]]; then
  echo "Error: Python venv not found at ${skill_dir}/.venv" >&2
  echo "Create it with: python3 -m venv ${skill_dir}/.venv && ${skill_dir}/.venv/bin/pip install pymupdf" >&2
  exit 1
fi

PYTHONPATH="${script_dir}" "$venv_python" -c "
from pdf_integrity import ensure_font_files, validate_font_files
import sys

for action in ensure_font_files():
    print(action)

errors = validate_font_files()
if errors:
    print('Font validation failed:', file=sys.stderr)
    for error in errors:
        print(f'  - {error}', file=sys.stderr)
    raise SystemExit(1)

print('Font validation passed.')
"
