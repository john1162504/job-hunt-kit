"""Load applicant config for job-hunt-kit scripts and prompt rendering."""

from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parent.parent
CONFIG_PATH = ROOT / "config.json"
EXAMPLE_PATH = ROOT / "config.example.json"


class ConfigError(RuntimeError):
    pass


def load_config(path: Path | None = None) -> dict[str, Any]:
    cfg_path = path or CONFIG_PATH
    if not cfg_path.is_file():
        raise ConfigError(
            f"Missing {cfg_path.name}. Copy config.example.json to config.json "
            "and fill in your details, then run: python3 scripts/bootstrap.py"
        )
    data = json.loads(cfg_path.read_text(encoding="utf-8"))
    validate_config(data)
    return data


def validate_config(data: dict[str, Any]) -> None:
    try:
        applicant = data["applicant"]
        name = applicant["full_name"].strip()
        prefix = applicant["file_prefix"].strip()
        email = applicant["email"].strip()
    except (KeyError, AttributeError, TypeError) as exc:
        raise ConfigError(f"config.json is missing required applicant fields: {exc}") from exc

    if not name or name.lower().startswith("your ") or name == "Alex Example":
        # Allow Alex Example only in example file; warn for real config later in bootstrap.
        pass
    if not prefix or not re.fullmatch(r"[A-Za-z][A-Za-z0-9_-]*", prefix):
        raise ConfigError(
            "applicant.file_prefix must be letters/digits/_/- and start with a letter "
            f"(got {prefix!r}). Example: JaneDoe"
        )
    if not email or "@" not in email:
        raise ConfigError("applicant.email must be a real email address")


def contact_line(cfg: dict[str, Any] | None = None) -> str:
    cfg = cfg or load_config()
    a = cfg["applicant"]
    parts = [a.get("phone", "").strip(), a.get("email", "").strip()]
    parts.extend(link.strip() for link in a.get("links", []) if link and link.strip())
    return " | ".join(p for p in parts if p)


def file_prefix(cfg: dict[str, Any] | None = None) -> str:
    cfg = cfg or load_config()
    return cfg["applicant"]["file_prefix"]


def full_name(cfg: dict[str, Any] | None = None) -> str:
    cfg = cfg or load_config()
    return cfg["applicant"]["full_name"]


def launch_agent_label(cfg: dict[str, Any] | None = None) -> str:
    cfg = cfg or load_config()
    label = cfg.get("launch_agent", {}).get("label")
    if label:
        return label
    prefix = file_prefix(cfg).lower().replace("_", "")
    return f"com.{prefix}.job-hunt.sync-cloud-results"


def resume_glob(cfg: dict[str, Any] | None = None) -> str:
    return f"{file_prefix(cfg)}-*.md"


def pdf_glob(cfg: dict[str, Any] | None = None) -> str:
    return f"{file_prefix(cfg)}-*.pdf"


def substitute(template: str, cfg: dict[str, Any] | None = None) -> str:
    """Replace {{dotted.keys}} and a few convenience tokens in a template string."""
    cfg = cfg or load_config()
    a = cfg["applicant"]
    s = cfg["search"]
    sched = cfg["schedule"]

    tokens = {
        "full_name": a["full_name"],
        "file_prefix": a["file_prefix"],
        "phone": a.get("phone", ""),
        "email": a.get("email", ""),
        "contact_line": contact_line(cfg),
        "location_city": a.get("location_city", ""),
        "location_country": a.get("location_country", ""),
        "spelling": a.get("spelling", "en-NZ"),
        "work_auth_note": a.get("work_auth_note", ""),
        "market_label": s.get("market_label", "software roles"),
        "freshness_hours": str(s.get("freshness_hours", 48)),
        "max_prepared_per_run": str(s.get("max_prepared_per_run", 5)),
        "primary_titles": ", ".join(s.get("primary", {}).get("titles", [])),
        "primary_locations": ", ".join(s.get("primary", {}).get("locations", [])),
        "adjacent_enabled": "yes" if s.get("adjacent", {}).get("enabled") else "no",
        "adjacent_titles": ", ".join(s.get("adjacent", {}).get("titles", [])),
        "adjacent_locations": ", ".join(s.get("adjacent", {}).get("locations_required", [])),
        "adjacent_notes": s.get("adjacent", {}).get("notes", ""),
        "preferred_sources": ", ".join(s.get("preferred_sources", [])),
        "display_timezone": sched.get("display_timezone", ""),
        "cron_utc_slots": " / ".join(sched.get("cron_utc_slots", [])),
        "local_display_slots": " / ".join(sched.get("local_display_slots", [])),
        "local_sync_window": sched.get("local_sync_window", ""),
        "launch_agent_label": launch_agent_label(cfg),
        "repo_path_placeholder": "{{REPO_PATH}}",
    }

    # Explicit {{token}} replacement
    out = template
    for key, value in tokens.items():
        out = out.replace("{{" + key + "}}", str(value))

    # Attempt numbering from cron slots
    slots = sched.get("cron_utc_slots", [])
    local = sched.get("local_display_slots", [])
    attempt_lines = []
    for i, utc in enumerate(slots, start=1):
        loc = local[i - 1] if i - 1 < len(local) else ""
        attempt_lines.append(f"- {utc} UTC → attempt {i}" + (f" ({loc})" if loc else ""))
    out = out.replace("{{attempt_slot_list}}", "\n".join(attempt_lines))

    return out
