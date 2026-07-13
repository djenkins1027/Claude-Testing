# Inbox — drop files here to add them to the database

Upload a document into the right entity folder below and the auto-ingest
workflow files it automatically within a minute or two: the original lands in
`/files/`, its text is extracted to `/extracted/`, and the search index is
updated. The inbox copy is removed once it's been filed.

## How to upload (GitHub website)

1. Open this folder on github.com and click into the entity's folder
   (`stillwater`, `pcl`, `riverwalk`, or `vault`).
2. Click **Add file → Upload files**, drag the document in, and commit.
3. **Name the file so it starts with the project number**, followed by an
   underscore — e.g. `SW-2026-001_shop_notes.docx`. (Alternatively, upload
   into an `inbox/{entity}/{project_number}/` folder if one exists.)
4. Wait a couple of minutes. When the file disappears from the inbox, it has
   been filed — find it under `/files/{entity}/{project_number}/` and its
   readable text under `/extracted/`.

If a file can't be filed (missing/unrecognizable project number, wrong
folder), it stays in the inbox and the workflow opens a GitHub issue titled
"Inbox upload needs attention" explaining what to fix. Progress is visible
under the repo's **Actions** tab.

Uploads can't carry descriptions or tags — ask Claude to add those to the
index afterwards if wanted.
