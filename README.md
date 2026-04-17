# codex-memory

Local-first memory and self-learning helpers for Codex workflows.

This repository provides a Python CLI that keeps local memory in a SQLite + FTS5 store, recalls scoped memory for runtime context, audits memory candidates, and manages retention workflows. It is designed to be public-safe: local databases, transcripts, logs, and generated candidate drafts stay outside git.

## Why This Exists

Codex Desktop does not currently expose a controllable long-term memory layer for this workflow, so this repository provides one through local `codex-memory` runtime storage. Runtime recall, hooks, `context`, and `dream-report` read SQLite directly. Markdown files are import/export and human-audit artifacts only; they are not runtime recall, hook, or fallback sources.

## What It Does

- Imports official Codex Memories into a local SQLite + FTS5 store on explicit `seed` runs.
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

Edit the copied file for your machine. Do not commit it. Public-repo configs must not contain private paths or secrets.

## CLI

```bash
uv run --python 3.11 codex-memory seed --config "$CODEX_HOME/memory/config.toml"
uv run --python 3.11 codex-memory recall --repo model --query "What should I read before model training changes?"
uv run --python 3.11 codex-memory context --repo model --query "What should I read before model training changes?"
uv run --python 3.11 codex-memory status --config "$CODEX_HOME/memory/config.toml"
```

`context` is the preferred startup entrypoint. It reads recall from SQLite only and does not refresh Markdown or official memory files. Run `seed --scope runtime` only when intentionally importing high-signal official-memory exports into SQLite; run `seed --scope full` only when intentionally importing the complete audit corpus. `fallback` is retired and does not consult Markdown runtime sources. `dream-report` is the preferred memory hygiene entrypoint because it combines SQLite status, recall context, candidate inventory, and imported-event noise checks into one JSON payload without mutating the recall index.

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

`session-start` and `user-prompt-submit` inject recalled context as additional developer context from SQLite only. `stop` parses the local transcript path from the hook payload and retains safe user/assistant events in SQLite. Hooks do not seed Markdown exports, edit Markdown exports, or install skills.

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
