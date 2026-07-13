# Multi-Entity Document & Spreadsheet Database

A GitHub-repo-based document store for four business entities:

| Entity key   | Business                       | Project number prefix |
|--------------|--------------------------------|-----------------------|
| `stillwater` | Stillwater Custom Cabinetry    | `SW-`                 |
| `pcl`        | Premier Care Logistics (PCL)   | `PCL-`                |
| `riverwalk`  | Riverwalk                      | `RW-`                 |
| `vault`      | The Vault                      | `VLT-`                |

It is designed to be readable and writable by **two different clients**:

- **Claude Code** (terminal/web sessions with git + Python): full read/write via
  the scripts in `/scripts` and real SQL queries against `/db/index.db`.
- **Chat-Claude** (a normal claude.ai conversation): read-only by default, via
  plain HTTPS fetches of raw files — no SQL engine, no git credentials.

Because chat-Claude cannot open a SQLite file or run `query.py`, the repo keeps
**two synchronized layers**:

1. `/db/index.db` — SQLite, the **source of truth** for metadata and queries.
2. `/index/*.json` — flat JSON exports of the database, regenerated on **every**
   write so the two layers never drift apart. Never hand-edit these files;
   they are overwritten by `export.py`.

## Repo structure

```
/entities/{entity}/                                   entity roots (markers)
/files/{entity}/{project_number}/{filename}           native files, untouched (docx, xlsx, pdf, ...)
/extracted/{entity}/{project_number}/
    {filename}.md                                     text of each docx/pdf, as markdown
    {filename}__{sheet}.csv                           one csv per sheet of each xlsx
/inbox/{entity}/                                      drop zone for GitHub-website uploads (auto-ingested)
/db/index.db                                          SQLite index (source of truth)
/index/documents.json                                 full export of the documents table
/index/entities.json                                  entity + project rollup counts
/scripts/ingest.py                                    add/update a file (see below)
/scripts/query.py                                     CLI queries against SQLite
/scripts/export.py                                    regenerate /index/*.json (auto-run by ingest)
/scripts/extract.py                                   docx/pdf -> md, xlsx -> csv helpers
/scripts/dbschema.py                                  shared schema/connection; run standalone to init the db
/scripts/process_inbox.py                             files /inbox uploads (run by the auto-ingest Action)
/.github/workflows/ingest-inbox.yml                   auto-ingest Action for /inbox uploads
```

> Note: `/documents`, `/webapp`, and the other `/scripts/*.py` files not listed
> above are an earlier, unrelated prototype and are not part of this system.

## Entity / project numbering convention

Project numbers mirror the existing SharePoint numbering scheme — the number
used here must be **identical** to the project's number in SharePoint so the
two systems cross-reference cleanly. The pattern is
`{ENTITY PREFIX}-{YEAR}-{SEQ}`, e.g. `SW-2026-001`, `PCL-2026-014`,
`RW-2026-003`, `VLT-2026-007`. If a SharePoint project uses a different format,
use that exact string as the project number here rather than renumbering.

## Ingesting a file (Claude Code)

```bash
python3 scripts/ingest.py path/to/estimate.xlsx \
    --entity stillwater \
    --project SW-2026-001 \
    --project-name "Hendricks kitchen remodel" \
    --description "Materials and labor estimate" \
    --tags "estimate,budget"
```

This copies the file to `/files/`, extracts its text to `/extracted/`
(docx/pdf → markdown; xlsx → one csv per sheet), upserts the SQLite index,
regenerates `/index/*.json`, and commits + pushes with the message
`ingest: {entity}/{project_number}/{filename}`. Pass `--no-git` to skip the
commit/push (e.g. when batching several files into one commit).

Re-ingesting a file whose content hasn't changed (matched by sha256) is a
no-op on the file layer — only metadata (description/tags/modified date) is
updated. Re-ingesting changed content overwrites the stored file and its
extractions in place.

## Adding documents from the GitHub website (no tools needed)

Upload files straight from a browser — no git, no Python:

1. On github.com, open `inbox/` and click into the entity's folder.
2. **Add file → Upload files**, drag the document in, commit.
3. Name the file starting with the project number plus an underscore
   (e.g. `SW-2026-001_shop_notes.docx`), or upload into an existing
   `inbox/{entity}/{project_number}/` folder.

The auto-ingest Action (`.github/workflows/ingest-inbox.yml`) files it within
a couple of minutes: original to `/files/`, extracted text to `/extracted/`,
index updated, inbox copy removed. Files it can't place stay in the inbox and
get flagged in a GitHub issue titled "Inbox upload needs attention". See
`inbox/README.md` for details.

## Querying (Claude Code)

```bash
python3 scripts/query.py                          # everything
python3 scripts/query.py --entity pcl             # one entity
python3 scripts/query.py --project SW-2026-001    # one project
python3 scripts/query.py --tag budget             # by tag
python3 scripts/query.py --filename cost          # filename substring
python3 scripts/query.py --since 2026-07-01 --before 2026-08-01
python3 scripts/query.py --entity vault --json    # JSON output
```

Or query SQLite directly: `sqlite3 db/index.db "SELECT ..."`.

## How chat-Claude reads this repo (no SQL, no git)

Chat-Claude reads by fetching **raw GitHub URLs**. It cannot run `query.py` or
open `index.db` — only `/index/*.json` and `/extracted/*.md` / `*.csv` are
usable by it.

Start with the catalog:

```
https://raw.githubusercontent.com/djenkins1027/Claude-Testing/main/index/documents.json
https://raw.githubusercontent.com/djenkins1027/Claude-Testing/main/index/entities.json
```

Each entry in `documents.json` includes an `extracted_path`; fetch a specific
document's content from that path, e.g.:

```
https://raw.githubusercontent.com/djenkins1027/Claude-Testing/main/extracted/pcl/PCL-2026-014/PCL-2026-014_route_costs.xlsx__Q3%20Routes.csv
```

(URL-encode spaces in sheet names as `%20`. If content lives on a branch other
than `main`, substitute the branch name in the URL.)

**Size guardrail:** keep `/index/documents.json` reasonably sized so a single
fetch stays useful. If it grows past a few hundred entries, split it by entity
into `/index/{entity}.json` (a small change in `export.py`) and keep
`documents.json` as a slim manifest pointing at the per-entity files.

## Chat-Claude write access

Chat-Claude has **no persistent git credentials** — nothing carries over
between conversations, so by default it can only read. All routine writes go
through Claude Code / `ingest.py`, which holds persistent credentials and is
the default writer.

When you want chat-Claude to write directly in a given session, hand it a
**short-lived fine-grained personal access token** for that conversation only.

### Token setup (do this once, renew on expiry)

Create the token at GitHub → Settings → Developer settings →
Fine-grained tokens, scoped as narrowly as possible:

- **Repository access:** this repo only (not all repos).
- **Permissions:** `Contents: Read and write` only — no Actions, no Admin,
  no Workflows.
- **Expiration:** short (30–90 days), so it needs periodic renewal rather
  than sitting valid indefinitely.

### Steps for a session where chat-Claude writes

1. Generate/copy the token from GitHub (Settings → Developer settings →
   Fine-grained tokens), or reuse the current one if still valid.
2. Paste it into the chat-Claude conversation along with the request
   (e.g. "here's a token, please update X in the PCL folder").
3. Chat-Claude clones with the token, makes the edit, commits, and pushes —
   all within that session. Ask it to also re-run `export.py` (or update the
   JSON to match) if it touches anything the index tracks.
4. The token is never persisted by chat-Claude beyond that conversation.
   Treat each paste as a one-time-use credential; revoke/regenerate it if it
   is ever pasted somewhere it shouldn't be.

### Why this differs from the QuickBooks / Microsoft 365 connectors

Those connectors stay connected across chat-Claude sessions at the account
level. This repo intentionally does not — each write session needs a fresh
token paste. If GitHub is later added as an account-level connector, this
manual-token flow becomes unnecessary; worth revisiting after the initial
test period.

## Setup (fresh clone)

```bash
pip install python-docx openpyxl pypdf reportlab
python3 scripts/dbschema.py   # creates/initializes db/index.db if missing
```
