import json
import sqlite3

from codex_memory.store import MemoryStore


def test_schema_initialization_is_idempotent(tmp_path):
    db_path = tmp_path / "memory.sqlite3"

    MemoryStore(db_path).initialize()
    MemoryStore(db_path).initialize()

    with sqlite3.connect(db_path) as connection:
        version = connection.execute("PRAGMA user_version").fetchone()[0]
        tables = {
            row[0]
            for row in connection.execute(
                "SELECT name FROM sqlite_master WHERE type IN ('table', 'virtual')"
            )
        }

    assert version == 1
    assert "memory_items" in tables
    assert "sessions" in tables
    assert "session_events" in tables
    assert "memory_items_fts" in tables


def test_upsert_item_is_idempotent_by_content_hash(tmp_path):
    store = MemoryStore(tmp_path / "memory.sqlite3")
    store.initialize()

    first = store.upsert_item(
        bank_id="global",
        kind="constraint",
        status="active",
        content="Use uv for Python commands.",
        source_path="/example/AGENTS.md",
        source_anchor="line:1",
        tags=["scope:global"],
    )
    second = store.upsert_item(
        bank_id="global",
        kind="constraint",
        status="active",
        content="Use uv for Python commands.",
        source_path="/example/AGENTS.md",
        source_anchor="line:1",
        tags=["scope:global"],
    )

    assert first == second
    assert store.count_items() == 1


def test_recall_prioritizes_repo_then_global_and_hides_candidates(tmp_path):
    store = MemoryStore(tmp_path / "memory.sqlite3")
    store.initialize()
    store.upsert_item(
        bank_id="global",
        kind="constraint",
        status="active",
        content="All Python commands should use uv.",
        tags=["scope:global"],
    )
    store.upsert_item(
        bank_id="repo:model",
        repo="model",
        kind="lesson",
        status="active",
        content="Before model training changes, read docs/ENVIRONMENT.md and docs/MEMORY.md.",
        tags=["repo:model"],
    )
    store.upsert_item(
        bank_id="repo:model",
        repo="model",
        kind="candidate",
        status="candidate",
        content="Candidate memory about temporary debugging state.",
        tags=["repo:model"],
    )

    results = store.recall("model training uv environment", repo="model", limit=10)

    assert [item.bank_id for item in results] == ["repo:model", "global"]
    assert all(item.status == "active" for item in results)


def test_recall_prioritizes_durable_memory_before_session_events(tmp_path):
    store = MemoryStore(tmp_path / "memory.sqlite3")
    store.initialize()
    store.upsert_item(
        bank_id="repo:backend",
        repo="backend",
        kind="session_event",
        status="active",
        content="backend ENVIRONMENT uv architecture pre_merge_gate " * 8,
        tags=["repo:backend", "imported", "codex-conversation"],
    )
    store.upsert_item(
        bank_id="repo:backend",
        repo="backend",
        kind="lesson",
        status="active",
        content="Backend changes must read docs/ENVIRONMENT.md and run pre_merge_gate.",
        source_path="/workspace/backend/docs/MEMORY.md",
        tags=["repo:backend", "source:repo-memory"],
    )

    results = store.recall("backend ENVIRONMENT uv architecture pre_merge_gate", repo="backend", limit=2)

    assert [item.kind for item in results] == ["lesson", "session_event"]


def test_recall_limits_session_event_supplements(tmp_path):
    store = MemoryStore(tmp_path / "memory.sqlite3")
    store.initialize()
    store.upsert_item(
        bank_id="repo:automation",
        repo="automation",
        kind="lesson",
        status="active",
        content="Automation memory dream should keep durable Markdown first.",
        tags=["repo:automation", "source:repo-memory"],
    )
    for index in range(5):
        store.upsert_item(
            bank_id="repo:automation",
            repo="automation",
            kind="session_event",
            status="active",
            content=f"Automation memory dream imported session event {index}.",
            tags=["repo:automation", "imported", "codex-conversation"],
        )

    results = store.recall("automation memory dream imported", repo="automation", limit=10, max_session_events=2)

    assert [item.kind for item in results].count("lesson") == 1
    assert [item.kind for item in results].count("session_event") == 2


def test_recall_can_include_candidates_when_requested(tmp_path):
    store = MemoryStore(tmp_path / "memory.sqlite3")
    store.initialize()
    store.upsert_item(
        bank_id="repo:model",
        repo="model",
        kind="candidate",
        status="candidate",
        content="Candidate memory about model workflow.",
        tags=["repo:model"],
    )

    results = store.recall("candidate model workflow", repo="model", include_candidates=True)

    assert [item.status for item in results] == ["candidate"]


def test_retain_session_writes_events_and_candidates(tmp_path):
    store = MemoryStore(tmp_path / "memory.sqlite3")
    store.initialize()

    session_id = store.retain_session(
        repo="backend",
        cwd="/workspace/backend",
        summary="Investigated backend deployment.",
        events=[
            {"role": "user", "content": "Fix backend deploy"},
            {"role": "assistant", "content": "Updated runbook candidate"},
        ],
        candidates=[
            {
                "kind": "workflow",
                "content": "Backend deploy changes should check docs/ENVIRONMENT.md first.",
                "evidence": "Session summary",
                "tags": ["repo:backend"],
            }
        ],
    )

    assert session_id
    assert store.count_sessions() == 1
    assert store.count_events(session_id) == 2
    candidates = store.list_candidates(repo="backend")
    assert len(candidates) == 1
    assert json.loads(candidates[0].tags_json) == ["repo:backend"]
