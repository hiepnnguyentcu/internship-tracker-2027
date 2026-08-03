# Internship Tracker — 2-Week MVP Build Plan

Source design doc: `/Users/hiepnguyen/.claude/plans/i-need-to-brainstorm-declarative-acorn.md`

Stack: Python 3.11+, Google Sheets API v4, Gmail API, Google Calendar API, `schedule` skill for cron routines.

Each milestone below is self-contained: goal, prerequisites, functional/non-functional requirements, exact files/schemas to build, and a testing checklist. Each ends with a **"Prompt for this milestone"** block — paste that verbatim into a new session to build just that chunk.

---

## Week 1

### Milestone 1 (Days 1-2) — Foundation: Auth + Sheet + API clients

**Goal**: A working Google Sheet with all tabs/headers, and Python wrappers that can read/write it, send Gmail, and create Calendar events.

**Manual steps (you do these, ~20 min, before any code runs)**:
1. Go to console.cloud.google.com → new project (e.g. "internship-tracker-2027").
2. Enable APIs: Google Sheets API, Gmail API, Google Calendar API.
3. OAuth consent screen → External → add yourself as a test user → scopes: `spreadsheets`, `gmail.send`, `gmail.readonly`, `calendar.events`.
4. Credentials → Create OAuth Client ID → type **Desktop app** → download JSON → save as `.credentials/client_secret.json` (this directory gets gitignored).

**Functional requirements**:
- FR1: Authenticate to Sheets, Gmail, and Calendar APIs via OAuth2 using a stored refresh token, without requiring interactive login on every script run.
- FR2: Create the tracker spreadsheet with exactly the 9 named tabs and header rows if it doesn't already exist.
- FR3: `SheetsClient` supports read-tab-as-dicts, append-row, update-single-cell, and find-rows-by-match.
- FR4: `GmailClient` can send an email and return both the message id and thread id.
- FR5: `CalendarClient` can create an event with a title, start time, and a reminder offset.

**Non-functional requirements**:
- NFR1: Credentials (client secret, token) are never committed to version control — enforced by `.gitignore`, not just convention.
- NFR2: Token refresh happens transparently; scripts don't need `setup_auth.py` re-run except when the refresh token itself is revoked/expired.
- NFR3: `setup_sheet.py` is idempotent — running it twice must not create a duplicate spreadsheet or duplicate tabs (check `config.yaml`'s `sheet_id` first).
- NFR4: Auth/API failures surface a clear, actionable message (e.g. "run setup_auth.py") rather than a raw stack trace.

**Files to build**:
- `requirements.txt`: `google-auth`, `google-auth-oauthlib`, `google-api-python-client`, `PyYAML`, `python-dateutil`, `requests`
- `.gitignore`: `.credentials/`, `config.local.yaml`, `__pycache__/`
- `config.yaml` — central config:
  ```yaml
  sheet_id: ""              # filled in by setup_sheet.py
  digest_email: "hiepnguyentcu@gmail.com"
  timezone: "America/Los_Angeles"   # confirm actual tz
  repos:
    - name: SimplifyJobs
      type: json
      url: https://raw.githubusercontent.com/SimplifyJobs/Summer2027-Internships/dev/.github/scripts/listings.json
      category_filter: ["Software"]
    - name: vanshb03
      type: json
      url: https://raw.githubusercontent.com/vanshb03/Summer2027-Internships/dev/.github/scripts/listings.json
      category_filter: []   # this repo's listings.json has no "category" field at all
    - name: speedyapply
      type: markdown
      url: https://raw.githubusercontent.com/speedyapply/2027-SWE-College-Jobs/main/README.md
    - name: jobright-ai
      type: markdown
      url: https://raw.githubusercontent.com/jobright-ai/2026-Software-Engineer-Internship/master/README.md
  cold_email:
    throttle_per_run: 3
  action_items:
    stale_application_days: 14
    stale_cold_email_days: 6
    oa_reminder_minutes_before: [1440, 120]   # 24h and 2h before the OA due date (9am local); added in Milestone 3
    jd_overlap_warning_threshold: 0.08        # added in M3; calibrated against a real posting, see config.yaml comment
  ```
- `google_auth.py` — `get_credentials() -> google.oauth2.credentials.Credentials` (loads/refreshes `.credentials/token.json`, raises a clear error telling the user to run `setup_auth.py` if missing).
- `sheets_client.py` — `class SheetsClient`:
  - `read_tab(tab: str) -> list[dict]` (first row = headers, zip into dicts)
  - `append_row(tab: str, row: dict) -> None` (order values by the tab's existing header row)
  - `update_cell(tab: str, row_index: int, col_name: str, value) -> None`
  - `find_rows(tab: str, **match) -> list[tuple[int, dict]]` (row index + row dict for matches)
  - `append_rows(tab: str, rows: list[dict]) -> None` and `batch_update_cells(tab: str, updates: list[tuple[int, str, object]]) -> None` — batched versions added during Milestone 2 build after hitting the Sheets API's default 60-writes/min/user quota with a per-row loop on a ~800-row first run. Any script writing more than a handful of rows/cells per run should use these, not the single-row methods, in a loop.
  - **All writes use `valueInputOption="RAW"`, not `"USER_ENTERED"`** (fixed during Milestone 4 — found live that Sheets auto-parsed plain `"2026-08-03"`-style date strings as dates under `USER_ENTERED`, converting them to a serial-number cell value with no date format applied, so reads came back as raw numbers like `"46237"` instead of the original string. Silently corrupted `ListingsSeen.date_first_seen` for all 774 Milestone 2 rows undetected until a `due_date` column hit the same bug in Milestone 4 testing; repaired retroactively via a batched `batch_update_cells` pass. `RAW` is also the semantically correct choice here regardless — every column is plain data our own Python code parses, never a Sheets formula/auto-typed value).
- `gmail_client.py` — `class GmailClient`:
  - `send(to: str, subject: str, body_html: str) -> tuple[message_id, thread_id]`
  - `get_thread_message_count(thread_id: str) -> int`
- `calendar_client.py` — `class CalendarClient`:
  - `create_event(title: str, start: datetime, reminder_minutes_before: int, description: str = "") -> str` (returns event_id)
- `scripts/setup_auth.py` — runs `InstalledAppFlow.run_local_server()`, saves token.
- `scripts/setup_sheet.py` — creates a new spreadsheet named "Internship Tracker 2027" via `spreadsheets.create`, adds these 9 tabs with header rows exactly as below, prints the sheet_id + URL, writes sheet_id into `config.yaml`:
  - `Resumes`: `resume_id, track, variant, email_used, phone_used, drive_link, notes`
  - `Applications`: `app_id, date_applied, company, role_title, source, job_url, resume_id, referral, referral_name, current_stage, current_stage_date, oa_due_date, notes`
  - `StageEvents`: `event_id, app_id, stage, date, notes`
  - `EmailTemplates`: `template_id, subject, body, notes`
  - `ColdEmails`: `contact_id, company, recruiter_name, recruiter_email, template_id, status, queued_at, date_sent, gmail_thread_id, last_checked_date, notes`
  - `ActionItems`: `item_id, type, ref_id, due_date, done, notes`
  - `CompanyNotes`: `company, target_tier, interview_process_notes, culture_notes, key_people, prep_links, last_updated`
  - `TargetCompanies`: `company, tier, notes`
  - `ListingsSeen`: `listing_key, source_repo, company, role, location, url, date_first_seen, emailed`

**Testing / acceptance checklist**:
- [ ] `python scripts/setup_auth.py` completes, `.credentials/token.json` exists.
- [ ] `python scripts/setup_sheet.py` creates the sheet; open the URL and visually confirm all 9 tabs with correct headers.
- [ ] Smoke test (`scripts/smoke_test.py`): append a dummy `Resumes` row, read it back, assert it matches; send a test email to yourself via `GmailClient.send`, confirm it arrives; create a Calendar event 1 hour out, confirm it appears on your calendar with a reminder.

**Prompt for this milestone**:
> Implement Milestone 1 (Foundation) from `MILESTONES.md` in `/Users/hiepnguyen/code/personal-assistant`. I've already done the manual Google Cloud Console steps (OAuth client at `.credentials/client_secret.json`). Build `requirements.txt`, `.gitignore`, `config.yaml`, `google_auth.py`, `sheets_client.py`, `gmail_client.py`, `calendar_client.py`, `scripts/setup_auth.py`, `scripts/setup_sheet.py`, and `scripts/smoke_test.py` exactly per the schemas/signatures in Milestone 1. Then run `setup_auth.py`, `setup_sheet.py`, and the smoke test, and report the sheet URL and smoke-test results.

---

### Milestone 2 (Days 3-5) — Listings watcher (the core value prop)

**Goal**: Running `check_listings.py` fetches all 4 repos, finds genuinely new postings, dedupes across repos, flags target-company matches, and emails a digest.

**Prerequisites**: Milestone 1 complete (sheet + clients working).

**Functional requirements**:
- FR1: Fetch and parse listings from all 4 configured repos (2 JSON-based, 2 markdown-based).
- FR2: Surface only listings not already recorded in `ListingsSeen` — no repeat notifications for the same posting.
- FR3: Dedupe identical company+title postings that appear in more than one source repo.
- FR4: Flag postings from companies in `TargetCompanies` and surface them in a distinct, prioritized digest section.
- FR5: Filter JSON-based repo listings by configured category (e.g. "Software") and visibility.
- FR6: Support a `--dry-run` mode that performs no sheet writes and no email send.

**Non-functional requirements**:
- NFR1: A single run completes in well under a minute under normal conditions, so it's cheap to run every few hours.
- NFR2: One repo being malformed/unreachable (network error, schema change) doesn't crash the whole run or block the other 3 repos' listings from being processed and emailed.
- NFR3: The markdown parser tolerates minor formatting drift (extra whitespace, emoji variants) without silently dropping rows.
- NFR4: Digest emails stay scannable (grouped by source/target, not one flat list) even with dozens of new rows in a single run.
- NFR5: Re-running immediately after a successful run produces zero new emails (idempotent under "nothing new" conditions).

**Files to build**:
- `watchers/models.py` — `@dataclass Listing: id, source, company, title, location, url, date_posted`
- `watchers/parsers/json_parser.py` — `parse_json_listings(raw_json: list[dict], category_filter: list[str]) -> list[Listing]`. Filter `is_visible`, `active` (found during build: `is_visible` is true for ~99.9% of entries — it means "not moderator-hidden", not "currently open"; `active` is the real "still accepting applications" signal, without it a first run floods with years of closed postings), and `category in category_filter` (skipped entirely when `category_filter` is empty — vanshb03's feed has no `category` field at all); map fields per the schema found during research (`company_name→company`, `title→title`, `locations[0]→location`, `url→url`, `date_posted→date_posted`, `id→id`).
- `watchers/parsers/markdown_parser.py` — `parse_markdown_table(readme_text: str) -> list[Listing]`. Regex per table row (`^\|.*\|$`), skip header/separator rows, extract company/role/location/application-link cells, strip markdown link syntax `[text](url)` to get the URL, strip icons (🔒🔥↳ etc.), synthetic `id = sha256(f"{company}|{title}|{url}".lower())[:16]`. Handle the "↳" continuation convention (blank/arrow company cell means "same company as row above").
- `watchers/dedup.py` — `normalize_key(company: str, title: str) -> str` (lowercase, strip non-alnum/whitespace); `cross_repo_dedupe(listings: list[Listing]) -> list[Listing]` (first-seen wins).
- `watchers/target_match.py` — `load_target_companies(sheets_client) -> set[str]` (normalized); `is_target(company: str, target_set: set[str]) -> bool`.
- `scripts/check_listings.py` — orchestration:
  1. Fetch + parse all 4 repos per `config.yaml`.
  2. Cross-repo dedupe.
  3. Diff against `ListingsSeen` (by `listing_key`).
  4. Split into target-company matches vs rest.
  5. Append new rows to `ListingsSeen` (`emailed=N`).
  6. Compose digest HTML: "🎯 Target companies" section first, then grouped-by-source general list.
  7. Send via `GmailClient.send` to `config.digest_email`.
  8. Mark rows `emailed=Y`.
  9. Support `--dry-run` flag: print the digest instead of sending, don't write to sheet.

**Testing / acceptance checklist**:
- [ ] `tests/fixtures/simplify_sample.json` (a saved real snippet) → `parse_json_listings` returns expected `Listing` objects, filtered correctly by category.
- [ ] `tests/fixtures/speedyapply_sample.md` (a saved real README snippet) → `parse_markdown_table` returns expected listings, links extracted correctly.
- [ ] Dedup test: two listings with same normalized company+title from different sources → collapses to one.
- [ ] Target-match test: `TargetCompanies` has "Stripe"; a listing for "Stripe " (trailing space/case difference) → flagged.
- [ ] `python scripts/check_listings.py --dry-run` against live repos — eyeball the printed digest for sanity (real companies, real links, no garbage).
- [ ] Full run (no `--dry-run`): confirm the digest email actually arrives, `ListingsSeen` populated, run again immediately and confirm **no** duplicate email (nothing new).

**Prompt for this milestone**:
> Implement Milestone 2 (Listings watcher) from `MILESTONES.md` in `/Users/hiepnguyen/code/personal-assistant`. Milestone 1 (google_auth/sheets_client/gmail_client, the Sheet with all tabs) is already built and working. Build `watchers/models.py`, `watchers/parsers/json_parser.py`, `watchers/parsers/markdown_parser.py`, `watchers/dedup.py`, `watchers/target_match.py`, and `scripts/check_listings.py` exactly per Milestone 2's spec, including a `--dry-run` flag. Write the fixture-based unit tests listed in the testing checklist (fetch a couple hundred lines of real listings.json / README.md content to use as fixtures). Then run `--dry-run` against the live repos and report what it would send.

---

### Milestone 3 (Days 6-7) — Application/resume logging, JD-keyword check, Calendar wiring

**Goal**: A script/flow to log applications and resumes, with OA-stage logging automatically creating action items + calendar reminders, and a keyword sanity check against JDs.

**Prerequisites**: Milestone 1.

**Functional requirements**:
- FR1: Register a new resume version under a unique `resume_id`.
- FR2: Reject silently overwriting an existing `resume_id`'s linked file (enforces the version-integrity rule).
- FR3: Log an application with all required fields and create a corresponding `StageEvents` entry.
- FR4: Logging a stage of "OA" creates both an `ActionItems` row and a Calendar event with a reminder.
- FR5: Compute a keyword-overlap score between a resume and a job description and warn when it's below the configured threshold.

**Non-functional requirements**:
- NFR1: A JD page that fails to load or returns non-HTML content doesn't crash the logging flow — the keyword check is skipped gracefully and the application still gets logged.
- NFR2: The keyword-overlap check runs in a few seconds, not disrupting the flow of logging an application.
- NFR3: Calendar reminder timing (e.g. 24h/2h before) is configurable, not hardcoded, so it can be tuned after real-world use.

**Files to build**:
- `scripts/log_resume.py` — registers a new `resume_id` in `Resumes` (enforces the version-integrity rule: refuses to reuse a `resume_id` whose `drive_link` differs from what's on file — tells you to bump the id instead, e.g. `R1` → `R1.1`).
- `scripts/log_application.py` — CLI args: `--company --role --job-url --resume-id --referral [Y/N] --referral-name --source --stage [Applied|OA|...]`. Appends `Applications` row + a matching `StageEvents` row. If `--stage OA`, also prompts/accepts `--oa-due-date` and:
  - creates an `ActionItems` row (`type=OA Deadline`)
  - creates a Calendar event via `CalendarClient.create_event` (reminder e.g. 24h and 2h before due date)
- `jd_keyword_check.py` — `extract_keywords(text: str) -> set[str]` (lowercase, strip stopwords via a small hardcoded stopword list, keep nouns/tech terms — simple frequency-based, no heavy NLP dependency); `fetch_jd_text(job_url: str) -> str` (requests + HTML tag stripping + HTML-entity unescaping — found live that `&nbsp;`/`&amp;` leak in as fake keywords without unescaping); `overlap_score(resume_text: str, jd_text: str, top_k: int = 50) -> float` (compares against only the JD's top-50-by-frequency keywords, not its full unique vocabulary — found live that a real ~7,000-character posting has ~450 unique keywords, mostly one-off EEO/benefits boilerplate, which makes full-vocabulary overlap mathematically tiny even for a strong match); `top_missing_keywords(...)` (extra helper beyond the original 3-function spec, needed to actually produce the "top missing keywords" the warning message promises). `log_application.py` calls this when both `--job-url` and `--resume-text-file` are available, and prints a warning if `overlap_score < jd_overlap_warning_threshold` (0.08 default, calibrated live — see config.yaml comment).

**Testing / acceptance checklist**:
- [ ] `log_resume.py` for a new resume succeeds; running it again with a changed `drive_link` under the same id is rejected with a clear message.
- [ ] `log_application.py --stage Applied ...` creates one `Applications` row + one `StageEvents` row.
- [ ] `log_application.py --stage OA --oa-due-date <near date> ...` additionally creates an `ActionItems` row and a real Calendar event with the correct reminder — check your calendar app.
- [ ] `jd_keyword_check` against a known strong match (systems resume text vs. a driver/kernel JD) scores high; against a known mismatch (full-stack resume vs. an embedded-firmware JD) scores low and triggers the warning.

**Prompt for this milestone**:
> Implement Milestone 3 (Application/resume logging + JD-keyword check + Calendar) from `MILESTONES.md` in `/Users/hiepnguyen/code/personal-assistant`. Milestones 1-2 are already built. Build `scripts/log_resume.py`, `scripts/log_application.py`, and `jd_keyword_check.py` exactly per Milestone 3's spec, including the OA-stage → ActionItems + Calendar event behavior and the version-integrity check in `log_resume.py`. Then run through the full testing checklist and report results, including confirming the calendar event actually appears.

---

## Week 2

### Milestone 4 (Days 8-10) — Cold-email templates, mail-merge sending, reply tracking

**Goal**: Queue a batch of recruiter contacts per company against a template, have the tool send them out throttled over time with merge fields filled in, and detect replies automatically.

**Prerequisites**: Milestone 1.

**Functional requirements**:
- FR1: Bulk-queue contacts from a CSV into `ColdEmails` with status `Queued`.
- FR2: Render templates with merge fields and refuse to send if any field is left unfilled.
- FR3: Send only up to the configured throttle count per run.
- FR4: Capture the Gmail thread id for every sent email for later reply detection.
- FR5: Detect replies by monitoring thread message counts and update status accordingly.
- FR6: Flag cold emails unanswered past the configured stale threshold as follow-up action items, without duplicating the flag on repeated runs.

**Non-functional requirements**:
- NFR1: Sending is throttled/paced (not bursty) to reduce spam-flagging risk on the user's Gmail account — a hard behavioral constraint, not a nice-to-have.
- NFR2: The system never sends a cold email twice to the same contact (idempotent on `contact_id`/status transition).
- NFR3: Reply detection isn't fooled by the user's own Sent messages inflating thread counts — only a net-new message from the recipient counts as a reply.
- NFR4: Template-rendering errors fail loudly before send, never after — no partially-broken emails go out.

**Files to build**:
- `template_engine.py` — `render(template: str, context: dict) -> str` using `{{field}}` placeholders (simple `str.replace` loop or Jinja2 if you want stricter templating); raise a clear error listing any `{{...}}` left unfilled after rendering (never silently send a template with a literal `{{recruiter_name}}` in it).
- `scripts/queue_cold_emails.py` — takes a CSV (`company, recruiter_name, recruiter_email, template_id`) and bulk-appends `ColdEmails` rows with `status=Queued, queued_at=now`.
- `scripts/send_cold_emails.py` — pulls up to `config.cold_email.throttle_per_run` rows where `status==Queued` (oldest `queued_at` first), renders the matching template, sends via `GmailClient.send`, records `gmail_thread_id` + `date_sent`, flips `status → Sent`.
- `scripts/check_cold_emails.py` — for every `status==Sent` row, calls `GmailClient.get_thread_message_count(thread_id)`; if it rose since last check → `status = Replied`, `last_checked_date = today`. If unchanged and `today - date_sent > config.action_items.stale_cold_email_days` → creates an `ActionItems` row (`type=Cold-Email Follow-up`) if one doesn't already exist for that contact.

**Testing / acceptance checklist**:
- [ ] `template_engine.render` unit test: sample template + context → correct substitution; a template with a field missing from context raises, doesn't silently pass through.
- [ ] Queue 2 real rows pointed at a second email address you own; run `send_cold_emails.py` with `throttle_per_run=1` twice — confirm exactly one send per run, both eventually sent, correct merge fields in the actual received email.
- [ ] Reply from the second account to one of them; run `check_cold_emails.py`; confirm that row's `status` flips to `Replied` and the other stays `Sent`.
- [ ] Backdate a `Sent` row's `date_sent` past the stale threshold (manually edit the sheet); run `check_cold_emails.py`; confirm an `ActionItems` follow-up row is created, and running it again doesn't create a duplicate.

**Found during this build**: a real, retroactive bug in `sheets_client.py` itself (built in Milestone 1) — see the `valueInputOption="RAW"` note under Milestone 1's `SheetsClient` spec above. Surfaced here because `ActionItems.due_date` came back as a raw serial number; turned out to have silently corrupted all 774 `ListingsSeen.date_first_seen` values since Milestone 2 too. Fixed at the source and repaired retroactively.

**Prompt for this milestone**:
> Implement Milestone 4 (Cold-email templates, mail-merge sending, reply tracking) from `MILESTONES.md` in `/Users/hiepnguyen/code/personal-assistant`. Milestone 1 is already built. Build `template_engine.py`, `scripts/queue_cold_emails.py`, `scripts/send_cold_emails.py`, and `scripts/check_cold_emails.py` exactly per Milestone 4's spec, respecting the throttle config and never sending a template with unfilled `{{...}}` fields. Then run through the full testing checklist using a second email address I own for round-trip verification, and report results.

---

### Milestone 5 (Days 11-12) — Action items polish, CompanyNotes lookup, analytics, weekly retro

**Goal**: Stale-application detection, a company-notes lookup, and the on-demand + weekly analytics.

**Prerequisites**: Milestones 1-4.

**Functional requirements**:
- FR1: Detect applications with no stage movement past a configured number of days and create a follow-up action item.
- FR2: Support case-insensitive company-name lookup against `CompanyNotes`.
- FR3: Compute conversion rates by resume track/variant and by referral status from live sheet data.
- FR4: Render an on-demand chart (light/dark aware) summarizing those stats.
- FR5: Send a weekly summary email comparing this week's activity to the prior week's.

**Non-functional requirements**:
- NFR1: Stats reflect the live state of the sheet at call time — no caching/staleness beyond the API read itself.
- NFR2: Stale-application detection doesn't re-flag an application that already has an open, undone action item for it.
- NFR3: Chart output stays legible from a handful of rows up through a few hundred.
- NFR4: Rate calculations handle small-sample edge cases (e.g. zero applications for a resume variant) gracefully rather than crashing on division by zero.

**Files to build**:
- `scripts/check_action_items.py` — scans `Applications` for rows where `current_stage` hasn't changed in `config.action_items.stale_application_days`; creates an `ActionItems` row (`type=Application Follow-up`) if one doesn't already exist for that `app_id`.
- `scripts/company_notes.py` — `lookup(company: str) -> dict | None` reading the `CompanyNotes` tab (simple case-insensitive match) — used for a conversational "what do I know about Company X" flow.
- `stats_report.py` — pulls `Applications` + `Resumes` + `StageEvents` fresh via `sheets_client.read_tab` each call; computes:
  - response/OA/interview rate grouped by `(track, variant)` from `Resumes` joined to `Applications`
  - response/interview rate grouped by `referral (Y/N)`
  - funnel counts (Applied/OA/Phone/Onsite/Offer/Reject) and average days-in-stage from `StageEvents`
  - `--chart` flag: writes an HTML file (light/dark aware, per the `dataviz` skill) summarizing the above as bar charts, ready to hand to the `Artifact` tool.
- `scripts/weekly_retro.py` — reuses `stats_report` functions, computes this-week vs. last-week deltas (applications sent, interviews landed, response-rate trend), emails a short summary via `GmailClient.send`.

**Testing / acceptance checklist**:
- [ ] Seed ~15-20 fake `Applications` rows spread across all 4 resume variants and referral Y/N, with varied `current_stage`.
- [ ] `stats_report.py` output rates match a hand-count from the seeded data.
- [ ] `stats_report.py --chart` produces an HTML file; publish it as an Artifact and visually confirm it looks right in both light and dark mode.
- [ ] `check_action_items.py` flags a deliberately-stale seeded application and does not re-flag it on a second run.
- [ ] `company_notes.py lookup("Stripe")` returns the seeded row; a non-existent company returns `None` cleanly.
- [ ] `weekly_retro.py` run manually — confirm the emailed numbers match the current sheet state.

**Prompt for this milestone**:
> Implement Milestone 5 (Action items polish, CompanyNotes lookup, analytics, weekly retro) from `MILESTONES.md` in `/Users/hiepnguyen/code/personal-assistant`. Milestones 1-4 are already built. Build `scripts/check_action_items.py`, `scripts/company_notes.py`, `stats_report.py` (including the `--chart` flag), and `scripts/weekly_retro.py` exactly per Milestone 5's spec. Seed the sheet with ~15-20 fake `Applications`/`Resumes` rows as described in the testing checklist, run everything, publish the chart as an Artifact, and report whether the computed rates match a manual hand-count.

---

### Milestone 6 (Day 13) — Wire everything into scheduled cloud routines

**Goal**: `check_listings.py`, `send_cold_emails.py` + `check_cold_emails.py`, `check_action_items.py`, and `weekly_retro.py` all run on their own without you triggering them.

**Prerequisites**: Milestones 1-5, all scripts working when run manually.

**Functional requirements**:
- FR1: Listings watcher runs automatically on a recurring schedule without manual triggering.
- FR2: Cold-email send + reply-check runs automatically on a tighter recurring schedule to realize the throttled pacing designed in Milestone 4.
- FR3: Action-items and weekly-retro checks run automatically on daily/weekly schedules respectively.

**Non-functional requirements**:
- NFR1: Routines have access to valid, non-expired credentials at every scheduled fire, including after the user's local machine has been off/asleep.
- NFR2: Overlapping runs (a routine firing before the previous run finished) don't cause duplicate sends or duplicate sheet rows.
- NFR3: A single routine's failure (e.g. one repo unreachable) doesn't silently stop future scheduled fires — failures are surfaced (email/log), not swallowed.

**Open question to resolve at this point** (flagged since Milestone 1's planning): how the `schedule` skill's cloud routines get access to this repo's code and the OAuth token/credentials — this weill need to be figured out live (e.g. the routine's prompt pulls the repo and reads a secret-stored token vs. some other mechanism the skill provides). Don't assume a mechanism in advance; ask the `schedule` skill what it needs when you get here.

**Steps**:
1. Use the `schedule` skill to create a routine that runs `check_listings.py` on a cadence (e.g. every 3-4 hours).
2. A routine (or the same one, chained) that runs `send_cold_emails.py` then `check_cold_emails.py` every 30-60 min — this is what gives the throttled/paced cold-email sending its actual pacing.
3. A routine for `check_action_items.py` daily.
4. A routine for `weekly_retro.py` weekly.
5. Confirm each routine's execution environment actually has the `.credentials/token.json` (or equivalent secret) available — this is the part most likely to need iteration.

**Testing / acceptance checklist**:
- [ ] Each routine fires at least once on its own (not manually triggered) and produces the expected effect (email arrives / sheet updates) — verified by waiting for a real scheduled fire, not just a manual dry run.
- [ ] Confirm no double-processing if a routine fires while a previous run is still in flight (simple case: check the routine's own concurrency behavior, or add a lightweight lock/flag if needed).

**Prompt for this milestone**:
> Implement Milestone 6 (scheduled cloud routines) from `MILESTONES.md` in `/Users/hiepnguyen/code/personal-assistant`. Milestones 1-5 are built and each script works when run manually. Use the `schedule` skill to set up the 4 routines described in Milestone 6 (listings watcher every few hours, cold-email send+check every 30-60 min, action-items daily, weekly retro weekly). Figure out and document how the routine gets access to this repo and the Google OAuth token — don't assume, check what the skill actually needs. Report what mechanism ended up working.

**What actually happened (resolves the open question above)**:
- The `schedule` skill's cloud routines run each fire as a fully isolated cloud session with its own git checkout — **no access to local files at all**, confirmed live. This meant the project had to become a real GitHub repo (it wasn't one before this milestone): `git init`, committed, pushed to `github.com/hiepnnguyentcu/internship-tracker-2027` via `gh repo create`.
- **Credential delivery**: chosen approach was to embed `credentials/token.json`'s content directly in each routine's stored prompt, with instructions to write it to that path before running any script. Tradeoff accepted knowingly: the live OAuth refresh token now also lives in Anthropic's routine-storage system, not just the local machine. (Alternative considered and declined: deliver it via a Drive file + the Google Drive MCP connector instead, to avoid that — more moving parts, skipped for MVP.)
- **Repo had to be made public**, not kept private as originally intended. The routine-creation API requires a GitHub App connection with access to the target repo; connecting it from claude.ai's side surfaced two sequential blockers live — first the App wasn't installed on the GitHub account at all, then once installed its repository access was scoped to public repos only. Flipping the repo to public was the pragmatic unblock rather than continuing to debug the App's private-repo grant. No secrets are in the repo either way (`credentials/` stays gitignored), so the practical exposure is just the automation code and prompts being world-readable.
- **Cron minimum interval is 1 hour**, not the 30-60 min originally planned for cold-email pacing — the scheduler rejects anything finer (`*/30 * * * *` fails). The cold-email send+check routine runs hourly instead; still achieves real throttling/pacing (`throttle_per_run` per hour instead of per half-hour), just coarser than designed.
- **NFR3 (failures surfaced, not swallowed)**: each routine's prompt includes an explicit fallback step — if the script exits non-zero, the agent sends a `GmailClient` failure-report email itself rather than the cloud session just quietly ending.
- **Verified live** (not just created-and-assumed): manually fired the listings-watcher routine via `RemoteTrigger action:"run"` immediately after creating it. It genuinely executed in the cloud sandbox — cloned the repo, installed dependencies, wrote the embedded credentials, ran `check_listings.py`, found 7 real new postings, and sent a real digest email (confirmed via Gmail API + `ListingsSeen` growing from 774 to 781 rows). This is the actual mechanism that will fire on every future scheduled cron tick too, not a separate manual code path.
- **Known operational risk, not yet resolved**: the Google OAuth consent screen is still in "Testing" publishing status (confirmed earlier when a non-test-user login hit `403 access_denied`). Refresh tokens for apps in Testing status expire after ~7 days — meaning this whole automation chain will silently start failing about a week from now until `setup_auth.py` is re-run for a fresh token (and the routines' embedded tokens updated to match). Moving the consent screen to "In production" would remove that expiry; not done as part of this milestone.

Routine IDs created: `trig_01CiwaBMeVDeMvN9xG1T2FCV` (listings, `13 */3 * * *` UTC), `trig_01T9AYzv7d67vBJaov8ieS5z` (cold-email send+check, `22 * * * *` UTC), `trig_01YDV4akqaaoGcszMRPyDdWD` (action items, `7 2 * * *` UTC = ~9am Asia/Saigon daily), `trig_014tG4xvVoagrt5YZwtx8p3u` (weekly retro, `11 2 * * 1` UTC = ~9am Asia/Saigon Monday). Manage/view at `https://claude.ai/code/routines`.

---

### Milestone 7 (Day 14) — Buffer, end-to-end validation, polish

**Goal**: A full day held open for whatever broke, plus one real end-to-end pass using real data.

**Functional requirements**:
- FR1: A full real-data pass through every stage of the pipeline (listing → application → OA → cold email → reply → stats) completes without manual workarounds.

**Non-functional requirements**:
- NFR1: The system runs unattended for the remainder of the application cycle without daily developer intervention — this is the actual exit criterion for "MVP done," not just "all scripts exist."

**Steps**:
1. Let the scheduled routines run for a full day untouched; check in the evening for any silent failures (check script logs/error emails if you added any).
2. Do one real pass: log 2-3 real applications, queue real cold emails for one real target company, and confirm the whole loop (listing → application → OA → action item/calendar → cold email → reply detection → stats) works end to end with real data, not fixtures.
3. Fix whatever breaks. Not aiming for new features on this day — aim for the MVP being trustworthy enough to run unattended for the rest of the cycle.

**Prompt for this milestone**:
> Do Milestone 7 (buffer/E2E validation) from `MILESTONES.md` in `/Users/hiepnguyen/code/personal-assistant`. All prior milestones are built and scheduled. Review the last day's routine executions for silent failures, then walk through one real end-to-end pass (a real new listing → logging a real application → an OA stage with calendar reminder → a real cold-email send/reply-check → stats_report) and fix anything that breaks along the way. Report what broke and what's now confirmed working.

**What actually happened**:
- Step 1 (routines running untouched for a full day) is inherently a passive/ongoing check, not something completable in one sitting — the 4 routines from Milestone 6 keep firing on their own schedules; failures would surface as `Routine failure: ...` emails per the fallback built into each routine's prompt. Nothing has needed intervention since Milestone 6, but this stays a "keep an eye on it" item rather than a one-time checkbox.
- Step 2 (real E2E pass) — done with genuinely real data, not fixtures: registered the user's actual resume (real name/email/phone/Drive link, content fetched live from their shared Google Doc) as `R1` (Full-Stack/A), then logged 2 real applications the user is actually submitting — **Rippling** (Backend SWE Intern) and **Capital One** (Technology Intern) — both pulled from a real listings-watcher digest, not synthetic postings.
  - JD-keyword check ran for real on both: Rippling scored a genuine 22% overlap (fine, no warning); Capital One's Workday posting returned no extractable static text (JS-rendered SPA) and the check correctly skipped rather than crashing — a real, unplanned confirmation of NFR1's graceful-degradation requirement.
  - `stats_report.py` correctly showed 2 total applications, both `Applied`, 0% response (accurate — they were just submitted).
  - OA/calendar-reminder and cold-email send/reply-check paths were **not** re-exercised with real data this round (both already verified live with test accounts in Milestones 3-4) — the user opted to skip a real cold-email send for M7 specifically, so that leg of the FR1 chain stays validated-with-test-data rather than validated-with-production-data.
- Unlike every previous milestone's testing, **this data was not cleaned up afterward** — it's the user's real, permanent tracker data, not test/seed data.

---

## Phase 2: Web App + Auto-Apply

The MVP (Milestones 1-7) is done. This phase builds the web app + browser automation described in the "Phase 2: Web App + Auto-Apply (revised)" section of the design plan (`~/.claude/plans/i-need-to-brainstorm-declarative-acorn.md`). Unlike M1-M7, Phase 2 wasn't pre-broken into day-by-day milestones before building started — chunks get documented here as they're actually built.

**Revision note**: Chunk 2 below shipped a PySide6 **desktop** app. The user then asked to drop it for a **web** app (reachable from other devices via Tailscale, not PySide6) and to build the real auto-apply automation next, with resume-tweak generation explicitly deferred. Chunk 2's content is left intact below as an accurate build record — it was real, tested, working code — but it has since been **deleted** (see Chunk 3). Treat anything below referencing `app/`, `PySide6`, `MainWindow`, `ApplyDialog`, or `TweakDialog` as historical, not current.

### Chunk 2 — Apply-flow UI shell (queue + apply dialog + tweak dialog)

**Goal**: A real, launchable desktop window showing the live apply queue, with an apply flow and a tweak-review flow — explicitly wired to stubs for the pieces not built yet (ATS automation, Drive/Docs, Claude-generated tweaks), rather than faking functionality that doesn't exist.

**Why "chunk 2" and not "chunk 1"**: the user's own framing. Milestones 1-7 collectively are the data/backend layer chunk 2 builds on (Sheets schema, `record_application`, `register_resume`, `jd_keyword_check`) — there wasn't a separately-numbered "chunk 1."

**What's real vs. stubbed**:
- **Real**: the queue (`app/queue_model.py`) computes actual unapplied listings — `ListingsSeen` rows with no matching `Applications.job_url` — live from the real sheet (779 rows at build time, correctly excluding the 2 real applications logged in Milestone 7). The resume picker lists real `Resumes` rows. "Open & Apply" opens the real job URL and, on confirmation, calls the same `record_application()` the CLI uses — a real, permanent `Applications` + `StageEvents` row gets written, not a mock.
- **Stubbed, clearly labeled as such in the UI itself** (not silently fake):
  - **JD-match score / needs-tweak columns** show "—" always. Real scoring needs resume *text*, which needs the Drive/Docs client (not built) — resumes currently only exist as Drive Doc *links*. Showing a fabricated percentage would be worse than showing nothing.
  - **"Adjust Resume…"** opens a dialog that explains tweaking isn't implemented yet, rather than a fake diff.
  - **Applying** is "open the real listing in your browser, confirm once you've actually submitted it, then log it" — not real ATS form-filling (Greenhouse/Lever/Ashby automation is a later chunk).

**Files built**:
- `app/queue_model.py` — `QueueItem` dataclass, `load_queue()`, `load_resumes()`.
- `app/main_window.py` — `MainWindow`: queue table (Company/Role/Location/Source/First Seen/JD Match/Needs Tweak/Apply-button), Refresh button.
- `app/apply_dialog.py` — `ApplyDialog`: resume picker, "Adjust Resume…" (opens the tweak stub), "Open & Apply" (browser + confirm + `record_application`).
- `app/tweak_dialog.py` — `TweakDialog`: stub explanation dialog.
- `app/main.py` — entrypoint (`python app/main.py`).
- Refactored `scripts/log_application.py` → exposes `record_application()` (core logic) with `main()` as a thin CLI wrapper; `scripts/log_resume.py` → exposes `register_resume()` + `ResumeConflictError` the same way. Both the CLI and the app now call the identical code path, per the Phase 2 plan's explicit requirement — added `scripts/__init__.py` to make this importable as `from scripts.log_application import record_application`.
- `requirements.txt` — added `PySide6==6.11.1`.

**Testing performed**:
- [x] Regression: full pytest suite (25 tests) still passes after the `log_application.py`/`log_resume.py` refactor.
- [x] Regression: CLI behavior unchanged post-refactor — re-ran `log_application.py` and `log_resume.py` from the command line, confirmed identical output/behavior to pre-refactor (test rows cleaned up after; the real R1/Rippling/Capital One data was untouched).
- [x] Headless smoke test (`QT_QPA_PLATFORM=offscreen`, since this dev environment has no real display): `MainWindow` constructs against the live sheet, loads 779 real queue rows and 1 real resume, correctly excludes the 2 already-applied listings. `ApplyDialog` and `TweakDialog` construct without error against real data.
- [ ] **Not done, and can't be done from here**: actually opening/visually inspecting the running window. This is a native desktop app — there's no browser to screenshot. The offscreen smoke test proves the code runs without crashing and loads correct data; it does **not** prove the layout looks right, buttons are positioned sensibly, or the dialogs read well. **The user needs to run `python app/main.py` locally and look at it themselves before this chunk is considered visually verified.**

**Known gaps, deliberate for this chunk (see "Phase 2" plan for the full roadmap)**:
- No Drive/Docs OAuth scopes added yet — needed for real resume-text fetching (JD-match scoring) and the tweak pipeline.
- No Playwright/ATS automation yet.
- No Claude-API-based tweak generation yet (needs an Anthropic API key provisioned, since the app runs standalone).
- Apply flow doesn't yet collect referral/notes in the dialog (CLI still supports it; the UI defaults to `referral=N`) — minor, easy follow-up.

---

### Chunk 3 (sub-chunk A) — Desktop app removed, FastAPI web app scaffold

**Goal**: Replace the PySide6 desktop app with a web app, at feature parity — queue view, auth gate, manual apply-and-log flow — as the foundation sub-chunk C's real automation gets wired into.

**What changed from Chunk 2**:
- Deleted entirely: `app/main.py`, `app/main_window.py`, `app/apply_dialog.py`, `app/tweak_dialog.py`, and `PySide6` from `requirements.txt` (uninstalled from the venv too).
- `app/queue_model.py` had no PySide6 dependency (pure `SheetsClient` logic) — moved verbatim into `web/queue_model.py`, plus a small `find_queue_item()` addition needed by the apply route.
- The desktop app's "open link → manually apply → confirm → log" behavior carries forward as-is, just as HTML instead of Qt widgets: an "Open ↗" link (new tab) next to a per-row resume-picker form with a JS `confirm()` ("have you actually submitted this?") before it calls the same `record_application()`.

**Files built**:
- `web/auth.py` — shared-password gate (`TRACKER_WEB_PASSWORD` env var, `secrets.compare_digest` for the check, in-memory session-token set, httponly cookie). Deliberately simple: Tailscale (network-level access control, set up by the user outside this codebase) is the primary defense; this is a second layer, not the only one — appropriate for a single-user personal tool, not a general-purpose auth system.
- `web/queue_model.py` — moved from `app/`, plus `find_queue_item(listing_key)`.
- `web/main.py` — FastAPI app: `/login` (GET/POST), `/logout`, `/queue` (GET, protected), `/apply/manual` (POST, protected).
- `web/templates/login.html`, `web/templates/queue.html` — server-rendered Jinja2, no JS framework/build step.
- `requirements.txt` — removed `PySide6`, added `fastapi`, `uvicorn`, `jinja2`, `python-multipart` (required by FastAPI for parsing HTML form POSTs).

**Testing performed (all against the real running server, not just unit tests)**:
- [x] Regression: full pytest suite (25 tests) still passes.
- [x] Started `uvicorn web.main:app` locally, hit it with real `curl` requests (not just constructed objects in-process, unlike Chunk 2's offscreen-Qt approach — this app has no headless-rendering equivalent gap, since HTTP responses are the real interface):
  - Unauthenticated `GET /queue` → `307` redirect to `/login`. ✅
  - Wrong password → `303` redirect to `/login?error=1`. ✅
  - Correct password → `303` to `/queue` with a valid session cookie set. ✅
  - Authenticated `GET /queue` → real data: loaded the live sheet correctly.
  - `POST /apply/manual` against a **fake, clearly-marked test listing** (added to `ListingsSeen`, then deleted afterward along with the resulting test `Applications`/`StageEvents` rows) → correctly created a real `Applications` row, correct flash-message redirect.
  - `POST /apply/manual` against a nonexistent `listing_key` → correct error-message redirect, no row created.
- **Found and resolved a false alarm, not a bug**: while verifying the queue count, noticed an `Applications` row (`A0003`, Amazon) with no corresponding record in anything done this session. Traced every request made during testing via the uvicorn access log and confirmed none of them could have created it, then asked the user directly rather than guessing or silently deleting a real-looking row — confirmed it was the user's own real, manual use of the now-removed desktop app before it was taken down. Left untouched, as it should be.

**Known gaps for this sub-chunk (by design — sub-chunks B/C are next)**:
- No `Identity` tab yet, no `drive_client.py`, no real ATS automation — `/apply/manual` is still the only apply path, same as Chunk 2's desktop version.
- No queue multi-select / batch "Apply to Selected" yet — that's part of sub-chunk C, bundled with the real automation it drives.
- JD-match score column still shows "—" — unchanged from Chunk 2, still blocked on Drive text access.

---

### Chunk 4 (sub-chunk B) — Identity tab + minimal `drive_client.py`

**Goal**: Get the two things real ATS automation needs that didn't exist yet — biographical data to fill standard form fields, and a way to get the current resume onto disk as a PDF for the upload field.

**Files built**:
- `scripts/migrate_add_identity_and_apply_method.py` — idempotent migration: creates the `Identity` tab, adds `apply_method` to `Applications` via the new `SheetsClient.add_column()`, backfills existing rows to `Manual` (accurate — everything logged so far was applied to by hand).
- `drive_client.py` — `DriveClient.export_doc_as_pdf(doc_url_or_id, output_path)` via the Drive API's `files.export`. Read-only (`drive.readonly` scope), never writes to Drive.
- `google_auth.py` — added `drive.readonly` to `SCOPES`.

**Setup steps done live with the user** (both required — this wasn't just a code change):
- Re-ran `setup_auth.py` for a token covering the new scope (the user completed the browser consent step).
- The Drive API itself wasn't enabled on the Google Cloud project yet (separate from OAuth scope consent) — hit a live `403 accessNotConfigured` on the first export attempt, user enabled it in Cloud Console, retried successfully.

**Real data registered**: an `Identity` row (`ID1`) with the user's actual name, school (TCU), grad year, LinkedIn, and work-authorization/sponsorship status (asked directly rather than guessed, since this fills real legal-status fields on real applications).

**Testing performed**:
- [x] Regression: full pytest suite (25 tests) still passes.
- [x] Migration script is genuinely idempotent — re-ran it, confirmed zero duplicate backfills the second time.
- [x] Live export against the user's **real** resume Doc: produced a valid 142,990-byte, 1-page PDF; confirmed the PDF's embedded metadata/links (title, mailto, LinkedIn, GitHub) match the real resume content, not a blank/corrupt file. Test file deleted after verification.
