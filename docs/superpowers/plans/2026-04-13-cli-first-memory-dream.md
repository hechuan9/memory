# CLI-First Memory Dream Implementation Plan

> **For agentic workers:** REQUIRED: Use superpowers:subagent-driven-development (if subagents available) or superpowers:executing-plans to implement this plan. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Make daily memory dream use `codex-memory` CLI as the primary audit surface and add the missing CLI management commands needed for a future Markdown retirement.

**Architecture:** Keep the existing SQLite + FTS5 store as the primary operational layer. Add small store methods and CLI subcommands for item inspection, candidate promotion/rejection, conflict lifecycle, Markdown export, and a JSON dream report; update workflow documentation so Markdown is treated as legacy import/export material, not the main dream decision surface.

**Tech Stack:** Python 3.11, argparse CLI, SQLite/FTS5, pytest, uv.

---

## Chunk 1: CLI Management Commands

### Task 1: Add item and candidate lifecycle commands

**Files:**
- Modify: `src/codex_memory/store.py`
- Modify: `src/codex_memory/cli.py`
- Test: `tests/test_cli.py`

- [ ] Write failing CLI tests for `items list/get/update/delete`.
- [ ] Write failing CLI tests for `candidates promote/reject`.
- [ ] Implement store helpers: `list_items`, `get_item`, `update_item`, `set_item_status`, and FTS sync on updates.
- [ ] Wire argparse commands and JSON output.
- [ ] Run targeted CLI tests.

### Task 2: Add conflict lifecycle commands

**Files:**
- Modify: `src/codex_memory/store.py`
- Modify: `src/codex_memory/cli.py`
- Test: `tests/test_cli.py`

- [ ] Write failing tests for `conflicts mark` creating a `kind=conflict` active item.
- [ ] Write failing tests for `conflicts resolve` setting status to `resolved`.
- [ ] Implement conflict commands using existing `memory_items` rows instead of a new table.
- [ ] Run targeted CLI tests.

### Task 3: Add Markdown export and dream report

**Files:**
- Modify: `src/codex_memory/cli.py`
- Test: `tests/test_cli.py`

- [ ] Write failing tests for `export markdown --bank-id ...`.
- [ ] Write failing tests for `dream-report --repo ...` returning status, candidates, imported noise dry-run, and recall context.
- [ ] Implement export and report commands without mutating Markdown or SQLite.
- [ ] Run targeted CLI tests.

## Chunk 2: CLI-First Dream Workflow

### Task 4: Update docs and skill contract

**Files:**
- Modify: `README.md`
- Modify: `docs/TODO.md`
- Modify: `docs/MEMORY.md`
- External after code merge: `${CODEX_HOME}/skills/memory-dream/SKILL.md`
- External after code merge: `${CODEX_HOME}/automations/automation-3/memory.md`

- [ ] Document CLI-first dream commands in README.
- [ ] Update TODO to mark first/second phase pieces complete or narrowed.
- [ ] Add repo memory lesson: dream must not treat Markdown as the primary audit surface after CLI-first migration.
- [ ] After repository changes are validated, update installed `memory-dream` skill to require `codex-memory dream-report` during Orientation.
- [ ] Update automation-3 memory so future runs know CLI is primary and Markdown is legacy import/export.

## Verification

- [ ] Run `uv run --python 3.11 python -m pytest -q`.
- [ ] Run `bash scripts/pre_merge_gate.sh`.
- [ ] Smoke local CLI: `uv run --python 3.11 codex-memory dream-report --config ${CODEX_HOME}/memory/config.toml --repo memory --query "memory dream cli" --json`.
- [ ] Commit repository changes.
- [ ] Merge validated branch back to `main` and clean the worktree.
