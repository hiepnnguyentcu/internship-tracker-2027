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
