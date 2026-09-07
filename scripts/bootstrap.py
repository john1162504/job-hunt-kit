#!/usr/bin/env python3
"""Bootstrap a personal job-hunt-kit from config.example.json / config.json.

Usage:
  cp config.example.json config.json   # edit your details
  python3 scripts/bootstrap.py
"""

from __future__ import annotations

import json
import shutil
import sys
from pathlib import Path

SCRIPTS = Path(__file__).resolve().parent
ROOT = SCRIPTS.parent
sys.path.insert(0, str(SCRIPTS))

from config_lib import (  # noqa: E402
    CONFIG_PATH,
    EXAMPLE_PATH,
    ConfigError,
    contact_line,
    file_prefix,
    full_name,
    load_config,
    substitute,
)


def write_if_missing(path: Path, content: str) -> str:
    if path.exists():
        return "kept"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")
    return "created"


def render_template(src_name: str, dest_name: str, cfg: dict) -> str:
    src = ROOT / "templates" / src_name
    dest = ROOT / dest_name
    text = substitute(src.read_text(encoding="utf-8"), cfg)
    dest.write_text(text, encoding="utf-8")
    return "rendered"


def profile_stub(cfg: dict) -> str:
    name = full_name(cfg)
    a = cfg["applicant"]
    return f"""# Professional Profile — {name}

Living source of truth for tailored resumes and cover letters.
**Never invent experience** beyond what is written here.

## Contact

- Name: {name}
- Phone: {a.get("phone", "")}
- Email: {a.get("email", "")}
- Links: {", ".join(a.get("links", []))}
- Location: {a.get("location_city", "")}, {a.get("location_country", "")}
- Work authorisation: {a.get("work_auth_note", "")}

## Target roles

- Primary: {", ".join(cfg["search"].get("primary", {}).get("titles", []))}
- Locations: {", ".join(cfg["search"].get("primary", {}).get("locations", []))}
- Adjacent (optional): {", ".join(cfg["search"].get("adjacent", {}).get("titles", []))} — only in {", ".join(cfg["search"].get("adjacent", {}).get("locations_required", []))}

## Summary (for yourself)

Write 4–6 sentences about your background, strengths, and what you want next.

## Skills

List only skills you can evidence in projects or work:

- Languages:
- Backend:
- Frontend:
- Databases:
- Tools / testing:

## Experience

For each role:

### Role title — Organisation (dates)

- Bullet with purpose + outcome
- …

## Projects

For each project:

### Project name — one-line description

- Stack:
- Link:
- Bullets (purpose + outcome):

## Education

- Degree, institution, year

## Claims to Avoid

List phrases or claims you must never put on a resume (unsupported slogans, inflated scope, etc.).

## Preferences

- Spelling: {a.get("spelling", "en-NZ")}
- Tone: professional, friendly, confident yet humble
- Cover letter: default yes when applying

## Changelog

- bootstrap: created profile stub
"""


def master_resume_stub(cfg: dict) -> str:
    name = full_name(cfg)
    contact = contact_line(cfg)
    return f"""{name}
{contact}

## SUMMARY
Replace this paragraph with a 4–5 sentence professional summary aimed at your target roles. End with the kind of role you want next.

## EXPERIENCE
Role Title
Organisation City Country

- Describe what you did, why it mattered, and what improved
- Add 2–4 more purpose + outcome bullets

## PROJECTS
Project Name — Short description (Solo|Team of N)
Tech, Stack, Comma, Separated
github.com/you/repo

- Purpose + outcome bullet
- Purpose + outcome bullet
- Purpose + outcome bullet

## SKILLS
Languages: …
Backend: …
Frontend: …
Databases: …
Testing & Tools: …

## EDUCATION
Your Degree Title
Institution • Country • Year
"""


def main() -> int:
    if not CONFIG_PATH.is_file():
        if EXAMPLE_PATH.is_file():
            shutil.copy(EXAMPLE_PATH, CONFIG_PATH)
            print(f"Created {CONFIG_PATH.name} from config.example.json")
            print("Using example identity for first render — edit config.json, then re-run bootstrap.\n")
        else:
            print("Error: config.example.json missing", file=sys.stderr)
            return 1

    try:
        cfg = load_config()
    except ConfigError as exc:
        print(f"Error: {exc}", file=sys.stderr)
        return 1

    name = full_name(cfg)
    prefix = file_prefix(cfg)
    if name == "Alex Example" or prefix == "AlexExample":
        print("Warning: config.json still uses the example identity (Alex Example).")
        print("Update applicant.full_name / file_prefix / email before going live.\n")

    actions = []
    actions.append(("profile.md", write_if_missing(ROOT / "profile.md", profile_stub(cfg))))
    actions.append(("master-resume.md", write_if_missing(ROOT / "master-resume.md", master_resume_stub(cfg))))
    actions.append(("tracked-jobs.json", write_if_missing(ROOT / "tracked-jobs.json", json.dumps({"jobs": []}, indent=2) + "\n")))

    # Always re-render agent prompts from templates + config
    for src, dest in [
        ("SKILL.md.tmpl", "SKILL.md"),
        ("templates.md.tmpl", "templates.md"),
        ("automation-instructions.md.tmpl", "automation-instructions.md"),
        ("automation-instructions-local-sync.md.tmpl", "automation-instructions-local-sync.md"),
    ]:
        actions.append((dest, render_template(src, dest, cfg)))

    # Generate layout reference PDF from master resume when possible
    master_md = ROOT / "master-resume.md"
    master_pdf = ROOT / "assets" / "Resume-Master.pdf"
    root_pdf = ROOT / "Resume-Master.pdf"
    try:
        from render_resume_pdf import render_markdown_to_pdf

        render_markdown_to_pdf(master_md, master_pdf)
        shutil.copy(master_pdf, root_pdf)
        actions.append(("assets/Resume-Master.pdf", "rendered"))
    except Exception as exc:  # noqa: BLE001
        actions.append(("assets/Resume-Master.pdf", f"skipped ({exc})"))

    print(f"Bootstrapped for {name} (file prefix: {prefix})")
    for path, status in actions:
        print(f"  {status:10} {path}")
    print()
    print("Next:")
    print("  1. Fill in profile.md and master-resume.md with real experience")
    print("  2. Re-run: python3 scripts/bootstrap.py")
    print("  3. Push this repo to GitHub (private recommended)")
    print("  4. Create a Cursor Automation using automation-instructions.md")
    print("  5. On your Mac: ./scripts/install_mac_sync_launchagent.sh")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
