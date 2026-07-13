#!/usr/bin/env python3
"""ingest.py - add or update a file in the document database.

Copies the file into /files/{entity}/{project_number}/, extracts text
(docx/pdf -> markdown, xlsx -> per-sheet csv) into /extracted/, upserts
the SQLite index, regenerates /index/*.json, and commits + pushes.

    python3 scripts/ingest.py path/to/file.xlsx \
        --entity pcl --project PCL-2026-001 \
        --project-name "Fleet expansion" \
        --description "Q3 route cost model" \
        --tags "budget,fleet" \
        [--no-git]
"""

import argparse
import hashlib
import shutil
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

import extract
from dbschema import ENTITIES, REPO_ROOT, connect
from export import export_all

FILE_TYPES = {".docx": "docx", ".xlsx": "xlsx", ".pdf": "pdf"}


def sha256_of(path: Path) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(1 << 16), b""):
            h.update(chunk)
    return h.hexdigest()


def git_commit_and_push(paths: list, message: str) -> None:
    subprocess.run(["git", "add", "--"] + [str(p) for p in paths],
                   cwd=REPO_ROOT, check=True)
    staged = subprocess.run(["git", "diff", "--cached", "--quiet"], cwd=REPO_ROOT)
    if staged.returncode == 0:
        print("git: nothing to commit")
        return
    subprocess.run(["git", "commit", "-m", message], cwd=REPO_ROOT, check=True)
    branch = subprocess.run(["git", "rev-parse", "--abbrev-ref", "HEAD"],
                            cwd=REPO_ROOT, check=True,
                            capture_output=True, text=True).stdout.strip()
    subprocess.run(["git", "push", "-u", "origin", branch],
                   cwd=REPO_ROOT, check=True)


def ingest(src: Path, entity: str, project_number: str,
           project_name: str = None, description: str = None,
           tags: str = None, use_git: bool = True) -> dict:
    if not src.is_file():
        sys.exit(f"error: no such file: {src}")
    if entity not in ENTITIES:
        sys.exit(f"error: unknown entity {entity!r} (choose from {', '.join(ENTITIES)})")

    dest_dir = REPO_ROOT / "files" / entity / project_number
    dest_dir.mkdir(parents=True, exist_ok=True)
    dest = dest_dir / src.name
    digest = sha256_of(src)
    now = datetime.now(timezone.utc).isoformat(timespec="seconds")

    conn = connect()
    entity_id = conn.execute("SELECT id FROM entities WHERE name = ?",
                             (entity,)).fetchone()["id"]
    conn.execute("""INSERT INTO projects (entity_id, project_number, project_name)
                    VALUES (?, ?, ?)
                    ON CONFLICT(entity_id, project_number) DO UPDATE SET
                      project_name = COALESCE(excluded.project_name, project_name)""",
                 (entity_id, project_number, project_name))
    project_id = conn.execute(
        "SELECT id FROM projects WHERE entity_id = ? AND project_number = ?",
        (entity_id, project_number)).fetchone()["id"]

    existing = conn.execute(
        "SELECT * FROM documents WHERE project_id = ? AND filename = ?",
        (project_id, src.name)).fetchone()
    unchanged = (existing is not None and existing["sha256"] == digest
                 and dest.is_file())

    changed_paths = []
    if unchanged:
        print(f"no content change ({src.name} sha256 matches); "
              "updating metadata only")
        extracted_rel = existing["extracted_path"]
    else:
        if src.resolve() != dest.resolve():
            shutil.copy2(src, dest)
        changed_paths.append(dest)
        extracted_dir = REPO_ROOT / "extracted" / entity / project_number
        extracted_files = extract.extract_to_dir(dest, extracted_dir)
        changed_paths.extend(extracted_files)
        extracted_rel = (str(extracted_files[0].relative_to(REPO_ROOT))
                         if extracted_files else None)

    file_type = FILE_TYPES.get(src.suffix.lower(), "other")
    file_rel = str(dest.relative_to(REPO_ROOT))
    if existing:
        conn.execute("""UPDATE documents SET
                          file_type = ?, file_path = ?, extracted_path = ?,
                          description = COALESCE(?, description),
                          tags = COALESCE(?, tags),
                          modified_date = ?, sha256 = ?
                        WHERE id = ?""",
                     (file_type, file_rel, extracted_rel, description, tags,
                      now, digest, existing["id"]))
    else:
        conn.execute("""INSERT INTO documents
                          (project_id, filename, file_type, file_path,
                           extracted_path, description, tags,
                           added_date, modified_date, sha256)
                        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                     (project_id, src.name, file_type, file_rel, extracted_rel,
                      description, tags, now, now, digest))
    for tag in (tags or "").split(","):
        tag = tag.strip()
        if tag:
            conn.execute("INSERT OR IGNORE INTO tags (name) VALUES (?)", (tag,))
    conn.commit()

    export_all(conn)
    conn.close()

    changed_paths += [REPO_ROOT / "db" / "index.db",
                      REPO_ROOT / "index" / "documents.json",
                      REPO_ROOT / "index" / "entities.json"]
    if use_git:
        git_commit_and_push(changed_paths,
                            f"ingest: {entity}/{project_number}/{src.name}")
    print(f"ingested {entity}/{project_number}/{src.name}"
          + (f" (extracted: {extracted_rel})" if extracted_rel else ""))
    return {"entity": entity, "project_number": project_number,
            "filename": src.name, "sha256": digest}


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("file", type=Path, help="path to the file to ingest")
    ap.add_argument("--entity", required=True, choices=ENTITIES)
    ap.add_argument("--project", required=True, dest="project_number",
                    help="project number (matches the SharePoint scheme)")
    ap.add_argument("--project-name")
    ap.add_argument("--description")
    ap.add_argument("--tags", help="comma-separated tags")
    ap.add_argument("--no-git", action="store_true",
                    help="skip the automatic git commit + push")
    args = ap.parse_args()
    ingest(args.file, args.entity, args.project_number,
           project_name=args.project_name, description=args.description,
           tags=args.tags, use_git=not args.no_git)


if __name__ == "__main__":
    main()
