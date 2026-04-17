# TODO

## Active

- [ ] Add a Codex session-end retain helper that accepts a compact structured summary, archives transcript events in `session_events`, and writes only reviewed `candidate` records into `memory_items`.
- [ ] Add a manual review command for imported `session_event` records, with filters for `repo`, `bank_id`, `kind`, `source_anchor`, and short JSON output.
- [x] Add a candidate promotion workflow for selected `candidate` records through `codex-memory candidates promote/reject`.
- [x] Add CLI-first dream audit output through `codex-memory dream-report`.
- [x] Add item CRUD, conflict lifecycle, and Markdown export commands for migration support.
- [ ] Add skill candidate extraction from repeated session workflows, but keep installation manual through existing skill review paths.
- [x] Remove local startup wrapper requirement; `context` entrypoint is authoritative for startup bootstrap.
- [ ] Add migration metrics that show recall hit mix by `kind` so imported sessions cannot silently dominate durable Markdown sources.

## Guardrails

- [x] Keep local home paths, SQLite files, transcripts, logs, secrets, and private path dumps out of this public repository.
- [x] Treat the SQLite store and `codex-memory` CLI as the primary operational surface; keep Markdown as legacy import/export and human audit material.
- [ ] Keep historical import batch sizes small; expand only after recall quality checks.
- [ ] Keep raw transcript events in `sessions/session_events`; do not index new `session_event` items into durable recall.
