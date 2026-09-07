# Mac Sync — how PDFs and the daily report land on this machine

Cloud Automations **cannot** write to `/Users/...` or this Mac’s `~/Downloads`.
If a “local sync” Cursor Automation runs on Linux, treat that as a misconfigured **cloud** run.

## Recommended: macOS LaunchAgent (local time)

```bash
./scripts/install_mac_sync_launchagent.sh
```

- Runs every 15 minutes across the local afternoon sync window (`15:45-18:45`).
- Calls `./scripts/sync_cloud_results.sh --today`
- Pulls `origin/main`, copies recent `AlexExample-*.pdf` into `~/Downloads`
- LaunchAgent label: `com.alexexample.job-hunt.sync-cloud-results`
- Logs: `~/Library/Logs/job-hunt-kit/sync-cloud-results.{out,err}.log`

Manual anytime:

```bash
./scripts/sync_cloud_results.sh --today --open
```

If sync fails with “could not read Username for https://github.com”, run `gh auth login` once in Terminal.

## Optional: Cursor Automation (only if runtime is Local)

1. Runtime **must** be **Local** (not Cloud).
2. Trigger on a schedule overlapping the sync window, or manually after the cloud run.
3. Instructions: run the same sync script (below).

A git-push-triggered Cursor Automation still runs in the **cloud** and cannot pull into this Mac. Use the LaunchAgent for that.

---

You are the local sync companion for Alex Example's daily job-application cloud scanner.
You must refuse to continue if this machine is not the user's Mac (Darwin) or if this repository checkout is missing.

## Goal
Bring cloud results onto this Mac and show a clear summary in this chat.

## Steps
1. If `uname` is not Darwin, stop immediately and say: use the Mac LaunchAgent / run the sync script on the Mac.
2. In this repository root, run:
   `./scripts/sync_cloud_results.sh --today --open`
3. If the script fails because of local uncommitted changes, report them and stop — do not force-reset.
4. If the script fails because of GitHub auth, tell the user to run `gh auth login` once, then retry.
5. Read `daily-runs/YYYY-MM-DD.md` (today's local date). If missing, check for `*-attempt-*.md` or `*-NEEDS-APPROVAL.md` and summarise those instead.
6. Confirm which `AlexExample-*.pdf` files were copied into `~/Downloads`.
7. End with a short human report:
   - Did today succeed / no new roles / still failing?
   - Roles prepared (company + title), or none
   - PDF paths now in `~/Downloads`
   - Anything needing manual follow-up (NEEDS-APPROVAL, bad URLs, missing push)

Do not search job boards or regenerate application materials — sync and report only.
