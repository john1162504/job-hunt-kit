"""Parse daily run reports and application notes from the job-hunt-kit repo."""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from pathlib import Path


@dataclass
class PreparedRole:
    company: str
    role_title: str
    url: str = ""
    location: str = ""
    why_matched: str = ""
    folder: str = ""
    slug: str = ""
    resume_pdf: str = ""
    cover_letter_pdf: str = ""
    kind: str = "prepared"  # prepared | bad_url
    skip_reason: str = ""


@dataclass
class DailyRun:
    date: str
    status: str = ""
    timezone: str = ""
    attempt: str = ""
    headline: str = ""
    counts: dict[str, int] = field(default_factory=dict)
    roles: list[PreparedRole] = field(default_factory=list)
    failed_url_roles: list[PreparedRole] = field(default_factory=list)
    skipped_duplicates: list[str] = field(default_factory=list)
    skipped_bad_url: list[str] = field(default_factory=list)
    skipped_irrelevant: list[str] = field(default_factory=list)
    errors_notes: list[str] = field(default_factory=list)
    git_commit: str = ""
    pushed_to_main: str = ""
    raw_path: str = ""


ROLE_HEADER = re.compile(r"^###\s+(.+?)\s+[—–-]\s+(.+?)\s*$")
ROLE_HEADER_ALT = re.compile(r"^###\s+(.+?)\s+[—–-]\s+(.+?)\s*\(.+?\)\s*$")
BULLET = re.compile(r"^-\s+(.+?):\s*(.*)$")
URL_RE = re.compile(r"https?://[^\s)>\]]+")
# Field separators in daily reports use em dashes; keep en-dashes inside titles intact.
EM_DASH_SPLIT = re.compile(r"\s+—\s+")


def _slug_from_folder(folder: str) -> str:
    folder = folder.rstrip("/")
    if folder.startswith("applications/"):
        return folder[len("applications/") :]
    return Path(folder).name


def _slugify(text: str) -> str:
    slug = re.sub(r"[^a-z0-9]+", "-", text.lower()).strip("-")
    return slug[:80] or "role"


def _failed_slug(company: str, role_title: str, url: str, run_date: str) -> str:
    base = _slugify(f"{company}-{role_title}")
    if not base or base == "role":
        base = _slugify(url) or "listing"
    return f"failed-{run_date}-{base}"


def _extract_url(text: str) -> str:
    match = URL_RE.search(text)
    return match.group(0).rstrip(".,;") if match else ""


def _parse_role_block(lines: list[str]) -> PreparedRole | None:
    if not lines:
        return None

    header = lines[0].strip()
    match = ROLE_HEADER.match(header) or ROLE_HEADER_ALT.match(header)
    if not match:
        return None

    role = PreparedRole(company=match.group(1).strip(), role_title=match.group(2).strip())

    for line in lines[1:]:
        stripped = line.strip()
        if not stripped.startswith("-"):
            continue
        bullet = BULLET.match(stripped)
        if not bullet:
            # Nested PDF path without a key
            value = stripped.lstrip("- ").strip()
            if value.endswith(".pdf") and value.startswith("applications/"):
                lower = value.lower()
                role.folder = str(Path(value).parent)
                role.slug = _slug_from_folder(role.folder)
                if "resume" in lower and "cover" not in lower:
                    role.resume_pdf = value
                elif "cover" in lower:
                    role.cover_letter_pdf = value
            continue
        key = bullet.group(1).strip().lower()
        value = bullet.group(2).strip()
        if key in ("url", "listing url", "verified url"):
            role.url = value
        elif key == "location":
            role.location = value
        elif key in ("why matched", "match", "why it matched"):
            role.why_matched = value
        elif key in ("folder", "application folder"):
            role.folder = value.rstrip("/")
            role.slug = _slug_from_folder(role.folder)
        elif stripped.lower().startswith("- pdfs:"):
            continue
        elif value.endswith(".pdf"):
            lower = value.lower()
            if value.startswith("applications/"):
                role.folder = str(Path(value).parent)
                role.slug = _slug_from_folder(role.folder)
            if "resume" in lower and "cover" not in lower:
                role.resume_pdf = value
            elif "cover" in lower:
                role.cover_letter_pdf = value

    if role.folder and not role.slug:
        role.slug = _slug_from_folder(role.folder)
    return role


def _parse_role_sections(text: str, heading_pattern: str) -> list[PreparedRole]:
    section = re.search(heading_pattern + r"\s*\n+(.+?)(?=\n## |\Z)", text, re.DOTALL | re.IGNORECASE)
    if not section:
        return []
    roles: list[PreparedRole] = []
    blocks = re.split(r"\n(?=### )", section.group(1).strip())
    for block in blocks:
        role = _parse_role_block(block.splitlines())
        if role:
            roles.append(role)
    return roles


def _parse_undelivered_roles(section: str) -> list[PreparedRole]:
    """Parse compact prepared-but-not-delivered attempt-report blocks."""
    roles: list[PreparedRole] = []
    current: PreparedRole | None = None

    for raw in section.splitlines():
        line = raw.strip()
        if not line.startswith("-"):
            continue
        content = line[1:].strip()
        company_role = re.match(r"^(.+?)\s+[—–-]\s+(.+)$", content)
        if company_role and "applications/" not in content and not content.startswith("http"):
            if current:
                roles.append(current)
            current = PreparedRole(
                company=company_role.group(1).strip(),
                role_title=company_role.group(2).strip(),
            )
            continue
        if current and content.startswith("applications/") and content.endswith(".pdf"):
            lower = content.lower()
            current.folder = str(Path(content).parent)
            current.slug = _slug_from_folder(current.folder)
            if "resume" in lower and "cover" not in lower:
                current.resume_pdf = content
            elif "cover" in lower:
                current.cover_letter_pdf = content

    if current:
        roles.append(current)
    return roles


def _parse_company_role_bullets(section: str) -> list[PreparedRole]:
    roles: list[PreparedRole] = []
    for raw in section.splitlines():
        line = raw.strip()
        if not line.startswith("-"):
            continue
        content = line[1:].strip()
        if content.startswith("http") or "applications/" in content:
            continue
        company_role = re.match(r"^(.+?)\s+[—–-]\s+(.+)$", content)
        if not company_role:
            continue
        roles.append(
            PreparedRole(
                company=company_role.group(1).strip(),
                role_title=company_role.group(2).strip(),
            )
        )
    return roles


def _parse_failed_url_line(line: str, run_date: str) -> PreparedRole | None:
    content = line.strip()
    if content.startswith("-"):
        content = content[1:].strip()
    if not content:
        return None

    url = _extract_url(content)
    remainder = content
    if url:
        remainder = content.replace(url, " ").strip()
        remainder = re.sub(r"\s+[—–]\s*$", "", remainder)
        remainder = re.sub(r"^\s*[—–]\s*", "", remainder)
        remainder = re.sub(r"\s+[—–]\s+[—–]\s+", " — ", remainder)

    parts = [part.strip(" `") for part in EM_DASH_SPLIT.split(remainder) if part.strip(" `")]
    company = parts[0] if parts else "Unknown company"
    role_title = parts[1] if len(parts) > 1 else "Listing"
    reason_parts = parts[2:] if len(parts) > 2 else []
    reason = " — ".join(reason_parts).strip(" —")
    reason = re.sub(r"^`?skipped-bad-url`?:\s*", "", reason, flags=re.IGNORECASE).strip()
    if not reason and "skipped-bad-url" in content.lower():
        reason = "Verifier flagged listing as bad/unusable URL"
    if not reason:
        reason = "Skipped as bad/unusable URL (manual visit may still work)"
    if reason and re.search(r"HTTP 403|bot[_ ]?block|cloudflare|challenge", reason, re.I):
        reason = f"{reason} — if the SEEK URL opens in a browser, it may still be usable"

    return PreparedRole(
        company=company,
        role_title=role_title,
        url=url,
        kind="bad_url",
        skip_reason=reason,
        why_matched=reason,
        slug=_failed_slug(company, role_title, url, run_date),
    )


def _section_lines(text: str, heading_pattern: str) -> list[str]:
    section = re.search(heading_pattern + r"\s*\n+(.+?)(?=\n## |\Z)", text, re.DOTALL | re.IGNORECASE)
    if not section:
        return []
    return [
        line.strip().lstrip("- ").strip()
        for line in section.group(1).splitlines()
        if line.strip().startswith("-")
    ]


def _append_unique(target: list[str], items: list[str]) -> None:
    seen = set(target)
    for item in items:
        if item and item not in seen:
            target.append(item)
            seen.add(item)


def parse_daily_run(path: Path) -> DailyRun:
    text = path.read_text(encoding="utf-8")
    stem = path.stem
    date_match = re.match(r"^(\d{4}-\d{2}-\d{2})", stem)
    date = date_match.group(1) if date_match else stem
    run = DailyRun(date=date, raw_path=str(path))

    status_match = re.search(r"^status:\s*(.+)$", text, re.MULTILINE | re.IGNORECASE)
    if status_match:
        run.status = status_match.group(1).strip()

    tz_match = re.search(r"^timezone:\s*(.+)$", text, re.MULTILINE | re.IGNORECASE)
    if tz_match:
        run.timezone = tz_match.group(1).strip()

    attempt_match = re.search(r"^attempt:\s*(.+)$", text, re.MULTILINE | re.IGNORECASE)
    if attempt_match:
        run.attempt = attempt_match.group(1).strip()
    else:
        legacy_attempt = re.search(r"^- Attempt:\s*(.+)$", text, re.MULTILINE)
        if legacy_attempt:
            run.attempt = legacy_attempt.group(1).strip()

    for pattern in (
        r"## Headline",
        r"## Reason",
        r"## Failure reason",
    ):
        headline_match = re.search(pattern + r"\s*\n+(.+?)(?=\n## |\Z)", text, re.DOTALL | re.IGNORECASE)
        if headline_match:
            run.headline = headline_match.group(1).strip()
            break

    counts_match = re.search(
        r"## (?:Counts|Search summary|Search outcome)\s*\n+(.+?)(?=\n## |\Z)",
        text,
        re.DOTALL | re.IGNORECASE,
    )
    if counts_match:
        for line in counts_match.group(1).splitlines():
            count_match = re.match(r"^-\s+(.+?):\s*(\d+)\s*$", line.strip())
            if count_match:
                run.counts[count_match.group(1).strip().lower()] = int(count_match.group(2))
    else:
        for line in text.splitlines():
            count_match = re.match(
                r"^-\s+(Found|Prepared|Skipped duplicates|Skipped irrelevant[^:]*|Errors[^:]*):\s*(\d+)",
                line.strip(),
                re.IGNORECASE,
            )
            if count_match:
                run.counts[count_match.group(1).strip().lower()] = int(count_match.group(2))

    for heading in (
        r"## Roles? prepared",
        r"## Applications prepared",
        r"## Materials generated but not delivered[^\n]*",
        r"## Prepared but not delivered[^\n]*",
    ):
        for role in _parse_role_sections(text, heading):
            run.roles.append(role)

    if not run.roles:
        undelivered = re.search(
            r"## Prepared but not delivered[^\n]*\n+(.+?)(?=\n## |\Z)",
            text,
            re.DOTALL | re.IGNORECASE,
        )
        if undelivered:
            run.roles.extend(_parse_undelivered_roles(undelivered.group(1)))

    if not run.roles:
        prepared_branch = re.search(
            r"## Prepared on feature branch\s*\n+(.+?)(?=\n## |\Z)",
            text,
            re.DOTALL | re.IGNORECASE,
        )
        if prepared_branch:
            run.roles.extend(_parse_company_role_bullets(prepared_branch.group(1)))

    for section_name, target in (
        (r"## Skipped \(duplicates\)", "skipped_duplicates"),
        (r"## Duplicate skipped", "skipped_duplicates"),
        (r"## Duplicates", "skipped_duplicates"),
        (r"## Skipped duplicate", "skipped_duplicates"),
        (r"## Skipped \(bad/unusable URL\)", "skipped_bad_url"),
        (r"## Bad or unusable listings", "skipped_bad_url"),
        (r"## Skipped bad/unusable URL", "skipped_bad_url"),
        (r"## Skipped \(irrelevant(?: or ineligible)?\)", "skipped_irrelevant"),
        (r"## Main exclusions", "skipped_irrelevant"),
        (r"## Skipped \(irrelevant or ineligible\)", "skipped_irrelevant"),
    ):
        _append_unique(getattr(run, target), _section_lines(text, section_name))

    # Combined "## Skipped" sections (attempt reports) mix duplicate/bad/irrelevant.
    combined = re.search(r"^## Skipped\s*\n+(.+?)(?=\n## |\Z)", text, re.DOTALL | re.IGNORECASE | re.MULTILINE)
    if combined:
        for raw in combined.group(1).splitlines():
            if not raw.strip().startswith("-"):
                continue
            content = raw.strip().lstrip("- ").strip()
            lower = content.lower()
            if "skipped-bad-url" in lower or _extract_url(content):
                if "skipped-duplicate" in lower:
                    _append_unique(run.skipped_duplicates, [content])
                elif "skipped-irrelevant" in lower:
                    _append_unique(run.skipped_irrelevant, [content])
                else:
                    _append_unique(run.skipped_bad_url, [content])
            elif "skipped-duplicate" in lower:
                _append_unique(run.skipped_duplicates, [content])
            elif "skipped-irrelevant" in lower:
                _append_unique(run.skipped_irrelevant, [content])

    for line in run.skipped_bad_url:
        failed = _parse_failed_url_line(line, date)
        if failed:
            run.failed_url_roles.append(failed)

    for pattern in (
        r"## Errors? / notes",
        r"## Notes",
        r"## Error / delivery",
        r"## Export note",
    ):
        section = re.search(pattern + r"\s*\n+(.+?)(?=\n## |\Z)", text, re.DOTALL | re.IGNORECASE)
        if not section:
            continue
        body = section.group(1).strip()
        bullets = [
            line.strip().lstrip("- ").strip()
            for line in body.splitlines()
            if line.strip().startswith("-")
        ]
        if bullets:
            _append_unique(run.errors_notes, bullets)
        elif body:
            _append_unique(run.errors_notes, [body])

    commit_match = re.search(r"^- Commit on main:\s*(.+)$", text, re.MULTILINE)
    if commit_match:
        run.git_commit = commit_match.group(1).strip()

    pushed_match = re.search(r"^- Pushed to main:\s*(.+)$", text, re.MULTILINE)
    if pushed_match:
        run.pushed_to_main = pushed_match.group(1).strip()

    return run


def parse_notes(path: Path) -> dict:
    if not path.exists():
        return {}

    text = path.read_text(encoding="utf-8")
    sections: dict[str, str | list[str]] = {}
    current_key: str | None = None
    current_lines: list[str] = []

    def flush() -> None:
        nonlocal current_key, current_lines
        if current_key is None:
            return
        body = "\n".join(current_lines).strip()
        if current_key in ("listing", "why it matched", "tailoring highlights", "honest gaps"):
            bullets = [
                line.strip().lstrip("- ").strip()
                for line in current_lines
                if line.strip().startswith("-")
            ]
            sections[current_key] = bullets if bullets else body
        else:
            sections[current_key] = body
        current_key = None
        current_lines = []

    for line in text.splitlines():
        if line.startswith("## "):
            flush()
            current_key = line[3:].strip().lower()
            current_lines = []
        elif current_key is not None:
            current_lines.append(line)

    flush()
    return sections


def discover_application_files(app_dir: Path, repo_root: Path | None = None) -> dict[str, str]:
    if not app_dir.is_dir():
        return {}

    files: dict[str, str] = {}
    for path in sorted(app_dir.iterdir()):
        if not path.is_file():
            continue
        name = path.name
        lower = name.lower()
        stored = str(path.relative_to(repo_root)) if repo_root else str(path)
        if name == "notes.md":
            files["notes"] = stored
        elif lower.endswith(".md") and "resume" in lower:
            files["resume_md"] = stored
        elif lower.endswith(".md") and "cover" in lower:
            files["cover_md"] = stored
        elif lower.endswith(".pdf") and "resume" in lower:
            files["resume_pdf"] = stored
        elif lower.endswith(".pdf") and "cover" in lower:
            files["cover_pdf"] = stored
    return files
