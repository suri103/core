# `app/schemas/planned/` — Planned but Unimplemented Schemas

This directory holds **schema-only** modules that describe features the
backend has not yet shipped. They are kept here (rather than deleted) so
that:

1. The contract is documented and can be reviewed before the feature lands.
2. The schemas can be referenced from RFC docs, design notes, or issue
   trackers without anyone having to dig through git history.
3. When the implementation starts, the schemas move back up to
   `app/schemas/<name>.py` rather than being rewritten from scratch.

## Rules for this directory

- **No code under `app/api/`, `app/core/`, or `app/services/` may import
  from this directory.** If a route or service imports a schema here, the
  feature is no longer "planned" and the file must be moved up.
- **No migrations, no Alembic revisions** reference these modules.
- **CI should pass** even with these files in place. A simple `python -c
  "import app.schemas.planned.accounting"` must succeed.
- **Reviews**: when a planned feature ships, move the file out of
  `planned/`, add the matching endpoint + tests, and remove the
  "PLANNED FEATURE" header.

## Current contents

- `accounting.py` — QuickBooks integration schemas (auth, invoice sync).
  The matching endpoint file does not exist yet.
