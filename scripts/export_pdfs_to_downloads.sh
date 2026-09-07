#!/usr/bin/env bash
set -euo pipefail

script_dir="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
skill_dir="$(cd "${script_dir}/.." && pwd)"
venv_python="${skill_dir}/.venv/bin/python"
renderer="${script_dir}/render_resume_pdf.py"
ensure_fonts="${script_dir}/ensure_fonts.sh"

if [[ $# -lt 1 ]]; then
  echo "Usage: export_pdfs_to_downloads.sh <application-folder>"
  echo "Example: export_pdfs_to_downloads.sh ~/.cursor/skills/job-applications/applications/xero-backend-graduate"
  exit 2
fi

app_dir="$1"
downloads_dir="${HOME}/Downloads"

if [[ ! -d "$app_dir" ]]; then
  echo "Error: application folder not found: $app_dir" >&2
  exit 1
fi

if [[ ! -x "$venv_python" ]]; then
  echo "Error: Python venv not found at ${skill_dir}/.venv" >&2
  exit 1
fi

if [[ ! -f "$renderer" ]]; then
  echo "Error: renderer not found: $renderer" >&2
  exit 1
fi

if [[ ! -x "$ensure_fonts" ]]; then
  echo "Error: ensure_fonts script not found: $ensure_fonts" >&2
  exit 1
fi

"$ensure_fonts"

mkdir -p "$downloads_dir"

shopt -s nullglob
md_files=( "$app_dir"/*.md )
if [[ ${#md_files[@]} -eq 0 ]]; then
  echo "Error: no .md files found in: $app_dir" >&2
  exit 1
fi

for md in "${md_files[@]}"; do
  base="$(basename "$md")"
  case "$base" in
    notes.md) continue ;;
  esac

  pdf_name="${base%.md}.pdf"
  out_pdf="$downloads_dir/$pdf_name"
  "$venv_python" "$renderer" "$md" "$out_pdf"
done
