from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from codex_memory.store import MemoryStore


@dataclass(frozen=True)
class SeedStats:
    indexed_files: int
    indexed_items: int


def seed_markdown_sources(
    store: MemoryStore,
    *,
    global_memory_path: Path | None = None,
    workspace_root: Path | None = None,
    repo_names: list[str] | tuple[str, ...] = (),
) -> SeedStats:
    indexed_files = 0
    indexed_items = 0

    if global_memory_path and global_memory_path.exists():
        indexed_files += 1
        indexed_items += _seed_file(
            store,
            path=global_memory_path,
            bank_id="global",
            repo=None,
            kind="preference",
            tags=["scope:global"],
        )

    if workspace_root:
        agents_path = workspace_root / "AGENTS.md"
        if agents_path.exists():
            indexed_files += 1
            indexed_items += _seed_file(
                store,
                path=agents_path,
                bank_id="global",
                repo=None,
                kind="constraint",
                tags=["scope:global", "source:workspace-agents"],
            )
        for repo_name in repo_names:
            memory_path = workspace_root / repo_name / "docs" / "MEMORY.md"
            if not memory_path.exists():
                continue
            indexed_files += 1
            indexed_items += _seed_file(
                store,
                path=memory_path,
                bank_id=f"repo:{repo_name}",
                repo=repo_name,
                kind="lesson",
                tags=[f"repo:{repo_name}", "source:repo-memory"],
            )

    return SeedStats(indexed_files=indexed_files, indexed_items=indexed_items)


def _seed_file(
    store: MemoryStore,
    *,
    path: Path,
    bank_id: str,
    repo: str | None,
    kind: str,
    tags: list[str],
) -> int:
    count = 0
    for line_number, entry in _entries_from_markdown(path):
        store.upsert_item(
            bank_id=bank_id,
            repo=repo,
            kind=kind,
            status="active",
            content=entry,
            source_path=str(path),
            source_anchor=f"line:{line_number}",
            tags=tags,
        )
        count += 1
    return count


def _entries_from_markdown(path: Path) -> list[tuple[int, str]]:
    entries: list[tuple[int, str]] = []
    for line_number, raw_line in enumerate(path.read_text(encoding="utf-8").splitlines(), start=1):
        line = raw_line.strip()
        if not line or line.startswith("#"):
            continue
        if line.startswith("- "):
            line = line[2:].strip()
        if line:
            entries.append((line_number, line))
    return entries
