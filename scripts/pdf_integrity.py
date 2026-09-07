#!/usr/bin/env python3
"""Font and PDF text-integrity checks for application PDF export."""

from __future__ import annotations

from pathlib import Path

import fitz

FONTS_DIR = Path(__file__).resolve().parent.parent / "assets" / "fonts"

# Fonts used by render_resume_pdf.py. Only full fonts belong here — never PDF subset extractions.
REQUIRED_FONTS = {
    "arial": "Arial-Regular.ttf",
    "arial-bold": "Arial-Bold.ttf",
    "arial-bold-italic": "Arial-Bold-Italic.ttf",
}

# Subset fonts extracted from the master PDF omit glyphs and must not be wired back in.
DEPRECATED_SUBSET_FONTS = (
    "BCDFEE_Arial-BoldMT.ttf",
    "BCDIEE_Arial-BoldMT.ttf",
    "BCDGEE_ArialMT.ttf",
    "BCDHEE_ArialMT.ttf",
    "BCDKEE_Arial-BoldItalicMT.ttf",
    "BCDLEE_Arial-BoldItalicMT.ttf",
    "BCDMEE_Calibri-Bold.ttf",
    "BCDNEE_Calibri-Bold.ttf",
    "BCDJEE_SymbolMT.ttf",
)

MIN_FONT_BYTES = 200_000

# Glyphs that must render in body and bold text. Includes en dash and bullet used by the renderer.
REQUIRED_GLYPHS = (
    "abcdefghijklmnopqrstuvwxyz"
    "ABCDEFGHIJKLMNOPQRSTUVWXYZ"
    "0123456789"
    ".,;:!?()|'"
    "\u2013\u2022"
)

CORRUPTION_MARKERS = ("\x00", "\xad", "\ufffd", "\ufffe", "\uffff")

# PyMuPDF/Arial TextWriter encodes ASCII hyphen (U+002D) as soft hyphen (U+00AD), which many
# viewers display as a stray symbol. For prose and displayed project URLs, normalise to en dash
# (U+2013). Project URL *links* must still use ASCII hyphens via href_from_displayed_url().
UNICODE_REPLACEMENTS = {
    "\u00ad": "",  # soft hyphen
    "\u2010": "\u2013",  # hyphen
    "\u2011": "\u2013",  # non-breaking hyphen
    "\u2012": "\u2013",  # figure dash
    "\u2014": "\u2013",  # em dash
    "\u2212": "\u2013",  # minus sign
    "\u2018": "'",  # left single quote
    "\u2019": "'",  # right single quote / apostrophe
    "\u201a": "'",  # single low-9 quote
    "\u201b": "'",  # single high-reversed-9 quote
    "\u201c": '"',  # left double quote
    "\u201d": '"',  # right double quote
    "\u201e": '"',  # double low-9 quote
    "\u201f": '"',  # double high-reversed-9 quote
    "\u00a0": " ",  # non-breaking space
}

DASH_LIKE = ("\u00ad", "\u2010", "\u2011", "\u2012", "\u2013", "\u2014", "\u2212")


def normalise_pdf_text(text: str) -> str:
    """Normalise prose for PDF drawing. ASCII hyphens become en dashes (PyMuPDF/Arial soft-hyphen workaround)."""
    for old, new in UNICODE_REPLACEMENTS.items():
        text = text.replace(old, new)
    return text.replace("-", "\u2013")


def href_from_displayed_url(url: str) -> str:
    """Build a clickable https URI with ASCII hyphens only (safe for github.com paths)."""
    cleaned = url.strip()
    for dash in DASH_LIKE:
        cleaned = cleaned.replace(dash, "-")
    if cleaned.startswith(("http://", "https://")):
        return cleaned
    return f"https://{cleaned}"


MACOS_FONT_SOURCES = {
    "Arial-Regular.ttf": "/System/Library/Fonts/Supplemental/Arial.ttf",
    "Arial-Bold.ttf": "/System/Library/Fonts/Supplemental/Arial Bold.ttf",
    "Arial-Bold-Italic.ttf": "/System/Library/Fonts/Supplemental/Arial Bold Italic.ttf",
}


def validate_font_files(fonts_dir: Path = FONTS_DIR) -> list[str]:
    errors: list[str] = []

    for key, filename in REQUIRED_FONTS.items():
        path = fonts_dir / filename
        if not path.exists():
            errors.append(f"Missing required font for {key!r}: {path}")
            continue

        size = path.stat().st_size
        if size < MIN_FONT_BYTES:
            errors.append(
                f"Font {filename} is only {size:,} bytes and looks like a subset font. "
                f"Run scripts/ensure_fonts.sh to install full Arial files."
            )
            continue

        font = fitz.Font(fontfile=str(path))
        missing = [char for char in REQUIRED_GLYPHS if not font.has_glyph(ord(char))]
        if missing:
            preview = "".join(missing[:20])
            suffix = "..." if len(missing) > 20 else ""
            errors.append(f"Font {filename} is missing glyphs: {preview}{suffix}")

    return errors


def validate_pdf_text_integrity(pdf_path: Path) -> list[str]:
    errors: list[str] = []
    doc = fitz.open(pdf_path)
    try:
        text = "".join(page.get_text() for page in doc)

        if not text.strip():
            errors.append(f"PDF appears empty: {pdf_path}")
            return errors

        for marker in CORRUPTION_MARKERS:
            if marker in text:
                label = {
                    "\x00": "NUL",
                    "\xad": "soft hyphen (U+00AD)",
                    "\ufffd": "replacement character (U+FFFD)",
                    "\ufffe": "BOM (U+FFFE)",
                    "\uffff": "BOM (U+FFFF)",
                }[marker]
                errors.append(f"PDF contains {label}: {pdf_path}")

        # Displayed GitHub paths use en dashes (Arial/TextWriter soft-hyphen workaround).
        # Clickable link URIs must still resolve to ASCII-hyphen https URLs.
        for page in doc:
            for link in page.get_links():
                uri = link.get("uri") or ""
                if "github.com/" not in uri.lower():
                    continue
                if any(dash in uri for dash in DASH_LIKE):
                    errors.append(f"PDF link URI contains a non-ASCII dash: {uri!r} in {pdf_path}")
                if not uri.startswith("https://"):
                    errors.append(f"PDF GitHub link should use https://: {uri!r} in {pdf_path}")
    finally:
        doc.close()

    return errors


def ensure_font_files(fonts_dir: Path = FONTS_DIR) -> list[str]:
    """Copy full Arial fonts from macOS when missing or too small. Returns actions taken."""
    actions: list[str] = []
    fonts_dir.mkdir(parents=True, exist_ok=True)

    for dest_name, source in MACOS_FONT_SOURCES.items():
        dest = fonts_dir / dest_name
        source_path = Path(source)
        needs_copy = not dest.exists() or dest.stat().st_size < MIN_FONT_BYTES

        if not needs_copy:
            continue

        if not source_path.exists():
            actions.append(f"skipped {dest_name}: source not found at {source_path}")
            continue

        dest.write_bytes(source_path.read_bytes())
        actions.append(f"installed {dest_name} from {source_path}")

    return actions
