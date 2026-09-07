---
name: job-hunt
description: >-
  Tailor resumes and write cover letters for Alex Example.
  Maintains a living professional profile, master resume, and per-application
  outputs. All resumes must follow the layout in Resume-Master.pdf.
  Use when the user shares a job listing, asks to tailor a resume, write a
  cover letter, update their professional profile, or mentions job applications.
---

# Job Applications Workflow

## Source of Truth

Always read these files before generating application materials:

1. [profile.md](profile.md) — living professional model (skills, projects, preferences, accuracy notes)
2. [master-resume.md](master-resume.md) — base resume content to tailor from
3. [Resume-Master.pdf](Resume-Master.pdf) / [assets/Resume-Master.pdf](assets/Resume-Master.pdf) — canonical layout
4. [templates.md](templates.md) — style spec, tailoring checklist, cover letter structure
5. [config.json](config.json) — name, file prefix, search preferences

**Never invent experience.** Only use claims supported by `profile.md`. Check "Claims to Avoid" before writing.

Spelling: en-NZ.

---

## Phase 1: Build / Refresh Profile

Run when first setup, when the user shares new experience, or says "update my profile".

1. Read `profile.md`
2. Incorporate new information from the user's prompt
3. Update relevant sections and add a changelog entry
4. If projects changed materially, update `master-resume.md` too
5. Share a brief summary of what changed

---

## Phase 2: Master Resume

Rules:
- Follow the **Master Resume Style** in [templates.md](templates.md)
- Tone: professional and friendly; confident yet humble
- 1–2 pages equivalent
- Lead with strongest evidence-backed projects
- Avoid unsupported identity slogans; prefer concrete project evidence

After editing master content, regenerate the layout reference:

```bash
python3 scripts/bootstrap.py
```

---

## Phase 3: Tailor for a Job Listing

1. Read `profile.md`, `master-resume.md`, `Resume-Master.pdf`, and `templates.md`
2. Parse the listing: required skills, nice-to-haves, role level, company values
3. Follow the tailoring checklist in `templates.md`
4. Produce tailored resume — same layout; tailor content only
5. Write cover letter (default: yes when applying)
6. Save under `applications/{company}-{role-slug}/` as:
   - `AlexExample-Resume-{Company Name}.md`
   - `AlexExample-CoverLetter-{Company Name}.md`
7. Export PDFs: `python3 scripts/export_application_pdfs.py {company}-{role-slug}`
8. Present both documents with a brief note on tailoring choices

### Style Requirements

- Match Resume-Master.pdf layout
- Spelling: en-NZ
- Tone — professional and friendly; confident yet humble
- Accuracy — see profile.md "Claims to Avoid"
- Purpose + outcome bullets — every bullet states why it mattered or what improved
- No fabrication — if a skill is in the listing but not in profile, do not claim it

---

## Phase 4: Iterate

Apply user feedback to application files; if permanent, update `profile.md` or `templates.md`.

---

## Quick Commands

| User says | Action |
|-----------|--------|
| "Apply for this role" + listing | Phase 3: tailor resume + cover letter |
| "Tailor my resume for..." | Phase 3, resume only unless cover letter requested |
| "Write a cover letter for..." | Phase 3, cover letter |
| "Update my profile with..." | Phase 1 |
| "Refresh my master resume" | Phase 2 |
| "What do you know about me?" | Summarise `profile.md` |
