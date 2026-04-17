from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path

from codex_memory.store import MemoryStore


TOP_LEVEL_SECTION_RE = re.compile(r"^\s*#{1,2}\s+")
CWD_RE = re.compile(r"^\s*cwd\s*:\s*(.+?)\s*$", re.IGNORECASE)


@dataclass(frozen=True)
class OfficialSeedStats:
    indexed_files: int
    indexed_items: int
    pruned_items: int = 0


def seed_official_memories(
    store: MemoryStore,
    *,
    memories_dir: Path | None,
    repo_names: list[str] | tuple[str, ...] = (),
) -> OfficialSeedStats:
    indexed_files = 0
    indexed_items = 0
    pruned_items = 0

    if memories_dir is None or not memories_dir.exists():
        return OfficialSeedStats(indexed_files=0, indexed_items=0, pruned_items=0)

    source_paths = [
        memories_dir / "raw_memories.md",
        memories_dir / "memory_summary.md",
        memories_dir / "MEMORY.md",
        *sorted((memories_dir / "rollout_summaries").glob("*.md")),
    ]

    for source_path in source_paths:
        if not source_path.exists():
            continue

        indexed_files += 1
        item_ids = _seed_source_file(
            store,
            path=source_path,
            repo_names=tuple(repo_names),
            force_global=source_path.name == "raw_memories.md",
        )
        indexed_items += len(item_ids)
        pruned_items += store.delete_source_items_except(source_path=str(source_path), keep_item_ids=item_ids)

    return OfficialSeedStats(
        indexed_files=indexed_files,
        indexed_items=indexed_items,
        pruned_items=pruned_items,
    )


def _seed_source_file(
    store: MemoryStore,
    *,
    path: Path,
    repo_names: tuple[str, ...],
    force_global: bool,
) -> list[str]:
    item_ids: list[str] = []

    for start_line, chunk in _section_chunks(path):
        content = chunk.strip()
        if not content:
            continue

        repo = _infer_repo_from_cwd(content, repo_names) if not force_global else None
        bank_id = f"repo:{repo}" if repo else "global"
        source_anchor = f"line:{start_line}"

        item_id = store.upsert_item(
            bank_id=bank_id,
            kind="official_memory",
            status="active",
            content=content,
            repo=repo,
            source_path=str(path),
            source_anchor=source_anchor,
            tags=_item_tags(repo),
        )
        item_ids.append(item_id)

    return item_ids


def _infer_repo_from_cwd(chunk: str, repo_names: tuple[str, ...]) -> str | None:
    cwd = _extract_cwd(chunk)
    if not cwd:
        return None

    normalized = Path(cwd).expanduser()
    parts = {part.lower() for part in normalized.parts}
    for repo_name in repo_names:
        if repo_name.lower() in parts:
            return repo_name
    return None


def _extract_cwd(chunk: str) -> str | None:
    for line in chunk.splitlines():
        match = CWD_RE.match(line)
        if match:
            return match.group(1)
    return None


def _item_tags(repo: str | None) -> list[str]:
    tags = ["source:official-codex-memory"]
    if repo:
        tags.append(f"repo:{repo}")
    return tags


def _section_chunks(path: Path) -> list[tuple[int, str]]:
    lines = path.read_text(encoding="utf-8").splitlines()
    raw_text = "\n".join(lines).strip()
    if not raw_text:
        return []

    chunks: list[tuple[int, list[str]]] = []
    current_start = 1
    current_lines: list[str] = []
    has_top_level_section = False

    for index, line in enumerate(lines, start=1):
        if TOP_LEVEL_SECTION_RE.match(line):
            if current_lines:
                chunks.append((current_start, current_lines))
            current_start = index
            current_lines = [line]
            has_top_level_section = True
        else:
            current_lines.append(line)

    if current_lines:
        chunks.append((current_start, current_lines))

    if not has_top_level_section:
        return [(1, raw_text)]

    return [(start, "\n".join(block).strip()) for start, block in chunks]
