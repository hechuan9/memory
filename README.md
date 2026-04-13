# codex-memory

Local-first memory and self-learning helpers for Codex workflows.

This repository provides a small Python CLI that indexes existing Markdown memory, stores session summaries locally, recalls relevant context across sessions, audits memory hygiene, and drafts reusable skill candidates. It is designed to be public-safe: local databases, transcripts, logs, and generated candidate drafts stay outside git.

## Why This Exists

Codex Desktop does not currently expose a controllable local-first long-term memory layer for this workflow. This repository provides that missing layer. The CLI and its SQLite store are the primary operational layer for recall, review, and memory hygiene; configured Markdown files remain a legacy import/export and human audit surface during migration. It is not a replacement for ChatGPT or Codex session history; it is a local recall, retention, candidate, and skill-draft system designed to run without MCP or cloud memory services.

## What It Does

- Indexes durable Markdown sources into a local SQLite + FTS5 store.
- Recalls scoped memory from a current repository bank plus a global bank.
- Retains structured session summaries and candidate long-term memories.
- Imports local Codex archived conversations in explicit dry-run/write migration steps.
- Connects to Codex lifecycle hooks for automatic local recall and session retention.
- Reviews, promotes, rejects, updates, exports, and reports memory items from the CLI.
- Drafts skill candidates without installing or modifying real skills.

## What It Does Not Do

- It does not use MCP.
- It does not call Hindsight or any cloud memory service.
- It does not require an extra local LLM service.
- It does not automatically edit Markdown memory truth sources.
- It does not automatically install skills.

## Install

```bash
uv sync --python 3.11 --extra dev
```

## Configure

Copy an example config to your local data directory:

```bash
mkdir -p "${CODEX_HOME:-$HOME/.codex}/memory"
cp examples/climamind.config.example.toml "${CODEX_HOME:-$HOME/.codex}/memory/config.toml"
```

Edit the copied file for your machine. Do not commit it.

## CLI

```bash
uv run --python 3.11 codex-memory seed --config "$CODEX_HOME/memory/config.toml"
uv run --python 3.11 codex-memory recall --repo model --query "What should I read before model training changes?"
uv run --python 3.11 codex-memory context --repo model --query "What should I read before model training changes?"
uv run --python 3.11 codex-memory status --config "$CODEX_HOME/memory/config.toml"
```

`context` is the preferred startup entrypoint. It uses SQLite recall first, then falls back to configured Markdown sources when recall is empty. `dream-report` is the preferred memory hygiene entrypoint because it combines index refresh, status, recall context, candidate inventory, and imported-event noise checks into one JSON payload.

CLI-first memory hygiene:

```bash
uv run --python 3.11 codex-memory dream-report \
  --config "$CODEX_HOME/memory/config.toml" \
  --repo model \
  --query "model memory dream conflicts candidates" \
  --json
uv run --python 3.11 codex-memory candidates list --config "$CODEX_HOME/memory/config.toml" --json
uv run --python 3.11 codex-memory imported-events prune --config "$CODEX_HOME/memory/config.toml" --json
```

Review and manage memory items:

```bash
uv run --python 3.11 codex-memory items list --config "$CODEX_HOME/memory/config.toml" --repo model --json
uv run --python 3.11 codex-memory items get mem_<id> --config "$CODEX_HOME/memory/config.toml" --json
uv run --python 3.11 codex-memory items update mem_<id> --config "$CODEX_HOME/memory/config.toml" --content "Updated stable memory." --json
uv run --python 3.11 codex-memory items delete mem_<id> --config "$CODEX_HOME/memory/config.toml" --json
uv run --python 3.11 codex-memory candidates promote mem_<id> --config "$CODEX_HOME/memory/config.toml" --json
uv run --python 3.11 codex-memory candidates reject mem_<id> --config "$CODEX_HOME/memory/config.toml" --json
uv run --python 3.11 codex-memory conflicts mark --config "$CODEX_HOME/memory/config.toml" --repo model --content "Conflicting rule" --evidence "Why it conflicts" --json
uv run --python 3.11 codex-memory conflicts resolve mem_<id> --config "$CODEX_HOME/memory/config.toml" --json
uv run --python 3.11 codex-memory export markdown --config "$CODEX_HOME/memory/config.toml" --bank-id repo:model --json
```

Codex lifecycle hooks can call the `hook` subcommands. They read the Codex hook payload from stdin and emit the JSON shape Codex expects:

```bash
uv run --python 3.11 codex-memory hook session-start --config "$CODEX_HOME/memory/config.toml"
uv run --python 3.11 codex-memory hook user-prompt-submit --config "$CODEX_HOME/memory/config.toml"
uv run --python 3.11 codex-memory hook stop --config "$CODEX_HOME/memory/config.toml"
```

`session-start` and `user-prompt-submit` inject recalled context as additional developer context. `stop` parses the local transcript path from the hook payload and retains safe user/assistant events in SQLite. Hooks still do not edit Markdown exports or install skills.

Limit imported session snippets during recall:

```bash
uv run --python 3.11 codex-memory recall --repo backend --query "release checks" --max-session-events 2
uv run --python 3.11 codex-memory recall --repo backend --query "release checks" --max-session-events 0
```

Start migration conservatively:

```bash
uv run --python 3.11 codex-memory seed --config "$CODEX_HOME/memory/config.toml" --json
uv run --python 3.11 codex-memory import-conversations --config "$CODEX_HOME/memory/config.toml" --since-days 30 --max-files 25 --json
uv run --python 3.11 codex-memory import-conversations --config "$CODEX_HOME/memory/config.toml" --since-days 30 --max-files 25 --write --json
```

`import-conversations` defaults to dry-run. It reads local Codex `archived_sessions/*.jsonl`, keeps only user/assistant events that pass the safety scanner, infers `repo:<name>` from the working directory when possible, and does not create long-term memory candidates or edit Markdown truth sources.

Retain a session from JSON:

```bash
cat session.json | uv run --python 3.11 codex-memory retain-session --stdin-json
```

## Retain JSON Shape

```json
{
  "repo": "model",
  "cwd": "/path/to/repo",
  "summary": "Short factual session summary.",
  "events": [
    {"role": "user", "content": "User request"},
    {"role": "assistant", "content": "Assistant result"}
  ],
  "candidates": [
    {
      "kind": "workflow",
      "content": "Stable candidate memory.",
      "evidence": "Why this might be durable.",
      "tags": ["repo:model"]
    }
  ]
}
```

## Tests

```bash
uv run --python 3.11 python -m pytest -q
```
