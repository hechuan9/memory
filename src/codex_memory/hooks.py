from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from codex_memory.config import MemoryConfig
from codex_memory.conversations import parse_codex_conversation
from codex_memory.sources import MarkdownContextItem, collect_markdown_context, seed_markdown_sources
from codex_memory.store import MemoryItem, MemoryStore


HOOK_RECALL_LIMIT = 6
HOOK_RECALL_SEARCH_LIMIT = HOOK_RECALL_LIMIT * 3
HOOK_RECALL_MAX_CHARS = 2000
HOOK_RECALL_SEARCH_CHARS = HOOK_RECALL_MAX_CHARS * 2

_BOILERPLATE_MARKERS = (
    "本文件是",
    "这里只记录",
    "workspace root agENTS",
    "project-doc",
    "长期工程记忆",
)


@dataclass(frozen=True)
class HookResult:
    payload: dict[str, Any]


def handle_session_start(config: MemoryConfig, store: MemoryStore, payload: dict[str, Any]) -> HookResult:
    repo = infer_repo(payload.get("cwd"), config)
    seed_markdown_sources(
        store,
        global_memory_path=config.global_memory_path,
        workspace_root=config.workspace_root,
        repo_names=config.repo_names,
    )
    query = f"{repo or ''} workspace memory rules preferences".strip()
    context = recall_context(config, store, repo=repo, query=query)
    return HookResult(_additional_context_payload("SessionStart", context))


def handle_user_prompt_submit(config: MemoryConfig, store: MemoryStore, payload: dict[str, Any]) -> HookResult:
    repo = infer_repo(payload.get("cwd"), config)
    prompt = str(payload.get("prompt") or "").strip()
    if not prompt:
        return HookResult(_continue_payload("UserPromptSubmit"))
    seed_markdown_sources(
        store,
        global_memory_path=config.global_memory_path,
        workspace_root=config.workspace_root,
        repo_names=config.repo_names,
    )
    query = f"{repo or ''} {prompt}".strip()
    context = recall_context(config, store, repo=repo, query=query)
    return HookResult(_additional_context_payload("UserPromptSubmit", context))


def handle_stop(config: MemoryConfig, store: MemoryStore, payload: dict[str, Any]) -> HookResult:
    transcript_path = Path(str(payload.get("transcript_path") or "")).expanduser()
    if not transcript_path.is_file():
        return HookResult(_stop_continue_payload())

    parsed = parse_codex_conversation(
        transcript_path,
        repo="auto",
        max_events=80,
        max_event_chars=2000,
    )
    if not parsed.events:
        return HookResult(_stop_continue_payload())

    store.retain_session(
        repo=parsed.repo or infer_repo(payload.get("cwd"), config),
        cwd=parsed.cwd or str(payload.get("cwd") or ""),
        summary=parsed.summary,
        events=[{"role": event.role, "content": event.content} for event in parsed.events],
        candidates=[],
        tags=["codex-hook", "codex-conversation"],
        session_id=parsed.session_id,
    )
    return HookResult(_stop_continue_payload())


def infer_repo(cwd_value: object, config: MemoryConfig) -> str | None:
    raw_cwd = str(cwd_value or "").strip()
    if not raw_cwd:
        return None
    cwd = Path(raw_cwd).expanduser()
    repo_names = tuple(config.repo_names)
    for repo_name in repo_names:
        if cwd.name == repo_name:
            return repo_name
    if config.workspace_root:
        try:
            relative = cwd.resolve().relative_to(config.workspace_root.resolve())
        except (OSError, ValueError):
            relative = None
        if relative and relative.parts and relative.parts[0] in repo_names:
            return relative.parts[0]
    return None


def recall_context(
    config: MemoryConfig,
    store: MemoryStore,
    *,
    repo: str | None,
    query: str,
    limit: int = HOOK_RECALL_LIMIT,
    max_chars: int = HOOK_RECALL_MAX_CHARS,
) -> str:
    results = store.recall(
        query,
        repo=repo,
        limit=HOOK_RECALL_SEARCH_LIMIT,
        max_chars=HOOK_RECALL_SEARCH_CHARS,
        max_session_events=3,
    )
    results = _trim_hook_items(_filter_hook_items(results), limit=limit, max_chars=max_chars)
    if results:
        return format_context(results)

    fallback_results = collect_markdown_context(
        query=query,
        repo=repo,
        global_memory_path=config.global_memory_path,
        workspace_root=config.workspace_root,
        repo_names=config.repo_names,
        limit=HOOK_RECALL_SEARCH_LIMIT,
        max_chars=HOOK_RECALL_SEARCH_CHARS,
    )
    fallback_results = _trim_hook_items(_filter_hook_items(fallback_results), limit=limit, max_chars=max_chars)
    if not fallback_results:
        return ""
    return format_context(fallback_results, fallback=True)


def format_context(results: list[MemoryItem] | list[MarkdownContextItem], *, fallback: bool = False) -> str:
    lines = [
        "<memory-context>",
        "[System note: recalled memory context from codex-memory, not new user input.]"
        if not fallback
        else "[System note: fallback Markdown memory context, not new user input.]",
    ]
    for item in results:
        lines.append(f"- [{item.bank_id}/{item.kind}] {item.content}")
    lines.append("</memory-context>")
    return "\n".join(lines)


def _filter_hook_items(
    items: list[MemoryItem] | list[MarkdownContextItem],
) -> list[MemoryItem] | list[MarkdownContextItem]:
    return [item for item in items if not _is_boilerplate(item.content)]


def _trim_hook_items(
    items: list[MemoryItem] | list[MarkdownContextItem],
    *,
    limit: int,
    max_chars: int,
) -> list[MemoryItem] | list[MarkdownContextItem]:
    output = []
    total = 0
    for item in items:
        projected = total + len(item.content)
        if output and projected > max_chars:
            break
        output.append(item)
        total = projected
        if len(output) >= limit:
            break
    return output


def _is_boilerplate(content: str) -> bool:
    lowered = content.lower()
    return any(marker.lower() in lowered for marker in _BOILERPLATE_MARKERS)


def _additional_context_payload(hook_event_name: str, context: str) -> dict[str, Any]:
    if not context:
        return _continue_payload(hook_event_name)
    return {
        "continue": True,
        "hookSpecificOutput": {
            "hookEventName": hook_event_name,
            "additionalContext": context,
        },
    }


def _continue_payload(hook_event_name: str, **extra: Any) -> dict[str, Any]:
    hook_output: dict[str, Any] = {"hookEventName": hook_event_name}
    hook_output.update(extra)
    return {"continue": True, "hookSpecificOutput": hook_output}


def _stop_continue_payload() -> dict[str, Any]:
    return {"continue": True, "suppressOutput": True}


def loads_hook_payload(raw: str) -> dict[str, Any]:
    if not raw.strip():
        return {}
    data = json.loads(raw)
    if not isinstance(data, dict):
        raise ValueError("hook payload must be a JSON object")
    return data
