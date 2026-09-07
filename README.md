# Job Hunt Kit

A **shareable template** for a daily job-application automation: search → verify URLs → tailor resume/cover letter → export PDFs → ship to GitHub → sync PDFs to your Mac.

Someone else can clone this, fill in their profile, and start the automation without inheriting another person's applications or personal data.

## What you get

| Piece | Purpose |
|-------|---------|
| `config.json` | Your name, file prefix, search market, schedule |
| `profile.md` / `master-resume.md` | Your content (source of truth) |
| `SKILL.md` / `templates.md` | Agent tailoring rules (rendered from `templates/`) |
| `automation-instructions.md` | Cloud Cursor Automation prompt |
| `scripts/` | PDF export, URL verifier, Mac sync LaunchAgent |
| `applications/` | Per-role tailored packs (starts empty) |
| `daily-runs/` | Daily scanner reports (starts empty) |
| `review-ui/` | Local browser UI to review prepared roles |

## Quick start (new person)

```bash
# 1. Clone and enter the repo
git clone <this-repo-url> my-job-hunt && cd my-job-hunt

# 2. Create your config
cp config.example.json config.json
# Edit config.json — set full_name, file_prefix, email, phone, links, search prefs

# 3. Bootstrap prompts + profile stubs + master PDF
python3 -m pip install -r requirements.txt
python3 scripts/bootstrap.py

# 4. Fill real content
#    - Edit profile.md (experience, projects, Claims to Avoid)
#    - Edit master-resume.md (your base resume)
python3 scripts/bootstrap.py   # refresh prompts + Resume-Master.pdf

# 5. Push to your own GitHub repo (private recommended)
git remote set-url origin git@github.com:YOU/your-job-hunt.git
git add -A && git commit -m "Personalise job-hunt-kit" && git push -u origin main

# 6. Cursor → Automations → new automation
#    - Repo: this repo, branch main
#    - Cron (UTC): 30 3, 0 4, 30 4, 0 5, 30 5  (afternoon NZST)
#    - Instructions: paste from automation-instructions.md (below the ---)

# 7. On your Mac, sync PDFs after cloud runs
./scripts/install_mac_sync_launchagent.sh
```

See [SETUP.md](SETUP.md) for a longer walkthrough and customization tips.

## Daily flow (once running)

```
Cloud cron (afternoon)
    → agent searches + prepares up to N roles
    → commits PDFs + daily-runs/ to origin/main
    → (optional) GitHub Action merges cursor/** branches
Mac LaunchAgent
    → pulls main
    → copies {file_prefix}-*.pdf into ~/Downloads
```

## Local commands

```bash
# Tailor one role interactively in Cursor, then:
python3 scripts/export_application_pdfs.py {company}-{role-slug}

# Pull cloud results now
./scripts/sync_cloud_results.sh --today --open

# Review UI
./scripts/start_review_ui.sh   # http://127.0.0.1:8765

# After editing config.json or templates/*.tmpl
python3 scripts/bootstrap.py
```

## Privacy

- `config.json` is gitignored — keep secrets/personal contact out of commits if you prefer (or commit a redacted version).
- Do **not** share your filled `profile.md`, `applications/`, or `daily-runs/` when publishing a public template fork.
- This kit ships with empty applications history and example identity (`Alex Example`) until you bootstrap.

## License / sharing

Intended as a personal toolkit template. Share the **empty kit**, not someone else's filled applications.
