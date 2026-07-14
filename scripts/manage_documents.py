#!/usr/bin/env python3
import argparse
import json
import sys
from pathlib import Path

from db import CATEGORIES, DOC_TYPES, get_connection, init_db
from reader import READERS
from versioning import DOCS_ROOT, save_new_version


def cmd_init(_args):
    init_db()
    for category in CATEGORIES:
        (DOCS_ROOT / category).mkdir(parents=True, exist_ok=True)
    print("Database and folder structure initialized.")


def cmd_create(args):
    if args.type == "xlsx":
        raw_content = json.loads(args.rows) if args.rows else [[]]
    else:
        raw_content = args.text or ""

    row = save_new_version(args.category, args.doc_type, args.short_title, args.type, raw_content)
    print(f"Wrote {row['file_path']} (v{row['version']}) and indexed it in the database.")


def cmd_list(args):
    conn = get_connection()
    query = "SELECT id, category, doc_type, short_title, version, filename, file_type, updated_at FROM documents"
    params = ()
    if args.category:
        query += " WHERE category = ?"
        params = (args.category,)
    query += " ORDER BY category, doc_type, short_title"
    rows = conn.execute(query, params).fetchall()
    conn.close()
    if not rows:
        print("No documents found.")
        return
    for row in rows:
        print(f"[{row['id']}] {row['category']}/{row['filename']} "
              f"({row['doc_type']}, v{row['version']}, updated {row['updated_at']})")


def cmd_versions(args):
    conn = get_connection()
    current = conn.execute("SELECT * FROM documents WHERE id = ?", (args.id,)).fetchone()
    if current is None:
        print("Document not found.", file=sys.stderr)
        sys.exit(1)
    archived = conn.execute(
        "SELECT * FROM document_archive WHERE original_id = ? ORDER BY version",
        (args.id,),
    ).fetchall()
    conn.close()
    for row in archived:
        print(f"v{row['version']} (archived {row['archived_at']}) — {row['filename']}")
    print(f"v{current['version']} (current) — {current['filename']}")


def cmd_read(args):
    conn = get_connection()
    row = conn.execute("SELECT * FROM documents WHERE id = ?", (args.id,)).fetchone()
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
    row = conn.execute("SELECT * FROM documents WHERE id = ?", (args.id,)).fetchone()
    conn.close()
    if row is None:
        print("Document not found.", file=sys.stderr)
        sys.exit(1)
    out_path = Path(args.out)
    out_path.write_bytes(row["content"])
    print(f"Exported {row['category']}/{row['filename']} to {out_path}")


def build_parser():
    parser = argparse.ArgumentParser(description="Read/write versioned documents in the company_documents.db database.")
    sub = parser.add_subparsers(dest="command", required=True)

    sub.add_parser("init", help="Create the database schema and folder structure").set_defaults(func=cmd_init)

    create_p = sub.add_parser("create", help="Create a document, or save a new version if one already exists")
    create_p.add_argument("--category", choices=CATEGORIES, required=True)
    create_p.add_argument("--doc-type", choices=DOC_TYPES, required=True)
    create_p.add_argument("--short-title", required=True, help="Human-readable title, e.g. 'Employee Handbook'")
    create_p.add_argument("--type", choices=("docx", "xlsx", "pdf"), required=True)
    create_p.add_argument("--text", help="Body text for docx/pdf documents")
    create_p.add_argument("--rows", help="JSON list of rows (each a list of cell values) for xlsx documents")
    create_p.set_defaults(func=cmd_create)

    list_p = sub.add_parser("list", help="List current documents")
    list_p.add_argument("--category", choices=CATEGORIES)
    list_p.set_defaults(func=cmd_list)

    versions_p = sub.add_parser("versions", help="Show version history for a document")
    versions_p.add_argument("--id", type=int, required=True)
    versions_p.set_defaults(func=cmd_versions)

    read_p = sub.add_parser("read", help="Print the text/rows extracted from the current version of a document")
    read_p.add_argument("--id", type=int, required=True)
    read_p.set_defaults(func=cmd_read)

    export_p = sub.add_parser("export", help="Write a document's stored content back out to a file")
    export_p.add_argument("--id", type=int, required=True)
    export_p.add_argument("--out", required=True, help="Destination path")
    export_p.set_defaults(func=cmd_export)

    return parser


def main():
    parser = build_parser()
    args = parser.parse_args()
    args.func(args)


if __name__ == "__main__":
    main()
