import json
import sqlite3

from codex_memory.official import seed_official_memories
from codex_memory.store import MemoryStore


def test_seed_official_memories_indexes_raw_and_rollout_sources(tmp_path):
    memories_dir = tmp_path / "memories"
    memories_dir.mkdir()

    raw_memories = memories_dir / "raw_memories.md"
    rollout_dir = memories_dir / "rollout_summaries"
    rollout_dir.mkdir()
    rollout_summary = rollout_dir / "backend.md"

    raw_memories.write_text(
        """# Global memory\n\n- Remember to keep output concise.\n""",
        encoding="utf-8",
    )
    rollout_summary.write_text(
        """# Rollout summary\n\ncwd: /workspace/climamind/backend\n\n- Backend rollout completed on integration branch.\n""",
        encoding="utf-8",
    )

    store = MemoryStore(tmp_path / "memory.sqlite3")
    store.initialize()

    stats = seed_official_memories(
        store,
        memories_dir=memories_dir,
        repo_names=("backend", "model"),
    )

    assert stats.indexed_files == 2
    assert stats.indexed_items >= 2

    with sqlite3.connect(store.db_path) as connection:
        rows = connection.execute(
            "SELECT bank_id, repo, kind, source_path, tags_json FROM memory_items"
        ).fetchall()

    assert len({row[3] for row in rows}) == 2
    source_map = {row[3]: row for row in rows}

    raw_item = source_map[str(raw_memories)]
    assert raw_item[0] == "global"
    assert raw_item[2] == "official_memory"
    assert "source:official-codex-memory" in json.loads(raw_item[4])

    rollout_item = source_map[str(rollout_summary)]
    assert rollout_item[0] == "repo:backend"
    assert rollout_item[1] == "backend"


def test_seed_official_memories_missing_memories_dir_is_noop(tmp_path):
    store = MemoryStore(tmp_path / "memory.sqlite3")
    store.initialize()

    stats = seed_official_memories(store, memories_dir=tmp_path / "does-not-exist")

    assert stats.indexed_files == 0
    assert stats.indexed_items == 0
    assert stats.pruned_items == 0
    assert store.count_items() == 0


def test_seed_official_memories_falls_back_to_whole_file_chunk(tmp_path):
    memories_dir = tmp_path / "memories"
    memories_dir.mkdir()

    memory_summary = memories_dir / "memory_summary.md"
    memory_summary.write_text(
        "This memory summary has no headings and should still be indexed as one item.\n"
        "It contains long-form plain text for the fallback path.\n",
        encoding="utf-8",
    )

    store = MemoryStore(tmp_path / "memory.sqlite3")
    store.initialize()

    stats = seed_official_memories(store, memories_dir=memories_dir)

    assert stats.indexed_files == 1
    assert stats.indexed_items == 1
    rows = store._connect().execute(
        "SELECT bank_id, kind, content, tags_json FROM memory_items WHERE source_path = ?",
        (str(memory_summary),),
    ).fetchall()
    assert len(rows) == 1
    bank_id, kind, content, tags_json = rows[0]
    assert bank_id == "global"
    assert kind == "official_memory"
    assert "This memory summary" in content
    assert "source:official-codex-memory" in json.loads(tags_json)


def test_seed_official_memories_prunes_rows_for_removed_sources(tmp_path):
    memories_dir = tmp_path / "memories"
    rollout_dir = memories_dir / "rollout_summaries"
    rollout_dir.mkdir(parents=True)
    rollout_file = rollout_dir / "backend.md"
    rollout_file.write_text(
        """# Rollout backend\n\ncwd: /workspace/climamind/backend\n\n- Rollout completed.\n""",
        encoding="utf-8",
    )

    store = MemoryStore(tmp_path / "memory.sqlite3")
    store.initialize()

    first = seed_official_memories(
        store,
        memories_dir=memories_dir,
        repo_names=("backend",),
    )
    with store._connect() as connection:
        existing_rows = connection.execute(
            "SELECT source_path FROM memory_items WHERE kind = 'official_memory'",
        ).fetchall()
    assert first.indexed_files == 1
    assert first.indexed_items == 1
    assert len(existing_rows) == 1
    assert existing_rows[0][0] == str(rollout_file)

    rollout_file.unlink()
    second = seed_official_memories(
        store,
        memories_dir=memories_dir,
        repo_names=("backend",),
    )

    assert second.indexed_files == 0
    assert second.indexed_items == 0
    assert second.pruned_items == 1
    with store._connect() as connection:
        remaining_rows = connection.execute(
            "SELECT id FROM memory_items WHERE kind = 'official_memory'",
        ).fetchall()
    assert len(remaining_rows) == 0


def test_seed_official_memories_preserves_legacy_rows_with_same_source_path(tmp_path):
    memories_dir = tmp_path / "memories"
    memories_dir.mkdir()
    memory_file = memories_dir / "MEMORY.md"
    memory_file.write_text(
        """# Repo memory\n\n- Repo-level memory item.\n""",
        encoding="utf-8",
    )

    store = MemoryStore(tmp_path / "memory.sqlite3")
    store.initialize()
    legacy_id = store.upsert_item(
        bank_id="global",
        kind="lesson",
        status="active",
        content="legacy memory file content",
        source_path=str(memory_file),
        tags=["repo:model"],
    )

    first = seed_official_memories(store, memories_dir=memories_dir, repo_names=("backend",))

    with store._connect() as connection:
        remaining = {
            row["id"]: row["kind"]
            for row in connection.execute(
                "SELECT id, kind FROM memory_items WHERE source_path = ? ORDER BY id",
                (str(memory_file),),
            ).fetchall()
        }

    assert first.indexed_files == 1
    assert first.indexed_items == 1
    assert legacy_id in remaining
    assert remaining[legacy_id] == "lesson"
    assert len(remaining) == 2
    assert any(kind == "official_memory" for kind in remaining.values())
