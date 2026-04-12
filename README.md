# codex-memory

Local-first memory and self-learning helpers for Codex workflows.

This repository provides a small Python CLI that indexes existing Markdown memory, stores session summaries locally, recalls relevant context across sessions, and drafts reusable skill candidates. It is designed to be public-safe: local databases, transcripts, logs, and generated candidate drafts stay outside git.

## What It Does

- Indexes durable Markdown sources into a local SQLite + FTS5 store.
- Recalls scoped memory from a current repository bank plus a global bank.
- Retains structured session summaries and candidate long-term memories.
- Imports local Codex archived conversations in explicit dry-run/write migration steps.
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
uv run --python 3.11 codex-memory status --config "$CODEX_HOME/memory/config.toml"
```

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
