import sqlite3
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
DB_PATH = REPO_ROOT / "db" / "company_documents.db"

CATEGORIES = ("HR", "Finance", "Development")


def get_connection():
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def init_db():
    conn = get_connection()
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS documents (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            category TEXT NOT NULL CHECK (category IN ('HR', 'Finance', 'Development')),
            filename TEXT NOT NULL,
            file_type TEXT NOT NULL CHECK (file_type IN ('docx', 'xlsx', 'pdf')),
            file_path TEXT NOT NULL,
            content BLOB NOT NULL,
            created_at TEXT NOT NULL DEFAULT (datetime('now')),
            updated_at TEXT NOT NULL DEFAULT (datetime('now')),
            UNIQUE (category, filename)
        )
        """
    )
    conn.commit()
    conn.close()
