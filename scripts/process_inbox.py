#!/usr/bin/env python3
"""process_inbox.py - ingest files uploaded to /inbox via the GitHub website.

Run by the auto-ingest GitHub Action on every push that touches /inbox,
but also runnable locally. For each file under /inbox it determines the
entity and project, runs the normal ingest (copy to /files, extract,
index, regenerate /index/*.json), and removes the inbox copy. Files it
can't place are left in the inbox and reported.

Project number resolution, in order:
  1. inbox/{entity}/{project_number}/{filename}   -> from the folder
  2. inbox/{entity}/{PROJECT}_{anything}.docx     -> from the filename prefix
     (e.g. SW-2026-001_shop_notes.docx)

Problems are written to the file named by $PROBLEMS_FILE (if set) so the
workflow can open a GitHub issue.
"""

import os
import re
import sys
from pathlib import Path

from dbschema import ENTITIES, REPO_ROOT
from ingest import ingest

INBOX = REPO_ROOT / "inbox"
SKIP_NAMES = {".gitkeep", "README.md"}
PROJECT_PREFIX_RE = re.compile(r"^([A-Za-z0-9]+-\d{4}-\d+)(?=[-_ .])")


def resolve(rel: Path):
    """Return (entity, project_number, problem) for an inbox-relative path."""
    parts = rel.parts
    entity = parts[0].lower() if len(parts) > 1 else None
    if entity not in ENTITIES:
        return None, None, (
            f"`inbox/{rel}`: files must be uploaded inside one of the entity "
            f"folders ({', '.join(ENTITIES)})")
    if len(parts) >= 3:
        return entity, parts[1], None
    m = PROJECT_PREFIX_RE.match(rel.name)
    if not m:
        return None, None, (
            f"`inbox/{rel}`: couldn't determine the project number. Either "
            f"upload into `inbox/{entity}/{{project_number}}/` or start the "
            f"filename with the project number followed by an underscore "
            f"(e.g. `SW-2026-001_shop_notes.docx`). Rename or move the file "
            f"to retry.")
    return entity, m.group(1), None


def main() -> None:
    ingested, problems = [], []
    if INBOX.is_dir():
        for path in sorted(p for p in INBOX.rglob("*") if p.is_file()):
            if path.name in SKIP_NAMES:
                continue
            entity, project, problem = resolve(path.relative_to(INBOX))
            if problem:
                problems.append(problem)
                continue
            ingest(path, entity, project, use_git=False)
            path.unlink()
            ingested.append(f"{entity}/{project}/{path.name}")

    print(f"ingested {len(ingested)} file(s); {len(problems)} problem(s)")
    problems_file = os.environ.get("PROBLEMS_FILE")
    if problems_file and problems:
        Path(problems_file).write_text(
            "The auto-ingest workflow couldn't file these inbox uploads:\n\n"
            + "\n".join(f"- {p}" for p in problems) + "\n",
            encoding="utf-8")
    summary = os.environ.get("GITHUB_STEP_SUMMARY")
    if summary:
        with open(summary, "a", encoding="utf-8") as f:
            f.write("### Inbox auto-ingest\n\n")
            f.writelines(f"- ingested `{name}`\n" for name in ingested)
            f.writelines(f"- ⚠️ {p}\n" for p in problems)


if __name__ == "__main__":
    main()
