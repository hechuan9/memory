# TODO

## Active

- [ ] Add a Codex session-end retain helper that accepts a compact structured summary and writes `session_event` plus `candidate` records without touching Markdown truth sources.
- [ ] Add a manual review command for imported `session_event` records, with filters for `repo`, `bank_id`, `kind`, `source_anchor`, and short JSON output.
- [ ] Add a candidate promotion workflow that exports selected `candidate` records into review-ready Markdown for the existing `memory-capture` flow.
- [ ] Add skill candidate extraction from repeated session workflows, but keep installation manual through existing skill review paths.
- [ ] Add a local startup wrapper example that runs `seed` and `recall`, then emits fenced context marked as recalled background, not user instruction.
- [ ] Add migration metrics that show recall hit mix by `kind` so imported sessions cannot silently dominate durable Markdown sources.

## Guardrails

- [ ] Keep local home paths, SQLite files, transcripts, logs, secrets, and private path dumps out of this public repository.
- [ ] Keep Markdown memory as the truth source until a later explicit migration stage.
- [ ] Keep historical import batch sizes small; expand only after recall quality checks.
- [ ] Keep `session_event` recall as supplemental context, not a replacement for durable memory.
