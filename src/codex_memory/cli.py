from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

from codex_memory.config import MemoryConfig, load_config
from codex_memory.sources import seed_markdown_sources
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

    seed = subparsers.add_parser("seed", help="Index configured Markdown memory sources")
    seed.add_argument("--config", help="Path to local config.toml")
    seed.add_argument("--json", action="store_true", help="Emit JSON")
    seed.set_defaults(func=cmd_seed)

    recall = subparsers.add_parser("recall", help="Recall scoped memory")
    recall.add_argument("--config", help="Path to local config.toml")
    recall.add_argument("--repo", help="Current repository name")
    recall.add_argument("--query", required=True, help="Recall query")
    recall.add_argument("--limit", type=int, default=12)
    recall.add_argument("--include-candidates", action="store_true")
    recall.add_argument("--json", action="store_true", help="Emit JSON")
    recall.set_defaults(func=cmd_recall)

    retain = subparsers.add_parser("retain-session", help="Retain a structured session JSON payload")
    retain.add_argument("--config", help="Path to local config.toml")
    retain.add_argument("--stdin-json", action="store_true", help="Read payload from stdin")
    retain.set_defaults(func=cmd_retain_session)

    candidates = subparsers.add_parser("candidates", help="List candidate memories")
    candidates_sub = candidates.add_subparsers(required=True)
    candidates_list = candidates_sub.add_parser("list", help="List candidate memories")
    candidates_list.add_argument("--config", help="Path to local config.toml")
    candidates_list.add_argument("--repo", help="Repository filter")
    candidates_list.add_argument("--json", action="store_true")
    candidates_list.set_defaults(func=cmd_candidates_list)

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
    return parser


def cmd_seed(args: argparse.Namespace) -> int:
    config = _config(args)
    store = _store(config)
    stats = seed_markdown_sources(
        store,
        global_memory_path=config.global_memory_path,
        workspace_root=config.workspace_root,
        repo_names=config.repo_names,
    )
    payload = {
        "indexed_files": stats.indexed_files,
        "indexed_items": stats.indexed_items,
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


def cmd_candidates_list(args: argparse.Namespace) -> int:
    config = _config(args)
    store = _store(config)
    candidates = store.list_candidates(repo=args.repo)
    payload = {"candidates": [_item_payload(item) for item in candidates]}
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
    payload = {
        "data_dir": str(config.data_dir),
        "database_path": str(config.database_path),
        "items": store.count_items(),
        "sessions": store.count_sessions(),
    }
    _emit(payload, json_output=args.json)
    return 0


def _config(args: argparse.Namespace) -> MemoryConfig:
    return load_config(getattr(args, "config", None))


def _store(config: MemoryConfig) -> MemoryStore:
    store = MemoryStore(config.database_path)
    store.initialize()
    return store


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


def _emit(payload: dict[str, Any], *, json_output: bool) -> None:
    if json_output:
        print(json.dumps(payload, ensure_ascii=False, indent=2))
        return
    for key, value in payload.items():
        print(f"{key}: {value}")


if __name__ == "__main__":
    raise SystemExit(main())
