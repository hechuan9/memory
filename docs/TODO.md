# TODO

## Active

- [ ] Add a Codex session-end retain helper that accepts a compact structured summary and writes `session_event` plus `candidate` records without touching Markdown truth sources.
- [ ] Add a manual review command for imported `session_event` records, with filters for `repo`, `bank_id`, `kind`, `source_anchor`, and short JSON output.
- [x] Add a candidate promotion workflow for selected `candidate` records through `codex-memory candidates promote/reject`.
- [x] Add CLI-first dream audit output through `codex-memory dream-report`.
- [x] Add item CRUD, conflict lifecycle, and Markdown export commands for migration support.
- [ ] Add skill candidate extraction from repeated session workflows, but keep installation manual through existing skill review paths.
- [ ] Add a local startup wrapper example that runs `seed` and `recall`, then emits fenced context marked as recalled background, not user instruction.
- [ ] Add migration metrics that show recall hit mix by `kind` so imported sessions cannot silently dominate durable Markdown sources.

## Guardrails

- [ ] Keep local home paths, SQLite files, transcripts, logs, secrets, and private path dumps out of this public repository.
- [ ] Treat the SQLite store and `codex-memory` CLI as the primary operational surface; keep Markdown as legacy import/export and human audit material until all automations are migrated.
- [ ] Keep historical import batch sizes small; expand only after recall quality checks.
- [ ] Keep `session_event` recall as supplemental context, not a replacement for durable memory.
