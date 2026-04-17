from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

from codex_memory.config import MemoryConfig, load_config
from codex_memory.conversations import import_codex_conversations, prune_imported_events, stats_payload
from codex_memory.hooks import (
    handle_session_start,
    handle_stop,
    handle_user_prompt_submit,
    loads_hook_payload,
)
from codex_memory.official import seed_official_memories
from codex_memory.store import MemoryItem, MemoryStore
from codex_memory.skills import write_skill_candidate


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    try:
        return int(args.func(args))
    except Exception as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 1


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="codex-memory")
    parser.add_argument("--config", help="Path to local config.toml")
    subparsers = parser.add_subparsers(required=True)

    seed = subparsers.add_parser("seed", help="Index official Codex memories")
    seed.add_argument("--config", help="Path to local config.toml")
    seed.add_argument("--scope", choices=("runtime", "full"), default="full", help="Official memory source scope")
    seed.add_argument("--json", action="store_true", help="Emit JSON")
    seed.set_defaults(func=cmd_seed)

    recall = subparsers.add_parser("recall", help="Recall scoped memory")
    recall.add_argument("--config", help="Path to local config.toml")
    recall.add_argument("--repo", help="Current repository name")
    recall.add_argument("--query", required=True, help="Recall query")
    recall.add_argument("--limit", type=int, default=12)
    recall.add_argument("--max-session-events", type=int, default=3)
    recall.add_argument("--include-candidates", action="store_true")
    recall.add_argument("--json", action="store_true", help="Emit JSON")
    recall.set_defaults(func=cmd_recall)

    context = subparsers.add_parser("context", help="Emit recall context")
    context.add_argument("--config", help="Path to local config.toml")
    context.add_argument("--repo", help="Current repository name")
    context.add_argument("--query", required=True, help="Context query")
    context.add_argument("--limit", type=int, default=12)
    context.add_argument("--max-session-events", type=int, default=3)
    context.add_argument("--max-chars", type=int, default=4000)
    context.add_argument(
        "--fallback",
        choices=("empty", "always", "never"),
        default="empty",
        help="Deprecated. Markdown fallback is retired; this flag is now a no-op.",
    )
    context.add_argument("--json", action="store_true", help="Emit JSON")
    context.set_defaults(func=cmd_context)

    hook = subparsers.add_parser("hook", help="Run Codex lifecycle hook handlers")
    hook.add_argument("--config", help="Path to local config.toml")
    hook_sub = hook.add_subparsers(required=True)
    hook_session_start = hook_sub.add_parser("session-start", help="Handle Codex SessionStart hook")
    hook_session_start.add_argument("--config", help="Path to local config.toml")
    hook_session_start.set_defaults(func=cmd_hook_session_start)
    hook_user_prompt = hook_sub.add_parser("user-prompt-submit", help="Handle Codex UserPromptSubmit hook")
    hook_user_prompt.add_argument("--config", help="Path to local config.toml")
    hook_user_prompt.set_defaults(func=cmd_hook_user_prompt_submit)
    hook_stop = hook_sub.add_parser("stop", help="Handle Codex Stop hook")
    hook_stop.add_argument("--config", help="Path to local config.toml")
    hook_stop.set_defaults(func=cmd_hook_stop)

    retain = subparsers.add_parser("retain-session", help="Retain a structured session JSON payload")
    retain.add_argument("--config", help="Path to local config.toml")
    retain.add_argument("--stdin-json", action="store_true", help="Read payload from stdin")
    retain.set_defaults(func=cmd_retain_session)

    import_conversations = subparsers.add_parser(
        "import-conversations",
        help="Import local Codex archived conversations in dry-run mode by default",
    )
    import_conversations.add_argument("--config", help="Path to local config.toml")
    import_conversations.add_argument("--codex-home", default=str(Path.home() / ".codex"))
    import_conversations.add_argument("--input-dir", help="Directory containing Codex archived *.jsonl sessions")
    import_conversations.add_argument("--since-days", type=int, default=30)
    import_conversations.add_argument("--repo", default="auto", help="'auto' or an explicit repository name")
    import_conversations.add_argument("--max-files", type=int, default=25)
    import_conversations.add_argument("--max-events-per-session", type=int, default=80)
    import_conversations.add_argument("--write", action="store_true", help="Write imported session events")
    import_conversations.add_argument("--dry-run", action="store_true", help="Accepted for clarity; this is the default")
    import_conversations.add_argument("--json", action="store_true")
    import_conversations.set_defaults(func=cmd_import_conversations)

    imported_events = subparsers.add_parser("imported-events", help="Inspect or prune imported session events")
    imported_events_sub = imported_events.add_subparsers(required=True)
    imported_events_prune = imported_events_sub.add_parser("prune", help="Prune noisy imported session events")
    imported_events_prune.add_argument("--config", help="Path to local config.toml")
    imported_events_prune.add_argument("--apply", action="store_true", help="Delete matched event items from recall index")
    imported_events_prune.add_argument("--limit", type=int, default=500)
    imported_events_prune.add_argument("--json", action="store_true")
    imported_events_prune.set_defaults(func=cmd_imported_events_prune)

    items = subparsers.add_parser("items", help="Inspect or manage memory items")
    items_sub = items.add_subparsers(required=True)
    items_list = items_sub.add_parser("list", help="List memory items")
    items_list.add_argument("--config", help="Path to local config.toml")
    items_list.add_argument("--repo", help="Repository filter")
    items_list.add_argument("--bank-id", help="Bank filter, e.g. global or repo:model")
    items_list.add_argument("--kind", help="Kind filter")
    items_list.add_argument("--status", help="Status filter")
    items_list.add_argument("--limit", type=int, default=50)
    items_list.add_argument("--json", action="store_true")
    items_list.set_defaults(func=cmd_items_list)
    items_get = items_sub.add_parser("get", help="Get a memory item")
    items_get.add_argument("item_id")
    items_get.add_argument("--config", help="Path to local config.toml")
    items_get.add_argument("--json", action="store_true")
    items_get.set_defaults(func=cmd_items_get)
    items_update = items_sub.add_parser("update", help="Update memory item fields")
    items_update.add_argument("item_id")
    items_update.add_argument("--config", help="Path to local config.toml")
    items_update.add_argument("--content")
    items_update.add_argument("--evidence")
    items_update.add_argument("--status")
    items_update.add_argument("--json", action="store_true")
    items_update.set_defaults(func=cmd_items_update)
    items_delete = items_sub.add_parser("delete", help="Delete a memory item")
    items_delete.add_argument("item_id")
    items_delete.add_argument("--config", help="Path to local config.toml")
    items_delete.add_argument("--json", action="store_true")
    items_delete.set_defaults(func=cmd_items_delete)

    candidates = subparsers.add_parser("candidates", help="List candidate memories")
    candidates_sub = candidates.add_subparsers(required=True)
    candidates_list = candidates_sub.add_parser("list", help="List candidate memories")
    candidates_list.add_argument("--config", help="Path to local config.toml")
    candidates_list.add_argument("--repo", help="Repository filter")
    candidates_list.add_argument("--json", action="store_true")
    candidates_list.set_defaults(func=cmd_candidates_list)
    candidates_promote = candidates_sub.add_parser("promote", help="Promote a candidate to active memory")
    candidates_promote.add_argument("item_id")
    candidates_promote.add_argument("--config", help="Path to local config.toml")
    candidates_promote.add_argument("--json", action="store_true")
    candidates_promote.set_defaults(func=cmd_candidates_promote)
    candidates_reject = candidates_sub.add_parser("reject", help="Reject a candidate")
    candidates_reject.add_argument("item_id")
    candidates_reject.add_argument("--config", help="Path to local config.toml")
    candidates_reject.add_argument("--json", action="store_true")
    candidates_reject.set_defaults(func=cmd_candidates_reject)

    conflicts = subparsers.add_parser("conflicts", help="Track memory conflicts")
    conflicts_sub = conflicts.add_subparsers(required=True)
    conflicts_mark = conflicts_sub.add_parser("mark", help="Create an active conflict item")
    conflicts_mark.add_argument("--config", help="Path to local config.toml")
    conflicts_mark.add_argument("--repo", help="Repository scope")
    conflicts_mark.add_argument("--content", required=True)
    conflicts_mark.add_argument("--evidence", default="")
    conflicts_mark.add_argument("--json", action="store_true")
    conflicts_mark.set_defaults(func=cmd_conflicts_mark)
    conflicts_resolve = conflicts_sub.add_parser("resolve", help="Resolve a conflict item")
    conflicts_resolve.add_argument("item_id")
    conflicts_resolve.add_argument("--config", help="Path to local config.toml")
    conflicts_resolve.add_argument("--json", action="store_true")
    conflicts_resolve.set_defaults(func=cmd_conflicts_resolve)

    export = subparsers.add_parser("export", help="Export memory data")
    export_sub = export.add_subparsers(required=True)
    export_markdown = export_sub.add_parser("markdown", help="Export a bank as Markdown")
    export_markdown.add_argument("--config", help="Path to local config.toml")
    export_markdown.add_argument("--bank-id", required=True)
    export_markdown.add_argument("--status", default="active")
    export_markdown.add_argument("--limit", type=int, default=500)
    export_markdown.add_argument("--json", action="store_true")
    export_markdown.set_defaults(func=cmd_export_markdown)

    skill_candidates = subparsers.add_parser("skill-candidates", help="Create or inspect skill candidates")
    skill_sub = skill_candidates.add_subparsers(required=True)
    skill_create = skill_sub.add_parser("create", help="Write a skill candidate draft")
    skill_create.add_argument("--config", help="Path to local config.toml")
    skill_create.add_argument("--title", required=True)
    skill_create.add_argument("--slug", required=True)
    skill_create.add_argument("--applies-when", required=True)
    skill_create.add_argument("--trigger", action="append", default=[])
    skill_create.add_argument("--step", action="append", default=[])
    skill_create.add_argument("--counterexample", action="append", default=[])
    skill_create.add_argument("--evidence", required=True)
    skill_create.add_argument("--suggested-install-path", required=True)
    skill_create.set_defaults(func=cmd_skill_candidate_create)

    status = subparsers.add_parser("status", help="Show local memory status")
    status.add_argument("--config", help="Path to local config.toml")
    status.add_argument("--json", action="store_true")
    status.set_defaults(func=cmd_status)

    dream_report = subparsers.add_parser("dream-report", help="Emit CLI-first memory dream audit report")
    dream_report.add_argument("--config", help="Path to local config.toml")
    dream_report.add_argument("--repo", help="Repository scope")
    dream_report.add_argument("--query", required=True)
    dream_report.add_argument("--limit", type=int, default=12)
    dream_report.add_argument("--max-session-events", type=int, default=3)
    dream_report.add_argument("--max-chars", type=int, default=4000)
    dream_report.add_argument("--json", action="store_true")
    dream_report.set_defaults(func=cmd_dream_report)
    return parser


def cmd_seed(args: argparse.Namespace) -> int:
    config = _config(args)
    store = _store(config)
    stats = seed_official_memories(
        store,
        memories_dir=config.official_memories_dir,
        repo_names=config.repo_names,
        scope=args.scope,
    )
    payload = {
        "seed_source": "official_memories",
        "scope": args.scope,
        "indexed_files": stats.indexed_files,
        "indexed_items": stats.indexed_items,
        "pruned_items": stats.pruned_items,
        "database_path": str(config.database_path),
    }
    _emit(payload, json_output=args.json)
    return 0


def cmd_recall(args: argparse.Namespace) -> int:
    config = _config(args)
    store = _store(config)
    results = store.recall(
        args.query,
        repo=args.repo,
        limit=args.limit,
        include_candidates=args.include_candidates,
        max_session_events=args.max_session_events,
    )
    payload = {"results": [_item_payload(item) for item in results]}
    if args.json:
        _emit(payload, json_output=True)
    else:
        print("<memory-context>")
        print("[System note: recalled memory context, not new user input.]")
        for item in results:
            print(f"- [{item.bank_id}/{item.kind}] {item.content}")
        print("</memory-context>")
    return 0


def cmd_context(args: argparse.Namespace) -> int:
    config = _config(args)
    store = _store(config)
    results = store.recall(
        args.query,
        repo=args.repo,
        limit=args.limit,
        max_chars=args.max_chars,
        max_session_events=args.max_session_events,
    )
    payload = {
        "mode": "recall" if results else "empty",
        "results": [_item_payload(item) for item in results],
        "fallback": {
            "requested": args.fallback,
            "status": "retired",
        },
    }
    _emit_context_payload(payload, json_output=args.json)
    return 0


def cmd_retain_session(args: argparse.Namespace) -> int:
    if not args.stdin_json:
        raise ValueError("--stdin-json is required")
    payload = json.loads(sys.stdin.read())
    config = _config(args)
    store = _store(config)
    session_id = store.retain_session(
        repo=payload.get("repo"),
        cwd=payload.get("cwd"),
        summary=payload.get("summary", ""),
        events=payload.get("events", []),
        candidates=payload.get("candidates", []),
        tags=payload.get("tags", []),
        session_id=payload.get("session_id"),
    )
    _emit({"session_id": session_id}, json_output=True)
    return 0


def cmd_hook_session_start(args: argparse.Namespace) -> int:
    config = _config(args)
    store = _store(config)
    result = handle_session_start(config, store, loads_hook_payload(sys.stdin.read()))
    _emit(result.payload, json_output=True)
    return 0


def cmd_hook_user_prompt_submit(args: argparse.Namespace) -> int:
    config = _config(args)
    store = _store(config)
    result = handle_user_prompt_submit(config, store, loads_hook_payload(sys.stdin.read()))
    _emit(result.payload, json_output=True)
    return 0


def cmd_hook_stop(args: argparse.Namespace) -> int:
    config = _config(args)
    store = _store(config)
    result = handle_stop(config, store, loads_hook_payload(sys.stdin.read()))
    _emit(result.payload, json_output=True)
    return 0


def cmd_import_conversations(args: argparse.Namespace) -> int:
    if args.write and args.dry_run:
        raise ValueError("--write and --dry-run cannot be used together")
    config = _config(args)
    store = _store(config)
    input_dir = Path(args.input_dir).expanduser() if args.input_dir else Path(args.codex_home).expanduser() / "archived_sessions"
    if not input_dir.exists():
        raise ValueError(f"conversation input directory does not exist: {input_dir}")
    stats = import_codex_conversations(
        store,
        input_dir=input_dir,
        since_days=args.since_days,
        repo=args.repo,
        write=args.write,
        max_files=args.max_files,
        max_events_per_session=args.max_events_per_session,
    )
    _emit(stats_payload(stats, write=args.write), json_output=args.json)
    return 0


def cmd_imported_events_prune(args: argparse.Namespace) -> int:
    config = _config(args)
    store = _store(config)
    stats = prune_imported_events(store, apply=args.apply, limit=args.limit)
    payload = {
        "mode": "apply" if args.apply else "dry-run",
        "matched": stats.matched,
        "pruned": stats.pruned,
        "sanitized": stats.sanitized,
        "item_ids": stats.item_ids,
    }
    _emit(payload, json_output=args.json)
    return 0


def cmd_candidates_list(args: argparse.Namespace) -> int:
    config = _config(args)
    store = _store(config)
    candidates = store.list_candidates(repo=args.repo)
    payload = {"candidates": [_item_payload(item) for item in candidates]}
    _emit(payload, json_output=args.json)
    return 0


def cmd_items_list(args: argparse.Namespace) -> int:
    config = _config(args)
    store = _store(config)
    items = store.list_items(
        repo=args.repo,
        bank_id=args.bank_id,
        kind=args.kind,
        status=args.status,
        limit=args.limit,
    )
    _emit({"items": [_item_payload(item) for item in items]}, json_output=args.json)
    return 0


def cmd_items_get(args: argparse.Namespace) -> int:
    config = _config(args)
    store = _store(config)
    item = _require_item(store, args.item_id)
    _emit({"item": _item_payload(item)}, json_output=args.json)
    return 0


def cmd_items_update(args: argparse.Namespace) -> int:
    config = _config(args)
    store = _store(config)
    item = store.update_item(
        args.item_id,
        content=args.content,
        evidence=args.evidence,
        status=args.status,
    )
    if item is None:
        raise ValueError(f"memory item not found: {args.item_id}")
    _emit({"item": _item_payload(item)}, json_output=args.json)
    return 0


def cmd_items_delete(args: argparse.Namespace) -> int:
    config = _config(args)
    store = _store(config)
    deleted = store.delete_items([args.item_id])
    _emit({"deleted": deleted, "id": args.item_id}, json_output=args.json)
    return 0


def cmd_candidates_promote(args: argparse.Namespace) -> int:
    config = _config(args)
    store = _store(config)
    item = _require_item(store, args.item_id)
    if item.status != "candidate":
        raise ValueError(f"memory item is not a candidate: {args.item_id}")
    promoted = store.set_item_status(args.item_id, "active")
    if promoted is None:
        raise ValueError(f"memory item not found: {args.item_id}")
    _emit({"item": _item_payload(promoted)}, json_output=args.json)
    return 0


def cmd_candidates_reject(args: argparse.Namespace) -> int:
    config = _config(args)
    store = _store(config)
    item = _require_item(store, args.item_id)
    if item.status != "candidate":
        raise ValueError(f"memory item is not a candidate: {args.item_id}")
    rejected = store.set_item_status(args.item_id, "rejected")
    if rejected is None:
        raise ValueError(f"memory item not found: {args.item_id}")
    _emit({"item": _item_payload(rejected)}, json_output=args.json)
    return 0


def cmd_conflicts_mark(args: argparse.Namespace) -> int:
    config = _config(args)
    store = _store(config)
    bank_id = f"repo:{args.repo}" if args.repo else "global"
    item_id = store.upsert_item(
        bank_id=bank_id,
        repo=args.repo,
        kind="conflict",
        status="active",
        content=args.content,
        evidence=args.evidence,
        tags=[*([] if not args.repo else [f"repo:{args.repo}"]), "kind:conflict"],
    )
    item = _require_item(store, item_id)
    _emit({"item": _item_payload(item)}, json_output=args.json)
    return 0


def cmd_conflicts_resolve(args: argparse.Namespace) -> int:
    config = _config(args)
    store = _store(config)
    item = _require_item(store, args.item_id)
    if item.kind != "conflict":
        raise ValueError(f"memory item is not a conflict: {args.item_id}")
    resolved = store.set_item_status(args.item_id, "resolved")
    if resolved is None:
        raise ValueError(f"memory item not found: {args.item_id}")
    _emit({"item": _item_payload(resolved)}, json_output=args.json)
    return 0


def cmd_export_markdown(args: argparse.Namespace) -> int:
    config = _config(args)
    store = _store(config)
    items = store.list_items(bank_id=args.bank_id, status=args.status, limit=args.limit)
    lines = [f"# codex-memory export: {args.bank_id}", ""]
    for item in items:
        lines.append(f"- {item.content}")
    markdown = "\n".join(lines).rstrip() + "\n"
    _emit(
        {
            "bank_id": args.bank_id,
            "status": args.status,
            "items": len(items),
            "markdown": markdown,
        },
        json_output=args.json,
    )
    return 0


def cmd_dream_report(args: argparse.Namespace) -> int:
    config = _config(args)
    store = _store(config)
    results = store.recall(
        args.query,
        repo=args.repo,
        limit=args.limit,
        max_chars=args.max_chars,
        max_session_events=args.max_session_events,
    )
    context_mode = "recall" if results else "empty"
    context_results: list[dict[str, Any]] = [_item_payload(item) for item in results]
    prune_stats = prune_imported_events(store, apply=False, limit=500)
    payload = {
        "status": _status_payload(config, store),
        "seed": {
            "mode": "sqlite-canonical",
            "indexed_items": 0,
            "pruned_items": 0,
        },
        "context": {
            "mode": context_mode,
            "repo": args.repo,
            "query": args.query,
            "results": context_results,
        },
        "candidates": [_item_payload(item) for item in store.list_candidates(repo=args.repo)],
        "imported_events": {
            "mode": "dry-run",
            "matched": prune_stats.matched,
            "pruned": prune_stats.pruned,
            "sanitized": prune_stats.sanitized,
            "item_ids": prune_stats.item_ids,
        },
    }
    _emit(payload, json_output=args.json)
    return 0


def cmd_skill_candidate_create(args: argparse.Namespace) -> int:
    config = _config(args)
    output_dir = config.data_dir / "skill-candidates"
    path = write_skill_candidate(
        output_dir=output_dir,
        title=args.title,
        slug=args.slug,
        applies_when=args.applies_when,
        triggers=args.trigger,
        steps=args.step,
        counterexamples=args.counterexample,
        evidence=args.evidence,
        suggested_install_path=args.suggested_install_path,
    )
    _emit({"path": str(path)}, json_output=True)
    return 0


def cmd_status(args: argparse.Namespace) -> int:
    config = _config(args)
    store = _store(config)
    _emit(_status_payload(config, store), json_output=args.json)
    return 0


def _config(args: argparse.Namespace) -> MemoryConfig:
    return load_config(getattr(args, "config", None))


def _store(config: MemoryConfig) -> MemoryStore:
    store = MemoryStore(config.database_path)
    store.initialize()
    return store


def _status_payload(config: MemoryConfig, store: MemoryStore) -> dict[str, Any]:
    return {
        "data_dir": str(config.data_dir),
        "database_path": str(config.database_path),
        "items": store.count_items(),
        "sessions": store.count_sessions(),
    }


def _require_item(store: MemoryStore, item_id: str) -> MemoryItem:
    item = store.get_item(item_id)
    if item is None:
        raise ValueError(f"memory item not found: {item_id}")
    return item


def _item_payload(item: MemoryItem) -> dict[str, Any]:
    return {
        "id": item.id,
        "bank_id": item.bank_id,
        "repo": item.repo,
        "kind": item.kind,
        "status": item.status,
        "source_path": item.source_path,
        "source_anchor": item.source_anchor,
        "content": item.content,
        "evidence": item.evidence,
        "tags": json.loads(item.tags_json),
        "score": item.score,
    }


def _emit_context_payload(payload: dict[str, Any], *, json_output: bool) -> None:
    if json_output:
        _emit(payload, json_output=True)
        return
    print("<memory-context>")
    print("[System note: recalled memory context from codex-memory, not new user input.]")
    for item in payload["results"]:
        print(f"- [{item['bank_id']}/{item['kind']}] {item['content']}")
    print("</memory-context>")


def _emit(payload: dict[str, Any], *, json_output: bool) -> None:
    if json_output:
        print(json.dumps(payload, ensure_ascii=False, indent=2))
        return
    for key, value in payload.items():
        print(f"{key}: {value}")


if __name__ == "__main__":
    raise SystemExit(main())
