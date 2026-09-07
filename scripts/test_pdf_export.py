#!/usr/bin/env python3
"""Smoke-test PDF export using the configured applicant identity."""

from __future__ import annotations

import sys
import tempfile
from pathlib import Path

SCRIPTS = Path(__file__).resolve().parent
sys.path.insert(0, str(SCRIPTS))

from config_lib import contact_line, file_prefix, full_name, load_config  # noqa: E402
from render_resume_pdf import render_markdown_to_pdf  # noqa: E402


def main() -> int:
    cfg = load_config()
    name = full_name(cfg)
    contact = contact_line(cfg)
    prefix = file_prefix(cfg)

    sample_resume = f"""{name}
{contact}

## SUMMARY
Sample summary for PDF smoke test. Replace with real content in master-resume.md.

## EXPERIENCE
Software Intern
Example Org City Country

- Built a small feature to reduce manual steps for the team

## PROJECTS
Demo Project — Sample (Solo)
Python, FastAPI
github.com/example/demo

- Delivered a working prototype so reviewers can validate the PDF pipeline

## SKILLS
Languages: Python
Tools: Git

## EDUCATION
Bachelor of Example
Example University • Country • 2024
"""

    sample_cover = f"""Dear Hiring Team,

I am writing to apply for the Example Role at Example Company. This letter is only a PDF smoke test.

Kind regards,
{name}
{cfg["applicant"].get("phone", "")}
{cfg["applicant"].get("email", "")}
"""

    with tempfile.TemporaryDirectory() as tmp:
        tmp_path = Path(tmp)
        cases = [
            (f"{prefix}-Resume-Test.pdf", sample_resume),
            (f"{prefix}-CoverLetter-Test.pdf", sample_cover),
        ]
        for filename, body in cases:
            md = tmp_path / filename.replace(".pdf", ".md")
            pdf = tmp_path / filename
            md.write_text(body, encoding="utf-8")
            render_markdown_to_pdf(md, pdf)
            if not pdf.is_file() or pdf.stat().st_size == 0:
                print(f"FAIL: empty PDF {filename}", file=sys.stderr)
                return 1
            print(f"OK: {filename} ({pdf.stat().st_size} bytes)")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
