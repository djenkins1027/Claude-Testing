import re
from datetime import date

from db import REPO_ROOT, get_connection
from writer import build_docx, build_pdf, build_xlsx

DOCS_ROOT = REPO_ROOT / "documents"

# Characters disallowed in Windows/SharePoint file names, per REF-Core.md Section 1.
_UNSAFE_CHARS = re.compile(r'[<>:"/\\|?*]')


def slugify(short_title: str) -> str:
    cleaned = _UNSAFE_CHARS.sub("", short_title).strip()
    return re.sub(r"\s+", "-", cleaned)


def build_filename(category: str, doc_type: str, short_title: str, version: int, file_type: str) -> str:
    slug = slugify(short_title)
    today = date.today().isoformat()
    return f"{today}_{category}_{doc_type}_{slug}_v{version}.{file_type}"


def save_new_version(category: str, doc_type: str, short_title: str, file_type: str, raw_content) -> dict:
    """Build and write a new version of a document, archiving the prior version if one exists.

    raw_content is a str (docx/pdf body text) or a list of row lists (xlsx).
    """
    conn = get_connection()
    existing = conn.execute(
        "SELECT * FROM documents WHERE category = ? AND doc_type = ? AND short_title = ?",
        (category, doc_type, short_title),
    ).fetchone()

    version = 1
    if existing is not None:
        conn.execute(
            """
            INSERT INTO document_archive
                (original_id, category, doc_type, short_title, version, filename, file_type, file_path, content)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                existing["id"], existing["category"], existing["doc_type"], existing["short_title"],
                existing["version"], existing["filename"], existing["file_type"], existing["file_path"],
                existing["content"],
            ),
        )
        old_path = REPO_ROOT / existing["file_path"]
        archive_dir = DOCS_ROOT / category / "archive"
        archive_dir.mkdir(parents=True, exist_ok=True)
        if old_path.exists():
            old_path.rename(archive_dir / old_path.name)
        version = existing["version"] + 1

    footer_stamp = f"{date.today().isoformat()} | {doc_type} | v{version}"
    if file_type == "docx":
        content = build_docx(raw_content, footer_stamp=footer_stamp)
    elif file_type == "xlsx":
        content = build_xlsx(raw_content, footer_stamp=footer_stamp)
    elif file_type == "pdf":
        content = build_pdf(raw_content, footer_stamp=footer_stamp)
    else:
        raise ValueError(f"Unsupported file type: {file_type}")

    filename = build_filename(category, doc_type, short_title, version, file_type)
    file_path = DOCS_ROOT / category / filename
    file_path.parent.mkdir(parents=True, exist_ok=True)
    file_path.write_bytes(content)
    relative_path = str(file_path.relative_to(REPO_ROOT))

    if existing is not None:
        conn.execute(
            """
            UPDATE documents
            SET version = ?, filename = ?, file_type = ?, file_path = ?, content = ?, updated_at = datetime('now')
            WHERE id = ?
            """,
            (version, filename, file_type, relative_path, content, existing["id"]),
        )
        doc_id = existing["id"]
    else:
        cursor = conn.execute(
            """
            INSERT INTO documents (category, doc_type, short_title, version, filename, file_type, file_path, content)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (category, doc_type, short_title, version, filename, file_type, relative_path, content),
        )
        doc_id = cursor.lastrowid

    conn.commit()
    row = conn.execute("SELECT * FROM documents WHERE id = ?", (doc_id,)).fetchone()
    conn.close()
    return dict(row)
