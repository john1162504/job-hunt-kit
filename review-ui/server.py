#!/usr/bin/env python3
"""Local review UI for daily job-application runs."""

from __future__ import annotations

import json
import mimetypes
import re
import sys
from datetime import date
from http import HTTPStatus
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import unquote, urlparse

REPO_ROOT = Path(__file__).resolve().parents[1]
REVIEW_UI_ROOT = Path(__file__).resolve().parent
STATIC_ROOT = REVIEW_UI_ROOT / "static"
DAILY_RUNS_DIR = REPO_ROOT / "daily-runs"
APPLICATIONS_DIR = REPO_ROOT / "applications"
TRACKED_JOBS_PATH = REPO_ROOT / "tracked-jobs.json"
REVIEW_STATE_PATH = REVIEW_UI_ROOT / "review-state.json"

sys.path.insert(0, str(REVIEW_UI_ROOT))
from lib.parsers import (  # noqa: E402
    PreparedRole,
    discover_application_files,
    parse_daily_run,
    parse_notes,
)


def load_review_state() -> dict:
    if REVIEW_STATE_PATH.exists():
        return json.loads(REVIEW_STATE_PATH.read_text(encoding="utf-8"))
    return {"applications": {}}


def save_review_state(state: dict) -> None:
    REVIEW_STATE_PATH.parent.mkdir(parents=True, exist_ok=True)
    REVIEW_STATE_PATH.write_text(json.dumps(state, indent=2) + "\n", encoding="utf-8")


def load_tracked_jobs() -> list[dict]:
    if not TRACKED_JOBS_PATH.exists():
        return []
    data = json.loads(TRACKED_JOBS_PATH.read_text(encoding="utf-8"))
    return data.get("jobs", [])


def date_from_run_filename(stem: str) -> str | None:
    match = re.match(r"^(\d{4}-\d{2}-\d{2})", stem)
    return match.group(1) if match else None


def find_run_paths_for_date(run_date: str) -> list[Path]:
    """Prefer the success report, then NEEDS-APPROVAL, then attempt logs."""
    if not DAILY_RUNS_DIR.is_dir():
        return []

    preferred = DAILY_RUNS_DIR / f"{run_date}.md"
    needs = DAILY_RUNS_DIR / f"{run_date}-NEEDS-APPROVAL.md"
    attempts = sorted(
        DAILY_RUNS_DIR.glob(f"{run_date}-attempt-*.md"),
        key=lambda p: p.name,
        reverse=True,
    )

    paths: list[Path] = []
    if preferred.exists():
        paths.append(preferred)
    if needs.exists():
        paths.append(needs)
    paths.extend(attempts)
    return paths


def list_daily_run_dates() -> list[dict]:
    """Unique calendar dates that have a report and/or tracked applications."""
    by_date: dict[str, dict] = {}

    if DAILY_RUNS_DIR.is_dir():
        for path in DAILY_RUNS_DIR.glob("*.md"):
            run_date = date_from_run_filename(path.stem)
            if not run_date:
                continue
            entry = by_date.setdefault(
                run_date,
                {
                    "date": run_date,
                    "hasSuccessReport": False,
                    "hasAttempt": False,
                    "hasNeedsApproval": False,
                    "label": run_date,
                },
            )
            stem = path.stem
            if stem == run_date:
                entry["hasSuccessReport"] = True
            elif "NEEDS-APPROVAL" in stem:
                entry["hasNeedsApproval"] = True
            elif "attempt" in stem:
                entry["hasAttempt"] = True

    for job in load_tracked_jobs():
        run_date = (job.get("dateFound") or "").strip()
        if not re.fullmatch(r"\d{4}-\d{2}-\d{2}", run_date):
            continue
        by_date.setdefault(
            run_date,
            {
                "date": run_date,
                "hasSuccessReport": False,
                "hasAttempt": False,
                "hasNeedsApproval": False,
                "label": run_date,
            },
        )

    dates = sorted(by_date.values(), key=lambda item: item["date"], reverse=True)
    for entry in dates:
        tags = []
        if entry["hasSuccessReport"]:
            tags.append("success report")
        elif entry["hasNeedsApproval"]:
            tags.append("needs approval")
        elif entry["hasAttempt"]:
            tags.append("attempt only")
        else:
            tags.append("tracked apps")
        entry["label"] = f"{entry['date']} ({', '.join(tags)})"
    return dates


def role_to_dict(role: PreparedRole, review_state: dict, date_found: str = "") -> dict:
    slug = role.slug
    return {
        "company": role.company,
        "roleTitle": role.role_title,
        "url": role.url,
        "location": role.location,
        "whyMatched": role.why_matched,
        "folder": role.folder,
        "slug": slug,
        "dateFound": date_found,
        "resumePdf": role.resume_pdf,
        "coverLetterPdf": role.cover_letter_pdf,
        "kind": role.kind or "prepared",
        "skipReason": role.skip_reason,
        "review": review_state.get(slug, {}) if slug else {},
    }


def match_slug_for_company_role(company: str, role_title: str) -> str:
    """Best-effort match when attempt reports list company/role without folder."""
    company_l = company.lower().strip()
    title_l = role_title.lower().strip()
    for job in load_tracked_jobs():
        if (job.get("company") or "").lower().strip() == company_l:
            job_title = (job.get("roleTitle") or "").lower().strip()
            if title_l in job_title or job_title in title_l or not title_l:
                return job.get("slug") or ""
    if APPLICATIONS_DIR.is_dir():
        company_slug = re.sub(r"[^a-z0-9]+", "-", company_l).strip("-")
        for app_dir in APPLICATIONS_DIR.iterdir():
            if not app_dir.is_dir():
                continue
            name = app_dir.name.lower()
            if name.startswith(company_slug) or company_slug in name:
                return app_dir.name
    return ""


def enrich_role_from_disk(role: dict) -> dict:
    if role.get("kind") == "bad_url":
        return role

    slug = role.get("slug") or ""
    if not slug and role.get("company"):
        slug = match_slug_for_company_role(role.get("company", ""), role.get("roleTitle", ""))
        if slug:
            role["slug"] = slug

    if not slug:
        return role
    app_dir = APPLICATIONS_DIR / slug
    files = discover_application_files(app_dir, REPO_ROOT)
    if files.get("resume_pdf") and not role.get("resumePdf"):
        role["resumePdf"] = files["resume_pdf"]
    if files.get("cover_pdf") and not role.get("coverLetterPdf"):
        role["coverLetterPdf"] = files["cover_pdf"]
    if not role.get("folder"):
        role["folder"] = f"applications/{slug}"
    if not role.get("url") and (app_dir / "notes.md").exists():
        notes = parse_notes(app_dir / "notes.md")
        listing = notes.get("listing")
        if isinstance(listing, list):
            for item in listing:
                if "http" in item:
                    url_match = re.search(r"https?://[^\s]+", item)
                    if url_match:
                        role["url"] = url_match.group(0)
                        break
    if not role.get("whyMatched") and (app_dir / "notes.md").exists():
        notes = parse_notes(app_dir / "notes.md")
        why = notes.get("why it matched")
        if isinstance(why, list):
            role["whyMatched"] = "; ".join(why)
        elif isinstance(why, str):
            role["whyMatched"] = why
    return role



def tracked_job_to_role(job: dict, review_state: dict) -> dict:
    slug = job.get("slug") or ""
    role = {
        "company": job.get("company") or slug,
        "roleTitle": job.get("roleTitle") or "",
        "url": job.get("url") or "",
        "location": "",
        "whyMatched": "",
        "folder": f"applications/{slug}" if slug else "",
        "slug": slug,
        "dateFound": job.get("dateFound") or "",
        "resumePdf": "",
        "coverLetterPdf": "",
        "kind": "prepared",
        "skipReason": "",
        "review": review_state.get(slug, {}),
        "trackedStatus": job.get("status") or "",
        "source": job.get("source") or "",
    }
    return enrich_role_from_disk(role)


def merge_roles(*role_lists: list[dict]) -> list[dict]:
    merged: dict[str, dict] = {}
    order: list[str] = []
    for roles in role_lists:
        for role in roles:
            slug = role.get("slug") or ""
            if not slug:
                # Keep prepared roles without slug by synthesizing a temporary key.
                slug = f"tmp-{role.get('company','')}-{role.get('roleTitle','')}".lower()
                role = {**role, "slug": role.get("slug") or ""}
                key = slug
            else:
                key = slug
            if key not in merged:
                merged[key] = role
                order.append(key)
            else:
                existing = merged[key]
                for field, value in role.items():
                    if field == "review":
                        if value:
                            existing["review"] = value
                        continue
                    if field == "kind" and existing.get("kind") == "prepared":
                        continue
                    if value and not existing.get(field):
                        existing[field] = value
    result = []
    for key in order:
        role = enrich_role_from_disk(merged[key])
        if not role.get("slug"):
            # Drop unresolved stubs that never got a real slug and aren't failed URLs.
            if role.get("kind") != "bad_url":
                continue
        result.append(role)
    return result


def daily_run_to_dict(run_date: str) -> dict:
    paths = find_run_paths_for_date(run_date)
    review_state = load_review_state()["applications"]
    report_roles: list[dict] = []
    failed_roles: list[dict] = []
    payload = {
        "date": run_date,
        "status": "",
        "timezone": "",
        "attempt": "",
        "headline": "",
        "counts": {},
        "roles": [],
        "skippedDuplicates": [],
        "skippedBadUrl": [],
        "skippedIrrelevant": [],
        "errorsNotes": [],
        "gitCommit": "",
        "pushedToMain": "",
        "rawPath": "",
        "sourceKind": "tracked-only",
    }

    for index, path in enumerate(paths):
        run = parse_daily_run(path)
        if index == 0:
            payload.update(
                {
                    "status": run.status,
                    "timezone": run.timezone,
                    "attempt": run.attempt,
                    "headline": run.headline,
                    "counts": run.counts,
                    "gitCommit": run.git_commit,
                    "pushedToMain": run.pushed_to_main,
                    "rawPath": run.raw_path,
                    "sourceKind": "report",
                }
            )
        elif not payload["headline"] and run.headline:
            payload["headline"] = run.headline

        for item in run.skipped_duplicates:
            if item not in payload["skippedDuplicates"]:
                payload["skippedDuplicates"].append(item)
        for item in run.skipped_bad_url:
            if item not in payload["skippedBadUrl"]:
                payload["skippedBadUrl"].append(item)
        for item in run.skipped_irrelevant:
            if item not in payload["skippedIrrelevant"]:
                payload["skippedIrrelevant"].append(item)
        for item in run.errors_notes:
            if item not in payload["errorsNotes"]:
                payload["errorsNotes"].append(item)

        report_roles.extend(
            role_to_dict(role, review_state, date_found=run_date) for role in run.roles
        )
        failed_roles.extend(
            role_to_dict(role, review_state, date_found=run_date)
            for role in run.failed_url_roles
        )

    tracked_roles = [
        tracked_job_to_role(job, review_state)
        for job in load_tracked_jobs()
        if (job.get("dateFound") or "").strip() == run_date
    ]

    prepared = merge_roles(report_roles, tracked_roles)
    # Failed URL roles stay after prepared apps so they remain visible for manual visit.
    failed = merge_roles(failed_roles)
    payload["roles"] = prepared + [role for role in failed if role.get("kind") == "bad_url"]

    if not payload["headline"]:
        if payload["roles"]:
            prepared_count = sum(1 for role in payload["roles"] if role.get("kind") != "bad_url")
            failed_count = sum(1 for role in payload["roles"] if role.get("kind") == "bad_url")
            payload["headline"] = (
                f"{prepared_count} prepared and {failed_count} failed-verify listing(s) "
                f"for {run_date}."
            )
        else:
            payload["headline"] = f"No prepared applications found for {run_date}."
            payload["status"] = payload["status"] or "empty"

    if not payload["status"] and payload["roles"]:
        payload["status"] = "available"

    return payload


def list_all_applications() -> list[dict]:
    review_state = load_review_state()["applications"]
    tracked = {job.get("slug"): job for job in load_tracked_jobs() if job.get("slug")}
    roles: list[dict] = []

    if APPLICATIONS_DIR.is_dir():
        for app_dir in sorted(APPLICATIONS_DIR.iterdir(), key=lambda p: p.name.lower()):
            if not app_dir.is_dir():
                continue
            slug = app_dir.name
            job = tracked.get(slug, {})
            role = tracked_job_to_role(
                {
                    "company": job.get("company") or slug.replace("-", " ").title(),
                    "roleTitle": job.get("roleTitle") or "",
                    "url": job.get("url") or "",
                    "source": job.get("source") or "",
                    "slug": slug,
                    "dateFound": job.get("dateFound") or "",
                    "status": job.get("status") or "",
                },
                review_state,
            )
            roles.append(role)

    # Include tracked jobs whose folders are missing (still reviewable as stubs).
    existing = {role["slug"] for role in roles}
    for slug, job in tracked.items():
        if slug not in existing:
            roles.append(tracked_job_to_role(job, review_state))

    roles.sort(key=lambda role: (role.get("dateFound") or "", role.get("company") or ""), reverse=True)
    return roles


def application_to_dict(slug: str) -> dict:
    app_dir = APPLICATIONS_DIR / slug
    if not app_dir.is_dir():
        raise FileNotFoundError(slug)

    files = discover_application_files(app_dir, REPO_ROOT)
    notes_path = app_dir / "notes.md"
    notes = parse_notes(notes_path) if notes_path.exists() else {}

    resume_md = ""
    cover_md = ""
    if "resume_md" in files:
        resume_md = (REPO_ROOT / files["resume_md"]).read_text(encoding="utf-8")
    if "cover_md" in files:
        cover_md = (REPO_ROOT / files["cover_md"]).read_text(encoding="utf-8")

    return {
        "slug": slug,
        "folder": f"applications/{slug}",
        "notes": notes,
        "resumeMarkdown": resume_md,
        "coverMarkdown": cover_md,
        "files": {
            "resumeMd": files.get("resume_md", ""),
            "coverMd": files.get("cover_md", ""),
            "resumePdf": files.get("resume_pdf", ""),
            "coverPdf": files.get("cover_pdf", ""),
            "notes": files.get("notes", ""),
        },
        "review": load_review_state()["applications"].get(slug, {}),
    }


def upsert_review(slug: str, status: str | None = None, note: str | None = None) -> dict:
    state = load_review_state()
    entry = state["applications"].get(slug, {})
    if status is not None:
        entry["status"] = status
    if note is not None:
        entry["note"] = note
    entry["updatedAt"] = date.today().isoformat()
    state["applications"][slug] = entry
    save_review_state(state)
    return entry


def json_response(handler: BaseHTTPRequestHandler, payload: object, status: int = 200) -> None:
    body = json.dumps(payload, ensure_ascii=False).encode("utf-8")
    handler.send_response(status)
    handler.send_header("Content-Type", "application/json; charset=utf-8")
    handler.send_header("Content-Length", str(len(body)))
    handler.send_header("Cache-Control", "no-store")
    handler.end_headers()
    handler.wfile.write(body)


def text_response(handler: BaseHTTPRequestHandler, body: bytes, content_type: str, status: int = 200) -> None:
    handler.send_response(status)
    handler.send_header("Content-Type", content_type)
    handler.send_header("Content-Length", str(len(body)))
    handler.send_header("Cache-Control", "no-store")
    handler.end_headers()
    handler.wfile.write(body)


class ReviewHandler(BaseHTTPRequestHandler):
    server_version = "JobApplicationReview/1.1"

    def log_message(self, format: str, *args) -> None:  # noqa: A003
        sys.stderr.write("%s - %s\n" % (self.address_string(), format % args))

    def do_GET(self) -> None:  # noqa: N802
        parsed = urlparse(self.path)
        path = parsed.path

        if path == "/api/health":
            json_response(
                self,
                {
                    "ok": True,
                    "repoRoot": str(REPO_ROOT),
                    "today": date.today().isoformat(),
                },
            )
            return

        if path == "/api/daily-runs":
            dates = list_daily_run_dates()
            json_response(
                self,
                {
                    "dates": dates,
                    "defaultDate": dates[0]["date"] if dates else None,
                },
            )
            return

        daily_match = re.fullmatch(r"/api/daily-runs/(\d{4}-\d{2}-\d{2})", path)
        if daily_match:
            json_response(self, daily_run_to_dict(daily_match.group(1)))
            return

        if path == "/api/applications":
            roles = list_all_applications()
            json_response(self, {"roles": roles, "count": len(roles)})
            return

        app_match = re.fullmatch(r"/api/applications/([^/]+)", path)
        if app_match:
            slug = unquote(app_match.group(1))
            try:
                json_response(self, application_to_dict(slug))
            except FileNotFoundError:
                json_response(self, {"error": "Application not found"}, HTTPStatus.NOT_FOUND)
            return

        if path.startswith("/files/"):
            rel = unquote(path[len("/files/") :])
            target = (REPO_ROOT / rel).resolve()
            if not str(target).startswith(str(REPO_ROOT.resolve())):
                json_response(self, {"error": "Forbidden"}, HTTPStatus.FORBIDDEN)
                return
            if not target.is_file():
                json_response(self, {"error": "File not found"}, HTTPStatus.NOT_FOUND)
                return
            content_type, _ = mimetypes.guess_type(str(target))
            if content_type is None:
                content_type = "application/octet-stream"
            body = target.read_bytes()
            text_response(self, body, content_type)
            return

        if path in ("/", "/index.html"):
            index_path = STATIC_ROOT / "index.html"
            text_response(self, index_path.read_bytes(), "text/html; charset=utf-8")
            return

        static_path = (STATIC_ROOT / path.lstrip("/")).resolve()
        if str(static_path).startswith(str(STATIC_ROOT.resolve())) and static_path.is_file():
            content_type, _ = mimetypes.guess_type(str(static_path))
            if content_type is None:
                content_type = "application/octet-stream"
            text_response(self, static_path.read_bytes(), content_type)
            return

        json_response(self, {"error": "Not found"}, HTTPStatus.NOT_FOUND)

    def do_POST(self) -> None:  # noqa: N802
        parsed = urlparse(self.path)
        length = int(self.headers.get("Content-Length", "0"))
        raw = self.rfile.read(length) if length else b"{}"
        try:
            payload = json.loads(raw.decode("utf-8"))
        except json.JSONDecodeError:
            json_response(self, {"error": "Invalid JSON"}, HTTPStatus.BAD_REQUEST)
            return

        if parsed.path == "/api/review-state":
            slug = (payload.get("slug") or "").strip()
            if not slug:
                json_response(self, {"error": "slug is required"}, HTTPStatus.BAD_REQUEST)
                return
            entry = upsert_review(
                slug,
                status=payload.get("status"),
                note=payload.get("note"),
            )
            json_response(self, {"slug": slug, "review": entry})
            return

        if parsed.path == "/api/review-state/bulk":
            slugs = payload.get("slugs") or []
            if not isinstance(slugs, list) or not slugs:
                json_response(self, {"error": "slugs array is required"}, HTTPStatus.BAD_REQUEST)
                return
            status = payload.get("status")
            note = payload.get("note")
            if status is None and note is None:
                json_response(self, {"error": "status or note is required"}, HTTPStatus.BAD_REQUEST)
                return
            updates = []
            for slug in slugs:
                clean = str(slug).strip()
                if not clean:
                    continue
                entry = upsert_review(clean, status=status, note=note)
                updates.append({"slug": clean, "review": entry})
            json_response(self, {"updated": updates, "count": len(updates)})
            return

        json_response(self, {"error": "Not found"}, HTTPStatus.NOT_FOUND)


def main() -> None:
    port = 8765
    if len(sys.argv) > 1:
        port = int(sys.argv[1])

    server = ThreadingHTTPServer(("127.0.0.1", port), ReviewHandler)
    print(f"Job application review UI: http://127.0.0.1:{port}")
    print(f"Repo root: {REPO_ROOT}")
    print("Press Ctrl+C to stop.")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\nStopped.")
        server.server_close()


if __name__ == "__main__":
    main()
