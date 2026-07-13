import csv
import io
import os
import sys
from pathlib import Path

from flask import Flask, redirect, render_template, request, send_file, url_for
from werkzeug.security import check_password_hash, generate_password_hash

SCRIPTS_DIR = Path(__file__).resolve().parent.parent / "scripts"
sys.path.insert(0, str(SCRIPTS_DIR))

from db import CATEGORIES, REPO_ROOT, get_connection, init_db  # noqa: E402
from reader import read_docx, read_xlsx  # noqa: E402
from writer import build_docx, build_pdf, build_xlsx  # noqa: E402

DOCS_ROOT = REPO_ROOT / "documents"

app = Flask(__name__)
app.secret_key = os.environ.get("FLASK_SECRET_KEY", "dev-only-change-me")

APP_PASSWORD_HASH = generate_password_hash(os.environ.get("APP_PASSWORD", "changeme"))


@app.before_request
def require_auth():
    auth = request.authorization
    if not auth or not check_password_hash(APP_PASSWORD_HASH, auth.password):
        return app.response_class(
            status=401,
            headers={"WWW-Authenticate": 'Basic realm="Documents"'},
        )


def rows_to_csv(rows: list[list]) -> str:
    buffer = io.StringIO()
    csv.writer(buffer).writerows(rows)
    return buffer.getvalue()


def csv_to_rows(text: str) -> list[list]:
    return [row for row in csv.reader(io.StringIO(text)) if row]


@app.route("/")
def index():
    conn = get_connection()
    counts = conn.execute(
        "SELECT category, COUNT(*) AS n FROM documents GROUP BY category"
    ).fetchall()
    conn.close()
    counts_by_category = {row["category"]: row["n"] for row in counts}
    return render_template("index.html", categories=CATEGORIES, counts=counts_by_category)


@app.route("/category/<category>")
def category_view(category):
    if category not in CATEGORIES:
        return "Unknown category", 404
    conn = get_connection()
    docs = conn.execute(
        "SELECT id, filename, file_type, updated_at FROM documents WHERE category = ? ORDER BY filename",
        (category,),
    ).fetchall()
    conn.close()
    return render_template("category.html", category=category, docs=docs)


@app.route("/doc/<int:doc_id>/edit", methods=["GET", "POST"])
def edit_doc(doc_id):
    conn = get_connection()
    row = conn.execute("SELECT * FROM documents WHERE id = ?", (doc_id,)).fetchone()

    if row is None:
        conn.close()
        return "Document not found", 404

    if request.method == "POST":
        content_text = request.form["content"]
        if row["file_type"] == "docx":
            content = build_docx(content_text)
        elif row["file_type"] == "xlsx":
            content = build_xlsx(csv_to_rows(content_text))
        elif row["file_type"] == "pdf":
            content = build_pdf(content_text)

        file_path = REPO_ROOT / row["file_path"]
        file_path.write_bytes(content)

        conn.execute(
            "UPDATE documents SET content = ?, updated_at = datetime('now') WHERE id = ?",
            (content, doc_id),
        )
        conn.commit()
        conn.close()
        return redirect(url_for("category_view", category=row["category"]))

    if row["file_type"] == "docx":
        content_text = read_docx(row["content"])
    elif row["file_type"] == "xlsx":
        content_text = rows_to_csv(read_xlsx(row["content"]))
    else:
        content_text = ""  # PDFs are regenerated from scratch; start blank if no source text is tracked

    conn.close()
    return render_template("edit.html", doc=row, content_text=content_text)


@app.route("/doc/<int:doc_id>/download")
def download_doc(doc_id):
    conn = get_connection()
    row = conn.execute("SELECT * FROM documents WHERE id = ?", (doc_id,)).fetchone()
    conn.close()
    if row is None:
        return "Document not found", 404
    return send_file(
        io.BytesIO(row["content"]),
        as_attachment=True,
        download_name=row["filename"],
    )


@app.route("/new", methods=["GET", "POST"])
def new_doc():
    if request.method == "POST":
        category = request.form["category"]
        file_type = request.form["file_type"]
        name = request.form["name"]
        content_text = request.form["content"]

        if file_type == "docx":
            content = build_docx(content_text)
        elif file_type == "xlsx":
            content = build_xlsx(csv_to_rows(content_text))
        else:
            content = build_pdf(content_text)

        filename = f"{name}.{file_type}"
        file_path = DOCS_ROOT / category / filename
        file_path.parent.mkdir(parents=True, exist_ok=True)
        file_path.write_bytes(content)

        conn = get_connection()
        conn.execute(
            """
            INSERT INTO documents (category, filename, file_type, file_path, content)
            VALUES (?, ?, ?, ?, ?)
            ON CONFLICT (category, filename) DO UPDATE SET
                content = excluded.content,
                updated_at = datetime('now')
            """,
            (category, filename, file_type, str(file_path.relative_to(REPO_ROOT)), content),
        )
        conn.commit()
        conn.close()
        return redirect(url_for("category_view", category=category))

    return render_template("new.html", categories=CATEGORIES)


if __name__ == "__main__":
    init_db()
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT", 5000)), debug=False)
