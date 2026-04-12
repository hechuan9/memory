from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any

from codex_memory.retain import UnsafeContentError, validate_retain_content
from codex_memory.store import MemoryStore


IMPORT_TAGS = ("imported", "codex-conversation")


@dataclass(frozen=True)
class ConversationEvent:
    role: str
    content: str


@dataclass(frozen=True)
class ParsedConversation:
    path: Path
    session_id: str
    repo: str | None
    cwd: str | None
    summary: str
    events: tuple[ConversationEvent, ...]
    unsafe_events: int
    noisy_events: int


@dataclass
class ConversationImportStats:
    files_seen: int = 0
    files_selected: int = 0
    sessions_importable: int = 0
    events_seen: int = 0
    safe_events: int = 0
    unsafe_events: int = 0
    noisy_events: int = 0
    sessions_written: int = 0
    events_written: int = 0
    would_write_sessions: int = 0
    would_write_events: int = 0
    imported_session_ids: list[str] = field(default_factory=list)


@dataclass(frozen=True)
class PruneImportedEventsStats:
    matched: int
    pruned: int
    item_ids: list[str]


def import_codex_conversations(
    store: MemoryStore,
    *,
    input_dir: Path,
    since_days: int = 30,
    repo: str | None = "auto",
    write: bool = False,
    max_files: int = 25,
    max_events_per_session: int = 80,
    max_event_chars: int = 2000,
) -> ConversationImportStats:
    stats = ConversationImportStats()
    cutoff = datetime.now(timezone.utc) - timedelta(days=since_days)
    paths = sorted(input_dir.glob("*.jsonl"), key=lambda path: path.stat().st_mtime, reverse=True)
    stats.files_seen = len(paths)

    selected = [path for path in paths if _mtime(path) >= cutoff][:max_files]
    stats.files_selected = len(selected)
    for path in selected:
        parsed = parse_codex_conversation(
            path,
            repo=repo,
            max_events=max_events_per_session,
            max_event_chars=max_event_chars,
        )
        stats.events_seen += len(parsed.events) + parsed.unsafe_events + parsed.noisy_events
        stats.safe_events += len(parsed.events)
        stats.unsafe_events += parsed.unsafe_events
        stats.noisy_events += parsed.noisy_events
        if not parsed.events:
            continue
        stats.sessions_importable += 1
        stats.would_write_sessions += 1
        stats.would_write_events += len(parsed.events)
        if not write:
            continue
        session_id = store.retain_session(
            repo=parsed.repo,
            cwd=parsed.cwd,
            summary=parsed.summary,
            events=[{"role": event.role, "content": event.content} for event in parsed.events],
            candidates=[],
            tags=list(IMPORT_TAGS),
            session_id=parsed.session_id,
        )
        stats.sessions_written += 1
        stats.events_written += len(parsed.events)
        stats.imported_session_ids.append(session_id)
    return stats


def prune_imported_events(store: MemoryStore, *, apply: bool = False, limit: int = 500) -> PruneImportedEventsStats:
    items = store.list_imported_session_event_items(limit=limit)
    item_ids = [item.id for item in items if is_context_noise(item.content) or is_context_noise(item.evidence)]
    pruned = store.delete_items(item_ids) if apply else 0
    return PruneImportedEventsStats(matched=len(item_ids), pruned=pruned, item_ids=item_ids)


def parse_codex_conversation(
    path: Path,
    *,
    repo: str | None,
    max_events: int,
    max_event_chars: int,
) -> ParsedConversation:
    cwd: str | None = None
    source_session_id: str | None = None
    events: list[ConversationEvent] = []
    unsafe_events = 0
    noisy_events = 0

    for raw_line in path.read_text(encoding="utf-8").splitlines():
        if not raw_line.strip():
            continue
        try:
            record = json.loads(raw_line)
        except json.JSONDecodeError:
            unsafe_events += 1
            continue
        payload = record.get("payload") if isinstance(record, dict) else None
        if not isinstance(payload, dict):
            continue
        if record.get("type") == "session_meta":
            cwd = str(payload.get("cwd") or "") or cwd
            source_session_id = str(payload.get("id") or "") or source_session_id
            continue
        if record.get("type") != "response_item":
            continue
        role = payload.get("role")
        if role not in {"user", "assistant"}:
            continue
        content = _extract_text(payload.get("content")).strip()
        if not content:
            continue
        if is_context_noise(content):
            noisy_events += 1
            continue
        try:
            validate_retain_content(content, max_chars=max(len(content), 1))
        except UnsafeContentError:
            unsafe_events += 1
            continue
        events.append(ConversationEvent(role=role, content=_trim(content, max_event_chars)))
        if len(events) >= max_events:
            break

    inferred_repo = _infer_repo(cwd) if repo == "auto" else repo
    session_id = _import_session_id(source_session_id or path.stem)
    return ParsedConversation(
        path=path,
        session_id=session_id,
        repo=inferred_repo,
        cwd=cwd,
        summary=_summary(path, events),
        events=tuple(events),
        unsafe_events=unsafe_events,
        noisy_events=noisy_events,
    )


def stats_payload(stats: ConversationImportStats, *, write: bool) -> dict[str, Any]:
    return {
        "mode": "write" if write else "dry-run",
        "files_seen": stats.files_seen,
        "files_selected": stats.files_selected,
        "sessions_importable": stats.sessions_importable,
        "events_seen": stats.events_seen,
        "safe_events": stats.safe_events,
        "unsafe_events": stats.unsafe_events,
        "noisy_events": stats.noisy_events,
        "would_write_sessions": stats.would_write_sessions,
        "would_write_events": stats.would_write_events,
        "sessions_written": stats.sessions_written,
        "events_written": stats.events_written,
        "imported_session_ids": stats.imported_session_ids,
    }


def _extract_text(content: Any) -> str:
    if isinstance(content, str):
        return content
    if not isinstance(content, list):
        return ""
    parts: list[str] = []
    for item in content:
        if not isinstance(item, dict):
            continue
        text = item.get("text")
        if isinstance(text, str):
            parts.append(text)
    return "\n\n".join(parts)


def is_context_noise(content: str) -> bool:
    text = content.strip()
    if text.startswith("# AGENTS.md instructions") and "<INSTRUCTIONS>" in text:
        return True
    if text.startswith("Automation:") and "Automation ID:" in text:
        return True
    if text.startswith("Automation ID:"):
        return True
    return "::inbox-item{" in text


def _infer_repo(cwd: str | None) -> str | None:
    if not cwd:
        return None
    parts = Path(cwd).parts
    if "climamind" not in parts:
        return None
    index = parts.index("climamind")
    if index + 1 >= len(parts):
        return None
    return parts[index + 1]


def _import_session_id(source: str) -> str:
    digest = hashlib.sha256(source.encode("utf-8")).hexdigest()[:20]
    return f"import_{digest}"


def _summary(path: Path, events: list[ConversationEvent]) -> str:
    if not events:
        return f"Imported Codex conversation: {path.stem}"
    first_user = next((event.content for event in events if event.role == "user"), events[0].content)
    return _trim(first_user.replace("\n", " "), 240)


def _trim(text: str, max_chars: int) -> str:
    text = text.strip()
    if len(text) <= max_chars:
        return text
    return f"{text[: max_chars - 24].rstrip()} [truncated for import]"


def _mtime(path: Path) -> datetime:
    return datetime.fromtimestamp(path.stat().st_mtime, tz=timezone.utc)
