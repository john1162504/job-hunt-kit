#!/usr/bin/env python3
"""Verify a job listing URL is usable before the scanner prepares materials.

Exit codes:
  0 — URL looks like a live, individual job listing (not blacklisted / not a search page)
  1 — reject (blacklist, search/category page, removed, paywall signals, fetch failure)
  2 — usage / config error
  3 — bot-blocked (e.g. Cloudflare challenge); listing may still be fine in a browser
"""

from __future__ import annotations

import argparse
import json
import re
import ssl
import sys
import urllib.error
import urllib.request
from dataclasses import dataclass
from pathlib import Path
from typing import Any
from urllib.parse import urljoin, urlparse

ROOT = Path(__file__).resolve().parents[1]
BLACKLIST_PATH = ROOT / "source-blacklist.json"

# Category / search result URLs — never individual applications.
SEEK_SEARCH_RE = re.compile(
    r"seek\.co\.nz/.+-(jobs|jobs-in-)|"
    r"seek\.co\.nz/jobs-in-|"
    r"seek\.co\.nz/.+/in-All-|"
    r"seek\.co\.nz/jobs\?|"
    r"seek\.com/.+-(jobs|jobs-in-)|"
    r"seek\.com/jobs-in-|"
    r"seek\.com/.+/in-All-|"
    r"seek\.com/jobs\?",
    re.I,
)
SEEK_DETAIL_RE = re.compile(r"seek\.(co\.nz|com)/job/", re.I)

INDEED_SEARCH_RE = re.compile(r"indeed\.co\.nz/(jobs\?|q-)", re.I)
INDEED_DETAIL_RE = re.compile(r"indeed\.co\.nz/(viewjob|rc/clk|/jobs/view)", re.I)

LINKEDIN_SEARCH_RE = re.compile(r"linkedin\.com/jobs/(search|collections)", re.I)
LINKEDIN_DETAIL_RE = re.compile(r"linkedin\.com/jobs/view/", re.I)

TRADEME_SEARCH_RE = re.compile(r"trademe\.co\.nz/a/jobs/(search|browse)", re.I)
TRADEME_DETAIL_RE = re.compile(r"trademe\.co\.nz/.+/listing|/a/jobs/listing", re.I)

REMOVED_RE = re.compile(
    r"(job (was )?removed|no longer available|this (job|position) has (been )?(closed|expired|filled)|"
    r"listing (has )?(closed|expired)|position is closed|sorry,? this job)",
    re.I,
)
PAYWALL_RE = re.compile(
    r"(pay (to )?apply|unlock (to )?apply|subscribe (to )?apply|premium (membership|account) required|"
    r"buy (credits|tokens)|adapt my cv|upgrade to apply|sign up.*(to )?apply|"
    r"create (a )?free account|log in or sign up to (view|apply))",
    re.I,
)
BOT_CHALLENGE_RE = re.compile(
    r"just a moment\.\.\.|"
    r"challenges\.cloudflare\.com|"
    r"cdn-cgi/challenge-platform|"
    r"cf-browser-verification|"
    r"enable javascript and cookies to continue|"
    r"attention required!|"
    r"_cf_chl_opt|"
    r"cf-mitigated",
    re.I,
)

# Browser-like UA — custom scanner UAs make bot filters more aggressive.
USER_AGENT = (
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
    "AppleWebKit/537.36 (KHTML, like Gecko) "
    "Chrome/126.0.0.0 Safari/537.36"
)


@dataclass(frozen=True)
class VerifyResult:
    """ok | reject | bot_blocked"""

    status: str
    reasons: list[str]

    @property
    def ok(self) -> bool:
        return self.status == "ok"

    @property
    def bot_blocked(self) -> bool:
        return self.status == "bot_blocked"


def load_blacklist() -> dict[str, Any]:
    if not BLACKLIST_PATH.exists():
        return {"domains": [], "path_deny_substrings": []}
    return json.loads(BLACKLIST_PATH.read_text(encoding="utf-8"))


def host_blacklisted(host: str, domains: list[str]) -> bool:
    host = host.lower().removeprefix("www.")
    for d in domains:
        d_norm = d.lower().removeprefix("www.")
        if host == d_norm or host.endswith("." + d_norm):
            return True
    return False


def classify_board_url(url: str) -> str | None:
    """Return a rejection reason if the URL is clearly a search/category page."""
    if SEEK_SEARCH_RE.search(url) and not SEEK_DETAIL_RE.search(url):
        return "SEEK search/category page, not a job detail URL (need seek.co.nz/job/...)"
    if INDEED_SEARCH_RE.search(url) and not INDEED_DETAIL_RE.search(url):
        return "Indeed search results page, not a job detail URL"
    if LINKEDIN_SEARCH_RE.search(url) and not LINKEDIN_DETAIL_RE.search(url):
        return "LinkedIn jobs search/collection page, not a job view URL"
    if TRADEME_SEARCH_RE.search(url) and not TRADEME_DETAIL_RE.search(url):
        return "Trade Me jobs browse/search page, not a listing URL"
    return None


def _header_map(headers: Any) -> dict[str, str]:
    try:
        return {str(k).lower(): str(v) for k, v in headers.items()}
    except Exception:  # noqa: BLE001
        return {}


def is_bot_challenge(status: int, body: str, headers: dict[str, str] | None = None) -> bool:
    """True when the response is a bot/JS challenge interstitial, not the listing."""
    headers = headers or {}
    body = body or ""
    if headers.get("cf-mitigated", "").lower() == "challenge":
        return True
    if BOT_CHALLENGE_RE.search(body):
        # Challenge pages often arrive as 403/503; some boards return 200 interstitials.
        if status in {0, 200, 401, 403, 429, 503}:
            return True
    server = headers.get("server", "").lower()
    if "cloudflare" in server and status in {403, 429, 503}:
        return True
    # Cloudflare empty/short shells are not usable listing HTML (common before/without challenge body).
    if "cloudflare" in server and status in {200, 401, 403, 429, 503} and len(body.strip()) < 400:
        return True
    return False


class _HTTPRedirectHandler308(urllib.request.HTTPRedirectHandler):
    """Python 3.9's urllib does not follow HTTP 308; SEEK uses 308 to nz.seek.com."""

    def redirect_request(self, req, fp, code, msg, headers, newurl):  # noqa: ANN001,N802
        if code == 308:
            code = 307
        return super().redirect_request(req, fp, code, msg, headers, newurl)

    def http_error_308(self, req, fp, code, msg, headers):  # noqa: ANN001,N802
        return self.http_error_302(req, fp, code, msg, headers)


def fetch(url: str, timeout: float = 20.0) -> tuple[int, str, str, dict[str, str]]:
    """Return status, final URL, body text, and response headers (best-effort)."""
    ctx = ssl.create_default_context()
    try:
        import certifi  # type: ignore

        ctx = ssl.create_default_context(cafile=certifi.where())
    except Exception:  # noqa: BLE001 — certifi optional
        pass

    opener = urllib.request.build_opener(
        _HTTPRedirectHandler308(),
        urllib.request.HTTPSHandler(context=ctx),
    )
    req = urllib.request.Request(
        url,
        headers={
            "User-Agent": USER_AGENT,
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
            "Accept-Language": "en-NZ,en;q=0.9",
            "Accept-Encoding": "identity",
            "Cache-Control": "no-cache",
        },
        method="GET",
    )
    try:
        with opener.open(req, timeout=timeout) as resp:
            raw = resp.read(2_000_000)
            charset = resp.headers.get_content_charset() or "utf-8"
            try:
                body = raw.decode(charset, errors="replace")
            except LookupError:
                body = raw.decode("utf-8", errors="replace")
            return int(resp.status), str(resp.geturl()), body, _header_map(resp.headers)
    except urllib.error.HTTPError as e:
        raw = e.read(500_000) if e.fp else b""
        body = raw.decode("utf-8", errors="replace")
        # Prefer the error object's URL when redirects were followed before failing.
        final = getattr(e, "url", None) or url
        try:
            if e.hdrs and e.hdrs.get("Location") and e.code in {301, 302, 303, 307, 308}:
                final = urljoin(url, e.hdrs.get("Location"))
        except Exception:  # noqa: BLE001
            pass
        return int(e.code), str(final), body, _header_map(e.headers)
    except Exception as e:  # noqa: BLE001 — surface any network failure as reject
        raise RuntimeError(f"fetch failed: {e}") from e


def company_title_present(body: str, company: str | None, title: str | None) -> list[str]:
    missing: list[str] = []
    text = re.sub(r"\s+", " ", body).lower()
    if company:
        token = company.strip().lower()
        # Allow short brand tokens (e.g. "Smartly") and drop Ltd/Limited noise.
        token = re.sub(r"\b(limited|ltd|inc|llc)\b\.?", "", token).strip()
        if len(token) >= 3 and token not in text:
            missing.append(f"company name not found on page: {company}")
    if title:
        # Require at least half the significant words from the title.
        words = [w for w in re.findall(r"[a-z0-9]+", title.lower()) if len(w) > 2]
        words = [w for w in words if w not in {"the", "and", "for", "with", "role"}]
        if words:
            hits = sum(1 for w in words if w in text)
            if hits < max(1, (len(words) + 1) // 2):
                missing.append(f"role title not found on page: {title}")
    return missing


def verify(url: str, company: str | None = None, title: str | None = None) -> VerifyResult:
    reasons: list[str] = []
    parsed = urlparse(url.strip())
    if parsed.scheme not in {"http", "https"} or not parsed.netloc:
        return VerifyResult("reject", ["URL must be absolute http(s)"])

    bl = load_blacklist()
    host = parsed.netloc.lower()
    if host_blacklisted(host, list(bl.get("domains") or [])):
        reasons.append(f"blacklisted host: {host}")
    for needle in bl.get("path_deny_substrings") or []:
        if needle.lower() in (parsed.path + "?" + (parsed.query or "")).lower():
            reasons.append(f"blacklisted path pattern: {needle}")

    board_reason = classify_board_url(url)
    if board_reason:
        reasons.append(board_reason)

    if reasons:
        return VerifyResult("reject", reasons)

    try:
        status, final_url, body, headers = fetch(url)
    except RuntimeError as e:
        # SEEK often blocks scripted fetches (proxy/tunnel/CF) without challenge HTML.
        # Treat as bot_blocked so automations browser-confirm instead of hard-rejecting.
        if SEEK_DETAIL_RE.search(url):
            return VerifyResult(
                "bot_blocked",
                [
                    f"SEEK fetch failed ({e}); confirm in a browser — "
                    "listing may still be live"
                ],
            )
        return VerifyResult("reject", [str(e)])

    # Unfollowed 308/redirect shells on SEEK still mean "script could not read listing".
    if status in {301, 302, 303, 307, 308} and SEEK_DETAIL_RE.search(url):
        loc = headers.get("location")
        if loc:
            try:
                status, final_url, body, headers = fetch(urljoin(url, loc))
            except RuntimeError as e:
                return VerifyResult(
                    "bot_blocked",
                    [f"SEEK redirect could not be fetched ({e}); confirm in a browser"],
                )

    # Bot interstitials (common on SEEK) — not proof the listing is bad.
    if is_bot_challenge(status, body, headers):
        detail = f"HTTP {status}" if status else "fetch blocked"
        return VerifyResult(
            "bot_blocked",
            [
                f"bot protection challenge ({detail}); confirm in a browser — "
                "listing may still be live"
            ],
        )

    # SEEK detail pages that return hard bot HTTP codes without challenge HTML.
    if SEEK_DETAIL_RE.search(final_url or url) and status in {401, 403, 429, 503}:
        return VerifyResult(
            "bot_blocked",
            [
                f"bot protection challenge (HTTP {status}); confirm in a browser — "
                "listing may still be live"
            ],
        )

    if status >= 400:
        reasons.append(f"HTTP {status}")

    final_board = classify_board_url(final_url)
    if final_board:
        reasons.append(f"redirected to {final_board}")

    if host_blacklisted(urlparse(final_url).netloc, list(bl.get("domains") or [])):
        reasons.append(f"redirected to blacklisted host: {urlparse(final_url).netloc}")

    if REMOVED_RE.search(body):
        reasons.append("page indicates job removed/closed/expired")
    if PAYWALL_RE.search(body):
        reasons.append("page shows paywall / login-to-apply / premium apply signals")

    reasons.extend(company_title_present(body, company, title))

    # Soft length check — empty shells and soft-404s are common on aggregators.
    if len(body.strip()) < 400:
        reasons.append("page body too short to be a real listing")

    if reasons:
        return VerifyResult("reject", reasons)
    return VerifyResult("ok", [])


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("url", help="Candidate listing URL")
    parser.add_argument("--company", default=None)
    parser.add_argument("--title", default=None)
    parser.add_argument("--json", action="store_true", help="Print JSON result")
    args = parser.parse_args()

    result = verify(args.url, company=args.company, title=args.title)
    payload = {
        "ok": result.ok,
        "status": result.status,
        "bot_blocked": result.bot_blocked,
        "url": args.url,
        "reasons": result.reasons,
    }
    if args.json:
        print(json.dumps(payload, indent=2))
    else:
        if result.ok:
            print(f"OK: {args.url}")
        elif result.bot_blocked:
            print(f"BOT_BLOCKED: {args.url}")
            for r in result.reasons:
                print(f"  - {r}")
        else:
            print(f"REJECT: {args.url}")
            for r in result.reasons:
                print(f"  - {r}")

    if result.ok:
        return 0
    if result.bot_blocked:
        return 3
    return 1


if __name__ == "__main__":
    sys.exit(main())
