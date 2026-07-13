#!/usr/bin/env python3
"""dbschema.py - shared SQLite connection/schema for the document database.

Importing this module and calling connect() guarantees /db/index.db exists
with the canonical schema. Runnable standalone to (re)initialize the db:

    python3 scripts/dbschema.py
"""

import sqlite3
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
DB_PATH = REPO_ROOT / "db" / "index.db"

ENTITIES = ["stillwater", "pcl", "riverwalk", "vault"]

SCHEMA = """
CREATE TABLE IF NOT EXISTS entities (
  id INTEGER PRIMARY KEY,
  name TEXT UNIQUE NOT NULL          -- stillwater | pcl | riverwalk | vault
);

CREATE TABLE IF NOT EXISTS projects (
  id INTEGER PRIMARY KEY,
  entity_id INTEGER REFERENCES entities(id),
  project_number TEXT NOT NULL,      -- matches the existing SharePoint numbering scheme
  project_name TEXT,
  UNIQUE(entity_id, project_number)
);

CREATE TABLE IF NOT EXISTS documents (
  id INTEGER PRIMARY KEY,
  project_id INTEGER REFERENCES projects(id),
  filename TEXT NOT NULL,
  file_type TEXT,                    -- docx | xlsx | pdf | other
  file_path TEXT NOT NULL,           -- path under /files/
  extracted_path TEXT,               -- path under /extracted/ (nullable)
  description TEXT,
  tags TEXT,                         -- comma-separated
  added_date TEXT,
  modified_date TEXT,
  sha256 TEXT                        -- for change detection on re-ingest
);

CREATE UNIQUE INDEX IF NOT EXISTS idx_documents_project_filename
  ON documents(project_id, filename);

CREATE TABLE IF NOT EXISTS tags (
  id INTEGER PRIMARY KEY,
  name TEXT UNIQUE NOT NULL
);
"""


def connect() -> sqlite3.Connection:
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    conn.executescript(SCHEMA)
    for name in ENTITIES:
        conn.execute("INSERT OR IGNORE INTO entities (name) VALUES (?)", (name,))
    conn.commit()
    return conn


if __name__ == "__main__":
    connect().close()
    print(f"initialized {DB_PATH}")
