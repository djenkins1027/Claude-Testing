#!/usr/bin/env python3
import argparse
import json
import sys
from pathlib import Path

from db import CATEGORIES, REPO_ROOT, get_connection, init_db
from reader import READERS
from writer import build_docx, build_pdf, build_xlsx

DOCS_ROOT = REPO_ROOT / "documents"


def cmd_init(_args):
    init_db()
    for category in CATEGORIES:
        (DOCS_ROOT / category).mkdir(parents=True, exist_ok=True)
    print("Database and folder structure initialized.")


def _build_content(file_type: str, args) -> bytes:
    if file_type == "docx":
        return build_docx(args.text or "")
    if file_type == "xlsx":
        rows = json.loads(args.rows) if args.rows else [[]]
        return build_xlsx(rows)
    if file_type == "pdf":
        return build_pdf(args.text or "")
    raise ValueError(f"Unsupported file type: {file_type}")


def cmd_create(args):
    filename = f"{args.name}.{args.type}"
    content = _build_content(args.type, args)
    file_path = DOCS_ROOT / args.category / filename
    file_path.parent.mkdir(parents=True, exist_ok=True)
    file_path.write_bytes(content)

    conn = get_connection()
    conn.execute(
        """
        INSERT INTO documents (category, filename, file_type, file_path, content)
        VALUES (?, ?, ?, ?, ?)
        ON CONFLICT (category, filename) DO UPDATE SET
            content = excluded.content,
            file_path = excluded.file_path,
            updated_at = datetime('now')
        """,
        (args.category, filename, args.type, str(file_path.relative_to(REPO_ROOT)), content),
    )
    conn.commit()
    conn.close()
    print(f"Wrote {file_path.relative_to(REPO_ROOT)} and indexed it in the database.")


def cmd_list(args):
    conn = get_connection()
    query = "SELECT id, category, filename, file_type, file_path, created_at, updated_at FROM documents"
    params = ()
    if args.category:
        query += " WHERE category = ?"
        params = (args.category,)
    query += " ORDER BY category, filename"
    rows = conn.execute(query, params).fetchall()
    conn.close()
    if not rows:
        print("No documents found.")
        return
    for row in rows:
        print(f"[{row['id']}] {row['category']}/{row['filename']} "
              f"({row['file_type']}, updated {row['updated_at']})")


def _fetch_document(conn, args):
    if args.id is not None:
        return conn.execute("SELECT * FROM documents WHERE id = ?", (args.id,)).fetchone()
    return conn.execute(
        "SELECT * FROM documents WHERE category = ? AND filename = ?",
        (args.category, args.name),
    ).fetchone()


def cmd_read(args):
    conn = get_connection()
    row = _fetch_document(conn, args)
    conn.close()
    if row is None:
        print("Document not found.", file=sys.stderr)
        sys.exit(1)
    reader = READERS[row["file_type"]]
    result = reader(row["content"])
    if isinstance(result, list):
        for line in result:
            print(line)
    else:
        print(result)


def cmd_export(args):
    conn = get_connection()
    row = _fetch_document(conn, args)
    conn.close()
    if row is None:
        print("Document not found.", file=sys.stderr)
        sys.exit(1)
    out_path = Path(args.out)
    out_path.write_bytes(row["content"])
    print(f"Exported {row['category']}/{row['filename']} to {out_path}")


def build_parser():
    parser = argparse.ArgumentParser(description="Read/write documents in the company_documents.db database.")
    sub = parser.add_subparsers(dest="command", required=True)

    sub.add_parser("init", help="Create the database schema and folder structure").set_defaults(func=cmd_init)

    create_p = sub.add_parser("create", help="Create or update a document")
    create_p.add_argument("--category", choices=CATEGORIES, required=True)
    create_p.add_argument("--type", choices=("docx", "xlsx", "pdf"), required=True)
    create_p.add_argument("--name", required=True, help="Filename without extension")
    create_p.add_argument("--text", help="Text content for docx/pdf documents")
    create_p.add_argument("--rows", help="JSON list of rows (each a list of cell values) for xlsx documents")
    create_p.set_defaults(func=cmd_create)

    list_p = sub.add_parser("list", help="List indexed documents")
    list_p.add_argument("--category", choices=CATEGORIES)
    list_p.set_defaults(func=cmd_list)

    read_p = sub.add_parser("read", help="Print the text/rows extracted from a document")
    read_p.add_argument("--id", type=int)
    read_p.add_argument("--category", choices=CATEGORIES)
    read_p.add_argument("--name", help="Filename including extension, e.g. handbook.docx")
    read_p.set_defaults(func=cmd_read)

    export_p = sub.add_parser("export", help="Write a document's stored content back out to a file")
    export_p.add_argument("--id", type=int)
    export_p.add_argument("--category", choices=CATEGORIES)
    export_p.add_argument("--name", help="Filename including extension, e.g. handbook.docx")
    export_p.add_argument("--out", required=True, help="Destination path")
    export_p.set_defaults(func=cmd_export)

    return parser


def main():
    parser = build_parser()
    args = parser.parse_args()
    args.func(args)


if __name__ == "__main__":
    main()
