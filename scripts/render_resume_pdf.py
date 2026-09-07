#!/usr/bin/env python3
"""Render resumes using layout/fonts/colors from assets/Resume-Master.pdf / master_layout.json."""

from __future__ import annotations

import json
import re
import sys
from pathlib import Path

import fitz

from pdf_integrity import (
    href_from_displayed_url,
    normalise_pdf_text,
    validate_font_files,
    validate_pdf_text_integrity,
)

try:
    from config_lib import contact_line, full_name, load_config
except ImportError:  # pragma: no cover
    load_config = None  # type: ignore[assignment]
    full_name = None  # type: ignore[assignment]
    contact_line = None  # type: ignore[assignment]

ROOT = Path(__file__).resolve().parent.parent
SCRIPTS = Path(__file__).resolve().parent
LAYOUT_PATH = SCRIPTS / "master_layout.json"
FONTS_DIR = ROOT / "assets" / "fonts"

FONT_FILES = {
    # Full Arial only. Never use subset fonts extracted from the master PDF.
    "arial": "Arial-Regular.ttf",
    "arial-bold": "Arial-Bold.ttf",
    "arial-bold-italic": "Arial-Bold-Italic.ttf",
}


def strip_markdown(text: str) -> str:
    text = re.sub(r"\[([^\]]+)\]\(([^)]+)\)", r"\1", text)
    text = re.sub(r"\*\*([^*]+)\*\*", r"\1", text)
    text = re.sub(r"\*([^*]+)\*", r"\1", text)
    text = re.sub(r"`([^`]+)`", r"\1", text)
    return text.strip()


def normalise_lines(text: str) -> list[str]:
    lines: list[str] = []
    for raw in text.splitlines():
        line = strip_markdown(raw.strip())
        if line in {"---", "***", "___"}:
            continue
        lines.append(line)
    return lines


def is_bullet(line: str) -> bool:
    return line.startswith("- ") or line.startswith("• ")


def bullet_text(line: str) -> str:
    return line[2:].strip()


def is_section_heading(line: str) -> bool:
    return line.startswith("## ")


def section_name(line: str) -> str:
    return line[3:].strip().upper()


def is_project_url(line: str) -> bool:
    lowered = line.lower()
    return "github.com/" in lowered or lowered.startswith("http")


def is_skill_line(line: str) -> bool:
    return ":" in line and not line.startswith("http")


def format_education_institution(line: str) -> str:
    return line


def _defaults() -> tuple[str, str, str]:
    """Return (default_name, default_contact, location_city_lower)."""
    if load_config is None:
        return ("Your Name", "email@example.com", "")
    try:
        cfg = load_config()
        city = (cfg.get("applicant", {}).get("location_city") or "").strip().lower()
        return (full_name(cfg), contact_line(cfg), city)
    except Exception:  # noqa: BLE001
        return ("Your Name", "email@example.com", "")


def parse_resume(text: str) -> dict:
    lines = normalise_lines(text)
    default_name, default_contact, location_city = _defaults()
    name = default_name
    idx = 0

    if lines:
        if lines[0].startswith("# "):
            name = lines[0][2:].strip() or name
            idx = 1
        elif not is_section_heading(lines[0]):
            name = lines[0] or name
            idx = 1

    while idx < len(lines) and not lines[idx]:
        idx += 1

    contact = ""
    if idx < len(lines) and not is_section_heading(lines[idx]):
        contact = lines[idx]
        idx += 1

    while idx < len(lines) and not lines[idx]:
        idx += 1

    # Skip a standalone location line under the contact block (common resume mistake).
    if idx < len(lines) and location_city and lines[idx].lower().startswith(location_city):
        idx += 1
        while idx < len(lines) and not lines[idx]:
            idx += 1

    sections: dict[str, list] = {
        "SUMMARY": [],
        "EXPERIENCE": [],
        "PROJECTS": [],
        "SKILLS": [],
        "EDUCATION": [],
    }
    current = None

    while idx < len(lines):
        line = lines[idx]
        if not line:
            idx += 1
            continue

        if is_section_heading(line):
            heading = section_name(line)
            current = heading if heading in sections else None
            idx += 1
            continue

        if line.startswith("### "):
            line = line[4:].strip()

        if current is None:
            idx += 1
            continue

        if current == "SUMMARY":
            sections["SUMMARY"].append(line)
            idx += 1
            continue

        if current == "EXPERIENCE":
            if is_bullet(line):
                if sections["EXPERIENCE"] and isinstance(sections["EXPERIENCE"][-1], dict):
                    sections["EXPERIENCE"][-1]["bullets"].append(bullet_text(line))
            else:
                entry = {"title": line, "organisation": "", "bullets": []}
                idx += 1
                while idx < len(lines) and not lines[idx]:
                    idx += 1
                if idx < len(lines) and not is_section_heading(lines[idx]) and not is_bullet(lines[idx]):
                    entry["organisation"] = lines[idx]
                    idx += 1
                sections["EXPERIENCE"].append(entry)
                continue
            idx += 1
            continue

        if current == "PROJECTS":
            if is_bullet(line):
                if sections["PROJECTS"] and isinstance(sections["PROJECTS"][-1], dict):
                    sections["PROJECTS"][-1]["bullets"].append(bullet_text(line))
            else:
                project = {"title": line, "tech": "", "url": "", "bullets": []}
                idx += 1
                while idx < len(lines) and not lines[idx]:
                    idx += 1
                if idx < len(lines) and not is_section_heading(lines[idx]) and not is_bullet(lines[idx]):
                    candidate = lines[idx]
                    if is_project_url(candidate):
                        project["url"] = candidate
                        idx += 1
                    else:
                        project["tech"] = candidate
                        idx += 1
                        while idx < len(lines) and not lines[idx]:
                            idx += 1
                        if idx < len(lines) and is_project_url(lines[idx]):
                            project["url"] = lines[idx]
                            idx += 1
                sections["PROJECTS"].append(project)
                continue
            idx += 1
            continue

        if current == "SKILLS":
            if is_skill_line(line):
                label, _, value = line.partition(":")
                sections["SKILLS"].append((label.strip(), value.strip()))
            idx += 1
            continue

        if current == "EDUCATION":
            if line.lower().startswith("academic transcript"):
                idx += 1
                continue
            sections["EDUCATION"].append(line)
            idx += 1
            continue

        idx += 1

    if not contact:
        contact = default_contact

    return {"name": name, "contact": contact, "sections": sections}


def parse_cover_letter(text: str) -> dict:
    lines = normalise_lines(text)
    paragraphs: list[str] = []
    closing: list[str] = []
    body: list[str] = []
    in_closing = False

    for line in lines:
        if not line:
            if body:
                paragraphs.append(" ".join(body))
                body = []
            continue
        if line.lower().startswith("kind regards"):
            in_closing = True
            closing.append(line)
            continue
        if in_closing:
            closing.append(line)
            continue
        body.append(line)

    if body:
        paragraphs.append(" ".join(body))
    return {"paragraphs": paragraphs, "closing": closing}


class MasterResumeRenderer:
    def __init__(self, layout_path: Path = LAYOUT_PATH):
        with layout_path.open(encoding="utf-8") as handle:
            self.layout = json.load(handle)

        self.page_w = self.layout["page"]["width"]
        self.page_h = self.layout["page"]["height"]
        self.left = self.layout["margins"]["left"]
        self.right = self.layout["margins"]["right"]
        self.bottom = self.layout["margins"]["bottom"]
        self.top_continued = self.layout["margins"]["top_continued"]
        self.spacing = self.layout["spacing"]
        self.lines = self.layout["lines"]
        self.typography = self.layout["typography"]
        self.subheading_x = self.typography.get("subheading_x", self.lines["github_x0"])

        self.text_color = tuple(self.layout["colors"]["text"])
        self.rule_gray = tuple(self.layout["colors"]["rule_gray"])
        self.rule_black = tuple(self.layout["colors"]["rule_black"])
        self.link_color = tuple(self.layout["colors"]["link_underline"])

        self.font_metrics: dict[str, fitz.Font] = {}
        self.doc = fitz.open()
        self.page = self._new_page()
        self.y = self.spacing["first_section_y"]

    def _font_obj(self, key: str) -> fitz.Font:
        if key not in self.font_metrics:
            self.font_metrics[key] = fitz.Font(fontfile=str(FONTS_DIR / FONT_FILES[key]))
        return self.font_metrics[key]

    def _register_fonts(self, page: fitz.Page) -> None:
        for name, filename in FONT_FILES.items():
            page.insert_font(fontname=name, fontfile=str(FONTS_DIR / filename))

    def _new_page(self) -> fitz.Page:
        page = self.doc.new_page(width=self.page_w, height=self.page_h)
        self._register_fonts(page)
        return page

    def ensure_space(self, needed: float) -> None:
        if self.y + needed <= self.bottom:
            return
        self.page = self._new_page()
        self.y = self.top_continued

    def draw_hline(self, y: float, x0: float, x1: float, color: tuple[float, float, float]) -> None:
        rect = fitz.Rect(x0, y, x1, y + self.lines["thickness"])
        self.page.draw_rect(rect, color=color, fill=color, width=0)

    def block_bottom(self, top: float, extra: float = 600) -> float:
        clip = fitz.Rect(0, top - 1, self.page_w, top + extra)
        bottom = top
        for block in self.page.get_text("dict", clip=clip)["blocks"]:
            bottom = max(bottom, block["bbox"][3])
        return bottom

    def wrap_text(self, text: str, font_key: str, fontsize: float, max_width: float) -> list[str]:
        font = self._font_obj(font_key)
        words = text.split()
        if not words:
            return []

        lines: list[str] = []
        current = words[0]
        for word in words[1:]:
            trial = f"{current} {word}"
            if font.text_length(trial, fontsize=fontsize) <= max_width:
                current = trial
            else:
                lines.append(current)
                current = word
        lines.append(current)
        return lines

    def place_lines(
        self,
        lines: list[str],
        *,
        fontname: str,
        font_key: str,
        fontsize: float,
        x: float,
        line_step: float | None = None,
        gap_after: float = 0.0,
    ) -> None:
        if not lines:
            return

        step = line_step if line_step is not None else self.spacing["bullet_line_step"]
        body_h = self.spacing["body_line_height"]
        self.ensure_space(step * len(lines))
        start_y = self.y
        for index, line in enumerate(lines):
            top = self.y
            self.place_single_line(line, fontname=fontname, fontsize=fontsize, x=x, top=top)
            if index < len(lines) - 1:
                self.y += step
        self.y = start_y + step * max(len(lines) - 1, 0) + body_h + gap_after

    def place_wrapped(
        self,
        text: str,
        *,
        fontname: str,
        font_key: str,
        fontsize: float,
        x0: float | None = None,
        x1: float | None = None,
        gap_after: float = 0.0,
    ) -> None:
        x0 = self.left if x0 is None else x0
        x1 = self.right if x1 is None else x1
        lines = self.wrap_text(text, font_key, fontsize, x1 - x0)
        self.place_lines(
            lines,
            fontname=fontname,
            font_key=font_key,
            fontsize=fontsize,
            x=x0,
            gap_after=gap_after,
        )

    def add_header(self, name: str, contact: str) -> None:
        name_top = self.spacing["name_y"]
        contact_top = self.spacing["contact_y"]

        self.place_single_line(name, fontname="arial-bold", fontsize=15.8, x=self._center_x(name, "arial-bold", 15.8), top=name_top)
        self.place_single_line(
            contact,
            fontname="arial-bold",
            fontsize=8.2,
            x=self._center_x(contact, "arial-bold", 8.2),
            top=contact_top,
        )
        self.draw_hline(
            self.spacing["header_rule_y"],
            self.lines["full_x0"],
            self.lines["full_x1"],
            self.rule_gray,
        )
        self.y = self.spacing["first_section_y"]

    def _center_x(self, text: str, font_key: str, fontsize: float) -> float:
        width = self._font_obj(font_key).text_length(text, fontsize=fontsize)
        return (self.page_w - width) / 2

    def place_single_line(
        self,
        text: str,
        *,
        fontname: str,
        fontsize: float,
        x: float,
        top: float,
    ) -> None:
        baseline = top + fontsize
        self.place_at_baseline(text, fontname=fontname, fontsize=fontsize, x=x, baseline=baseline)

    def place_at_baseline(
        self,
        text: str,
        *,
        fontname: str,
        fontsize: float,
        x: float,
        baseline: float,
    ) -> None:
        self.page.insert_text(
            (x, baseline),
            normalise_pdf_text(text),
            fontname=fontname,
            fontsize=fontsize,
            color=self.text_color,
        )

    def begin_section(self, title: str) -> None:
        self.ensure_space(60)
        title_top = self.y
        self.place_single_line(
            title.upper(),
            fontname="arial-bold",
            fontsize=12.0,
            x=self.left,
            top=title_top,
        )
        rule_y = title_top + self.spacing["section_title_to_rule"]
        self.draw_hline(rule_y, self.lines["full_x0"], self.lines["full_x1"], self.rule_black)
        self.y = rule_y + self.spacing["section_rule_to_content"]

    def end_section(self) -> None:
        rule_y = self.y + self.spacing["section_footer_gap"]
        self.draw_hline(rule_y, self.lines["full_x0"], self.lines["full_x1"], self.rule_gray)
        self.y = rule_y + self.spacing["section_footer_to_next"]

    def add_bullets(self, bullets: list[str]) -> None:
        bullet_x = self.typography["bullet_x"]
        text_x = self.typography["bullet_text_x"]
        bullet_font = self.typography.get("bullet_font", "arial")
        bullet_size = self.typography.get("bullet_size", 9.0)
        line_step = self.spacing["bullet_line_step"]

        for index, bullet in enumerate(bullets):
            lines = self.wrap_text(bullet, "arial", 9.0, self.right - text_x)
            self.ensure_space(line_step * max(len(lines), 1) + 20)

            top = self.y
            self.place_single_line("\u2022", fontname=bullet_font, fontsize=bullet_size, x=bullet_x, top=top)
            for line_index, line in enumerate(lines):
                line_top = top + (line_index * line_step)
                self.place_single_line(line, fontname="arial", fontsize=9.0, x=text_x, top=line_top)

            self.y = top + (line_step * len(lines)) + self.spacing["bullet_after_wrap"]

    def add_project_url(self, url: str) -> None:
        url_top = self.y
        # Display uses en dashes (Arial/TextWriter soft-hyphen workaround).
        # Clickable URI keeps ASCII hyphens: https://github.com/.../expense-tracker
        safe_url = normalise_pdf_text(url)
        href = href_from_displayed_url(url)
        url_font = self._font_obj("arial-bold")
        baseline = url_top + 9.0
        writer = fitz.TextWriter(self.page.rect)
        writer.append((self.subheading_x, baseline), safe_url, font=url_font, fontsize=9.0)
        writer.write_text(page=self.page, color=self.text_color)
        width = url_font.text_length(safe_url, fontsize=9.0)
        underline_y = url_top + self.typography["url_underline_offset"]
        x0 = self.lines["github_x0"]
        self.draw_hline(
            underline_y,
            x0,
            x0 + width,
            self.link_color,
        )
        link_rect = fitz.Rect(x0, url_top, x0 + width, underline_y + 2)
        self.page.insert_link({"kind": fitz.LINK_URI, "from": link_rect, "uri": href})
        self.y = underline_y + self.spacing["url_to_bullets"]

    def render(self, data: dict) -> fitz.Document:
        sections = data["sections"]
        self.add_header(data["name"], data["contact"])

        summary = " ".join(sections["SUMMARY"]).strip()
        if summary:
            self.begin_section("Summary")
            self.place_wrapped(summary, fontname="arial", font_key="arial", fontsize=9.0)
            self.end_section()

        if sections["EXPERIENCE"]:
            self.begin_section("Experience")
            for index, entry in enumerate(experience := sections["EXPERIENCE"]):
                self.ensure_space(70)
                title_top = self.y
                self.place_single_line(
                    entry["title"],
                    fontname="arial-bold",
                    fontsize=11.2,
                    x=self.left,
                    top=title_top,
                )
                org_top = title_top + self.spacing["job_title_to_org"]

                org = entry["organisation"]
                if org:
                    self.y = org_top
                    self.place_single_line(org, fontname="arial-bold", fontsize=9.0, x=self.subheading_x, top=org_top)
                    self.y = org_top + self.spacing["org_to_bullets"]
                else:
                    # Organisation line is optional; still keep consistent spacing before bullets.
                    self.y = org_top + self.spacing["org_to_bullets"]

                self.add_bullets(entry["bullets"])
                if index < len(experience) - 1:
                    self.y += self.spacing["experience_after_block"]
            self.end_section()

        if sections["PROJECTS"]:
            self.begin_section("Projects")
            self.y += self.spacing["projects_heading_to_first"] - self.spacing["section_rule_to_content"]
            for index, project in enumerate(projects := sections["PROJECTS"]):
                self.ensure_space(80)
                title_top = self.y
                self.place_single_line(
                    project["title"],
                    fontname="arial-bold",
                    fontsize=11.2,
                    x=self.left,
                    top=title_top,
                )

                if project["tech"]:
                    tech_top = title_top + self.spacing["project_title_to_tech"]
                    self.place_single_line(
                        project["tech"],
                        fontname="arial-bold-italic",
                        fontsize=9.0,
                        x=self.subheading_x,
                        top=tech_top,
                    )
                else:
                    tech_top = title_top

                if project["url"]:
                    self.y = tech_top + self.spacing["tech_to_url"]
                    self.add_project_url(project["url"])
                else:
                    self.y = tech_top + self.spacing["tech_to_url"]

                self.add_bullets(project["bullets"])
                if index < len(projects) - 1:
                    self.y += self.spacing["project_after_block"]
            self.end_section()

        if sections["SKILLS"]:
            self.begin_section("Skills")
            for index, (label, value) in enumerate(sections["SKILLS"]):
                self.ensure_space(16)
                top = self.y
                label_text = f"{label}:"
                self.place_single_line(label_text, fontname="arial-bold", fontsize=9.0, x=self.left, top=top)
                label_width = self._font_obj("arial-bold").text_length(label_text, fontsize=9.0)
                self.place_single_line(
                    f" {value}",
                    fontname="arial",
                    fontsize=9.0,
                    x=self.left + label_width,
                    top=top,
                )
                self.y = top + (self.spacing["skill_line"] if index < len(sections["SKILLS"]) - 1 else 9.0)
            self.end_section()

        if sections["EDUCATION"]:
            self.begin_section("Education")
            degree_top = self.y
            self.place_single_line(
                sections["EDUCATION"][0],
                fontname="arial-bold",
                fontsize=9.0,
                x=self.left,
                top=degree_top,
            )
            self.y = degree_top + 9.0 + self.spacing["degree_to_org"]
            if len(sections["EDUCATION"]) > 1:
                institution_top = self.y
                self.place_single_line(
                    format_education_institution(sections["EDUCATION"][1]),
                    fontname="arial",
                    fontsize=9.0,
                    x=self.left,
                    top=institution_top,
                )
                self.y = institution_top + 9.0

            self.end_section()

        return self.doc


class CoverLetterRenderer:
    TEXT_COLOR = (45 / 255, 61 / 255, 79 / 255)
    BOTTOM_MARGIN = 72.0
    TOP_MARGIN = 72.0
    FONT_SIZE = 11.0
    LINE_HEIGHT = 1.35

    def __init__(self) -> None:
        self.page_w = 595.5
        self.page_h = 842.25
        self.doc = fitz.open()
        self.page = self._new_page()
        self.y = self.TOP_MARGIN
        self.left = 72.0
        self.right = 523.5

    def _new_page(self) -> fitz.Page:
        page = self.doc.new_page(width=self.page_w, height=self.page_h)
        page.insert_font(fontname="arial", fontfile=str(FONTS_DIR / FONT_FILES["arial"]))
        return page

    def render(self, data: dict) -> fitz.Document:
        parts = list(data["paragraphs"])
        if data["closing"]:
            parts.append("\n".join(data["closing"]))
        letter_text = "\n\n".join(parts)

        rect = fitz.Rect(self.left, self.TOP_MARGIN, self.right, self.page_h - self.BOTTOM_MARGIN)
        overflow = self.page.insert_textbox(
            rect,
            normalise_pdf_text(letter_text),
            fontname="arial",
            fontsize=self.FONT_SIZE,
            align=0,
            lineheight=self.LINE_HEIGHT,
            color=self.TEXT_COLOR,
        )
        if overflow < 0:
            raise RuntimeError("Cover letter content overflowed the page. Shorten the letter or reduce font size.")
        return self.doc


def document_kind(filename: str) -> str:
    lowered = filename.lower()
    if "coverletter" in lowered or "cover-letter" in lowered:
        return "cover"
    return "resume"


def render_markdown_to_pdf(md_path: Path, output_pdf: Path) -> None:
    font_errors = validate_font_files(FONTS_DIR)
    if font_errors:
        raise RuntimeError(
            "PDF font validation failed before render:\n"
            + "\n".join(f"  - {error}" for error in font_errors)
            + "\nRun scripts/ensure_fonts.sh to repair fonts."
        )

    text = md_path.read_text(encoding="utf-8")
    kind = document_kind(md_path.name)

    if kind == "cover":
        doc = CoverLetterRenderer().render(parse_cover_letter(text))
    else:
        doc = MasterResumeRenderer().render(parse_resume(text))

    output_pdf.parent.mkdir(parents=True, exist_ok=True)
    # Deflate + garbage collect keeps uploads under typical 2MB caps without changing text/fonts.
    doc.save(str(output_pdf), garbage=4, deflate=True, clean=True)
    doc.close()

    integrity_errors = validate_pdf_text_integrity(output_pdf)
    if integrity_errors:
        output_pdf.unlink(missing_ok=True)
        raise RuntimeError(
            f"PDF text integrity check failed for {output_pdf}:\n"
            + "\n".join(f"  - {error}" for error in integrity_errors)
        )


def main(argv: list[str]) -> int:
    if len(argv) < 3:
        print("Usage: render_resume_pdf.py <markdown-file> <output-pdf>", file=sys.stderr)
        return 2

    md_path = Path(argv[1]).expanduser()
    output_pdf = Path(argv[2]).expanduser()

    if not md_path.exists():
        print(f"Error: markdown file not found: {md_path}", file=sys.stderr)
        return 1

    render_markdown_to_pdf(md_path, output_pdf)
    print(f"Wrote: {output_pdf}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
