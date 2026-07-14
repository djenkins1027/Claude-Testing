import csv
import io
import os
import sys
from pathlib import Path

from flask import Flask, redirect, render_template, request, send_file, url_for
from werkzeug.security import check_password_hash, generate_password_hash

SCRIPTS_DIR = Path(__file__).resolve().parent.parent / "scripts"
sys.path.insert(0, str(SCRIPTS_DIR))

from db import CATEGORIES, DOC_TYPES, REPO_ROOT, get_connection, init_db  # noqa: E402
from reader import read_docx, read_xlsx  # noqa: E402
from versioning import save_new_version  # noqa: E402

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
        "SELECT id, doc_type, short_title, version, filename, file_type, updated_at "
        "FROM documents WHERE category = ? ORDER BY doc_type, short_title",
        (category,),
    ).fetchall()
    conn.close()
    return render_template("category.html", category=category, docs=docs)


@app.route("/doc/<int:doc_id>/edit", methods=["GET", "POST"])
def edit_doc(doc_id):
    conn = get_connection()
    row = conn.execute("SELECT * FROM documents WHERE id = ?", (doc_id,)).fetchone()
    conn.close()

    if row is None:
        return "Document not found", 404

    if request.method == "POST":
        content_text = request.form["content"]
        raw_content = csv_to_rows(content_text) if row["file_type"] == "xlsx" else content_text
        save_new_version(row["category"], row["doc_type"], row["short_title"], row["file_type"], raw_content)
        return redirect(url_for("category_view", category=row["category"]))

    if row["file_type"] == "docx":
        content_text = read_docx(row["content"])
    elif row["file_type"] == "xlsx":
        content_text = rows_to_csv(read_xlsx(row["content"]))
    else:
        content_text = ""  # PDFs are regenerated from scratch; start blank if no source text is tracked

    return render_template("edit.html", doc=row, content_text=content_text)


@app.route("/doc/<int:doc_id>/versions")
def doc_versions(doc_id):
    conn = get_connection()
    current = conn.execute("SELECT * FROM documents WHERE id = ?", (doc_id,)).fetchone()
    if current is None:
        conn.close()
        return "Document not found", 404
    archived = conn.execute(
        "SELECT * FROM document_archive WHERE original_id = ? ORDER BY version DESC",
        (doc_id,),
    ).fetchall()
    conn.close()
    return render_template("versions.html", current=current, archived=archived)


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


@app.route("/archive/<int:archive_id>/download")
def download_archived(archive_id):
    conn = get_connection()
    row = conn.execute("SELECT * FROM document_archive WHERE id = ?", (archive_id,)).fetchone()
    conn.close()
    if row is None:
        return "Archived version not found", 404
    return send_file(
        io.BytesIO(row["content"]),
        as_attachment=True,
        download_name=row["filename"],
    )


@app.route("/new", methods=["GET", "POST"])
def new_doc():
    if request.method == "POST":
        category = request.form["category"]
        doc_type = request.form["doc_type"]
        short_title = request.form["short_title"]
        file_type = request.form["file_type"]
        content_text = request.form["content"]

        raw_content = csv_to_rows(content_text) if file_type == "xlsx" else content_text
        row = save_new_version(category, doc_type, short_title, file_type, raw_content)
        return redirect(url_for("category_view", category=row["category"]))

    return render_template("new.html", categories=CATEGORIES, doc_types=DOC_TYPES)


if __name__ == "__main__":
    init_db()
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT", 5000)), debug=False)
