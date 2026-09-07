#!/usr/bin/env bash
# Pull cloud automation results onto this Mac and stage PDFs in ~/Downloads.
# Usage:
#   ./scripts/sync_cloud_results.sh           # pull + copy recent PDFs
#   ./scripts/sync_cloud_results.sh --today   # also print/open today's daily-runs report
#   ./scripts/sync_cloud_results.sh --open    # open the report in Cursor / default app
set -euo pipefail

root="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
downloads_dir="${HOME}/Downloads"
open_report=0
focus_today=0

for arg in "$@"; do
  case "$arg" in
    --open) open_report=1 ;;
    --today) focus_today=1 ;;
    -h|--help)
      sed -n '2,8p' "$0"
      exit 0
      ;;
    *)
      echo "Unknown arg: $arg" >&2
      exit 2
      ;;
  esac
done

cd "$root"

if [[ ! -f "$root/config.json" ]]; then
  echo "Missing config.json. Copy config.example.json and run: python3 scripts/bootstrap.py" >&2
  exit 1
fi

pdf_glob="$(python3 - <<'PY'
import sys
from pathlib import Path
sys.path.insert(0, str(Path("scripts").resolve()))
from config_lib import pdf_glob, load_config
print(pdf_glob(load_config()))
PY
)"

git_auth() {
  if command -v gh >/dev/null 2>&1; then
    GIT_TERMINAL_PROMPT=0 git -c credential.helper='!gh auth git-credential' "$@"
  else
    GIT_TERMINAL_PROMPT=0 git "$@"
  fi
}

echo "==> Fetching origin..."
git_auth fetch origin

default_branch="main"
if git show-ref --verify --quiet "refs/remotes/origin/main"; then
  default_branch="main"
elif git show-ref --verify --quiet "refs/remotes/origin/master"; then
  default_branch="master"
fi

current_branch="$(git rev-parse --abbrev-ref HEAD)"
if [[ "$current_branch" != "$default_branch" ]]; then
  echo "Warning: on branch '$current_branch' (expected $default_branch)." >&2
  echo "Checking out $default_branch for sync..." >&2
  git checkout "$default_branch"
fi

echo "==> Fast-forwarding to origin/$default_branch..."
git_auth pull --ff-only origin "$default_branch"

mkdir -p "$downloads_dir"

copied=0
while IFS= read -r -d '' pdf; do
  base="$(basename "$pdf")"
  dest="$downloads_dir/$base"
  cp -f "$pdf" "$dest"
  echo "Copied: $dest"
  copied=$((copied + 1))
done < <(find "$root/applications" -type f -name "$pdf_glob" -mtime -2 -print0 2>/dev/null)

echo "==> Copied $copied PDF(s) matching $pdf_glob (last 2 days) into $downloads_dir"

today="$(date +%Y-%m-%d)"
report="$root/daily-runs/${today}.md"

if [[ -f "$report" ]]; then
  echo ""
  echo "==> Today's report: $report"
  echo "----------"
  cat "$report"
  echo "----------"
  if [[ "$open_report" -eq 1 ]]; then
    if command -v cursor >/dev/null 2>&1; then
      cursor "$report" >/dev/null 2>&1 || open "$report"
    else
      open "$report"
    fi
  fi
elif [[ "$focus_today" -eq 1 || "$open_report" -eq 1 ]]; then
  echo "No daily-runs/${today}.md yet — cloud run may still be in progress or failed."
  latest="$(ls -1t "$root"/daily-runs/[0-9][0-9][0-9][0-9]-*.md 2>/dev/null | head -1 || true)"
  if [[ -n "${latest:-}" ]]; then
    echo "Latest report: $latest"
    if [[ "$open_report" -eq 1 ]]; then
      if command -v cursor >/dev/null 2>&1; then
        cursor "$latest" >/dev/null 2>&1 || open "$latest"
      else
        open "$latest"
      fi
    fi
  fi
fi
