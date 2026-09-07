#!/usr/bin/env python3
"""Export resume and cover letter PDFs for an application folder."""

from __future__ import annotations

import argparse
import subprocess
import sys
from pathlib import Path

SCRIPTS = Path(__file__).resolve().parent
ROOT = SCRIPTS.parent
sys.path.insert(0, str(SCRIPTS))

from config_lib import file_prefix, load_config  # noqa: E402


def ensure_pymupdf() -> None:
    try:
        import fitz  # noqa: F401
    except ImportError:
        subprocess.check_call(
            [sys.executable, "-m", "pip", "install", "pymupdf>=1.24.0"],
            cwd=ROOT,
        )


def _render_module():
    from render_resume_pdf import render_markdown_to_pdf  # noqa: E402

    return render_markdown_to_pdf


def export_slug(slug: str) -> list[Path]:
    ensure_pymupdf()
    render_markdown_to_pdf = _render_module()
    prefix = file_prefix(load_config())

    app_dir = ROOT / "applications" / slug
    if not app_dir.is_dir():
        raise FileNotFoundError(f"Application folder not found: {app_dir}")

    written: list[Path] = []
    markdown_files = sorted(app_dir.glob(f"{prefix}-*.md"))
    if not markdown_files:
        raise FileNotFoundError(f"No {prefix}-*.md files in {app_dir}")

    for md_path in markdown_files:
        pdf_path = md_path.with_suffix(".pdf")
        render_markdown_to_pdf(md_path, pdf_path)
        if not pdf_path.is_file() or pdf_path.stat().st_size == 0:
            raise RuntimeError(f"PDF export failed or empty: {pdf_path}")
        written.append(pdf_path)
        print(f"Wrote: {pdf_path}")

    return written


def main(argv: list[str]) -> int:
    parser = argparse.ArgumentParser(description="Export application markdown to PDF")
    parser.add_argument("slug", nargs="?", help="Application folder slug under applications/")
    parser.add_argument(
        "--check-deps",
        action="store_true",
        help="Install pymupdf and run PDF export smoke test",
    )
    args = parser.parse_args(argv[1:])

    ensure_pymupdf()

    if args.check_deps:
        test_script = SCRIPTS / "test_pdf_export.py"
        if not test_script.is_file():
            print(f"Error: missing {test_script}", file=sys.stderr)
            return 1
        subprocess.check_call([sys.executable, str(test_script)], cwd=ROOT)
        print("PDF dependencies OK")
        return 0

    if not args.slug:
        parser.error("slug is required unless --check-deps is used")

    try:
        export_slug(args.slug)
    except Exception as exc:  # noqa: BLE001
        print(f"Error: {exc}", file=sys.stderr)
        return 1

    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
