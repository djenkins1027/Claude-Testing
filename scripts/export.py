#!/usr/bin/env python3
"""export.py - regenerate /index/*.json from SQLite.

Called automatically by ingest.py after every write; also runnable
standalone if the flat layer ever needs to be rebuilt:

    python3 scripts/export.py
"""

import json
from datetime import datetime, timezone

from dbschema import REPO_ROOT, connect

INDEX_DIR = REPO_ROOT / "index"


def export_all(conn=None) -> list:
    own_conn = conn is None
    if own_conn:
        conn = connect()
    INDEX_DIR.mkdir(parents=True, exist_ok=True)
    generated_at = datetime.now(timezone.utc).isoformat(timespec="seconds")

    docs = [dict(r) for r in conn.execute("""
        SELECT d.id, e.name AS entity, p.project_number, p.project_name,
               d.filename, d.file_type, d.file_path, d.extracted_path,
               d.description, d.tags, d.added_date, d.modified_date, d.sha256
        FROM documents d
        JOIN projects p ON p.id = d.project_id
        JOIN entities e ON e.id = p.entity_id
        ORDER BY e.name, p.project_number, d.filename
    """)]
    (INDEX_DIR / "documents.json").write_text(
        json.dumps({"generated_at": generated_at,
                    "document_count": len(docs),
                    "documents": docs}, indent=2) + "\n",
        encoding="utf-8")

    entities = [dict(r) for r in conn.execute("""
        SELECT e.name AS entity,
               COUNT(DISTINCT p.id) AS project_count,
               COUNT(d.id) AS document_count
        FROM entities e
        LEFT JOIN projects p ON p.entity_id = e.id
        LEFT JOIN documents d ON d.project_id = p.id
        GROUP BY e.id ORDER BY e.name
    """)]
    for ent in entities:
        ent["projects"] = [dict(r) for r in conn.execute("""
            SELECT p.project_number, p.project_name,
                   COUNT(d.id) AS document_count
            FROM projects p
            JOIN entities e ON e.id = p.entity_id
            LEFT JOIN documents d ON d.project_id = p.id
            WHERE e.name = ?
            GROUP BY p.id ORDER BY p.project_number
        """, (ent["entity"],))]
    (INDEX_DIR / "entities.json").write_text(
        json.dumps({"generated_at": generated_at,
                    "entities": entities}, indent=2) + "\n",
        encoding="utf-8")

    if own_conn:
        conn.close()
    return docs


if __name__ == "__main__":
    docs = export_all()
    print(f"wrote {INDEX_DIR / 'documents.json'} ({len(docs)} documents)")
    print(f"wrote {INDEX_DIR / 'entities.json'}")
