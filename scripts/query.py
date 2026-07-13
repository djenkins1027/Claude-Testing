#!/usr/bin/env python3
"""query.py - query the SQLite document index from the command line.

    python3 scripts/query.py                          # everything
    python3 scripts/query.py --entity pcl             # one entity
    python3 scripts/query.py --project SW-2026-001    # one project
    python3 scripts/query.py --tag budget             # by tag
    python3 scripts/query.py --filename cost          # filename substring
    python3 scripts/query.py --type xlsx              # by file type
    python3 scripts/query.py --since 2026-07-01       # added on/after date
    python3 scripts/query.py --before 2026-08-01      # added before date
    python3 scripts/query.py --entity vault --json    # JSON output

Filters combine with AND. Dates are ISO (YYYY-MM-DD).
"""

import argparse
import json

from dbschema import ENTITIES, connect


def build_query(args):
    sql = """SELECT e.name AS entity, p.project_number, p.project_name,
                    d.filename, d.file_type, d.file_path, d.extracted_path,
                    d.description, d.tags, d.added_date, d.modified_date
             FROM documents d
             JOIN projects p ON p.id = d.project_id
             JOIN entities e ON e.id = p.entity_id
             WHERE 1=1"""
    params = []
    if args.entity:
        sql += " AND e.name = ?"
        params.append(args.entity)
    if args.project:
        sql += " AND p.project_number = ?"
        params.append(args.project)
    if args.tag:
        sql += " AND (',' || REPLACE(IFNULL(d.tags,''), ' ', '') || ',') LIKE ?"
        params.append(f"%,{args.tag.strip()},%")
    if args.filename:
        sql += " AND d.filename LIKE ?"
        params.append(f"%{args.filename}%")
    if args.type:
        sql += " AND d.file_type = ?"
        params.append(args.type)
    if args.since:
        sql += " AND d.added_date >= ?"
        params.append(args.since)
    if args.before:
        sql += " AND d.added_date < ?"
        params.append(args.before)
    sql += " ORDER BY e.name, p.project_number, d.filename"
    return sql, params


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--entity", choices=ENTITIES)
    ap.add_argument("--project", help="exact project number")
    ap.add_argument("--tag")
    ap.add_argument("--filename", help="filename substring")
    ap.add_argument("--type", choices=["docx", "xlsx", "pdf", "other"])
    ap.add_argument("--since", help="added on/after this date (YYYY-MM-DD)")
    ap.add_argument("--before", help="added before this date (YYYY-MM-DD)")
    ap.add_argument("--json", action="store_true", help="output JSON")
    args = ap.parse_args()

    conn = connect()
    sql, params = build_query(args)
    rows = [dict(r) for r in conn.execute(sql, params)]
    conn.close()

    if args.json:
        print(json.dumps(rows, indent=2))
        return
    if not rows:
        print("no documents match")
        return
    header = ["entity", "project", "filename", "type", "tags", "added"]
    table = [[r["entity"], r["project_number"], r["filename"],
              r["file_type"] or "", r["tags"] or "",
              (r["added_date"] or "")[:10]] for r in rows]
    widths = [max(len(str(row[i])) for row in [header] + table)
              for i in range(len(header))]
    for row in [header, ["-" * w for w in widths]] + table:
        print("  ".join(str(v).ljust(w) for v, w in zip(row, widths)))
    print(f"\n{len(rows)} document(s)")


if __name__ == "__main__":
    main()
