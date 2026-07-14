import sqlite3
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
DB_PATH = REPO_ROOT / "db" / "company_documents.db"

CATEGORIES = ("HR", "Finance", "Development")

# Standard document type tags (REF-Core.md Section 1)
DOC_TYPES = ("AGMT", "CONTRACT", "EST", "LOG", "CAD", "MEMO", "CORR", "REF", "OPS", "MISC")


def get_connection():
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    return conn


def init_db():
    conn = get_connection()
    conn.execute(
        f"""
        CREATE TABLE IF NOT EXISTS documents (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            category TEXT NOT NULL CHECK (category IN {CATEGORIES!r}),
            doc_type TEXT NOT NULL CHECK (doc_type IN {DOC_TYPES!r}),
            short_title TEXT NOT NULL,
            version INTEGER NOT NULL DEFAULT 1,
            filename TEXT NOT NULL,
            file_type TEXT NOT NULL CHECK (file_type IN ('docx', 'xlsx', 'pdf')),
            file_path TEXT NOT NULL,
            content BLOB NOT NULL,
            created_at TEXT NOT NULL DEFAULT (datetime('now')),
            updated_at TEXT NOT NULL DEFAULT (datetime('now')),
            UNIQUE (category, doc_type, short_title)
        )
        """
    )
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS document_archive (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            original_id INTEGER NOT NULL REFERENCES documents(id),
            category TEXT NOT NULL,
            doc_type TEXT NOT NULL,
            short_title TEXT NOT NULL,
            version INTEGER NOT NULL,
            filename TEXT NOT NULL,
            file_type TEXT NOT NULL,
            file_path TEXT NOT NULL,
            content BLOB NOT NULL,
            archived_at TEXT NOT NULL DEFAULT (datetime('now'))
        )
        """
    )
    conn.commit()
    conn.close()
