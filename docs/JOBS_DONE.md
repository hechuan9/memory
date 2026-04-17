# Jobs Done

- 2026-04-17: Documented official Codex Memories as runtime upstream, recorded Markdown recall/fallback retirement in repo docs, and added `docs/superpowers/plans/2026-04-17-official-memory-integration.md`.
- 2026-04-15: Stopped indexing retained transcript events as `memory_items.kind = session_event`, kept session archives in `sessions/session_events`, updated tests for hook/import archival behavior, and preserved legacy imported-event prune coverage.
- 2026-04-13: Added CLI-first dream management commands (`dream-report`, item CRUD, candidate promote/reject, conflict mark/resolve, Markdown export), updated docs and tests, and made `codex-memory` CLI the primary memory hygiene surface.
- 2026-04-12: Fixed Codex `Stop` hook output to satisfy the event-specific JSON schema, added null transcript coverage, and added repo merge guardrails.
