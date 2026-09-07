# Setup guide — Job Hunt Kit

## 1. Configure identity and search

Copy the example config and edit it:

```bash
cp config.example.json config.json
```

Important fields:

| Field | Meaning |
|-------|---------|
| `applicant.full_name` | Appears on resumes and cover letters |
| `applicant.file_prefix` | Filename prefix, e.g. `JaneDoe` → `JaneDoe-Resume-Xero.md` |
| `applicant.email` / `phone` / `links` | Contact line |
| `applicant.spelling` | e.g. `en-NZ` or `en-US` |
| `applicant.work_auth_note` | Honest one-liner for visa / sponsorship |
| `search.primary` | Titles and locations the scanner keeps |
| `search.adjacent` | Optional non-dev roles, restricted to listed cities |
| `search.max_prepared_per_run` | Cap per successful day (default 5) |
| `schedule.cron_utc_slots` | Must match what you set in Cursor Automations |
| `launch_agent.label` | Unique LaunchAgent id on your Mac |

Then:

```bash
python3 -m pip install -r requirements.txt
python3 scripts/bootstrap.py
```

Bootstrap will:

1. Create `profile.md` and `master-resume.md` stubs if missing
2. Render `SKILL.md`, `templates.md`, and automation instruction files from `templates/*.tmpl`
3. Create empty `tracked-jobs.json` if missing
4. Render `assets/Resume-Master.pdf` (+ root `Resume-Master.pdf`) from `master-resume.md`

## 2. Write your profile

Edit **`profile.md`** thoroughly:

- Contact and work authorisation
- Skills you can evidence
- Experience and projects with purpose + outcome bullets
- **Claims to Avoid** (unsupported slogans, inflated scope)

Edit **`master-resume.md`** into a real one-page (or two-page) base resume using the style in `templates.md`.

Re-run bootstrap after major edits:

```bash
python3 scripts/bootstrap.py
```

## 3. Connect GitHub + Cursor Automation

1. Create a **private** GitHub repo and push this kit.
2. In Cursor → **Cloud Agents**, ensure this repo can run (deps install via `.cursor/environment.json`).
3. Create a **Cursor Automation**:
   - Trigger: cron matching `schedule.cron_utc_slots` in config
   - Repository: this repo, branch `main`
   - Instructions: paste everything below the `---` in `automation-instructions.md`
4. Confirm `.github/workflows/merge-cursor-automation.yml` is present so `cursor/**` bot branches can land on `main`.

### Cron reminder (NZ afternoon)

| UTC | NZST (UTC+12) |
|-----|----------------|
| 03:30 | 3:30 PM |
| 04:00 | 4:00 PM |
| 04:30 | 4:30 PM |
| 05:00 | 5:00 PM |
| 05:30 | 5:30 PM |

Hours `15`–`17` UTC are **early morning** NZ — avoid them for afternoon runs.

## 4. Mac sync

Cloud agents cannot write to `~/Downloads`. Install the LaunchAgent on the Mac that should receive PDFs:

```bash
./scripts/install_mac_sync_launchagent.sh
gh auth login   # once, if pulls fail from LaunchAgent
./scripts/sync_cloud_results.sh --today --open
```

## 5. Optional review UI

```bash
./scripts/start_review_ui.sh
# open http://127.0.0.1:8765
```

## Customising for another country / market

Edit `config.json` → `search` (titles, locations, preferred sources) and re-run bootstrap.  
Adjust `source-blacklist.json` if your market uses different aggregator domains.  
Update `schedule` if your timezone differs — and set Cursor cron accordingly.

## Updating prompt templates

Edit files under `templates/` (`*.tmpl`), then:

```bash
python3 scripts/bootstrap.py
```

Do not hand-edit the rendered `SKILL.md` / `automation-instructions.md` long-term — they will be overwritten.

## Checklist before sharing this kit with a friend

- [ ] They clone a clean copy (no your `applications/` or personal `profile.md`)
- [ ] They create their own `config.json`
- [ ] They run `bootstrap.py` and fill profile + master resume
- [ ] They push to **their** GitHub repo
- [ ] They create **their** Cursor Automation
- [ ] They install the LaunchAgent on **their** Mac
