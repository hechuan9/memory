from codex_memory.sources import seed_markdown_sources
from codex_memory.store import MemoryStore


def test_seed_markdown_sources_indexes_global_workspace_and_repo_memories(tmp_path):
    global_memory = tmp_path / "memory.md"
    workspace = tmp_path / "workspace"
    repo = workspace / "model"
    repo_docs = repo / "docs"
    repo_docs.mkdir(parents=True)
    global_memory.write_text("# Long memory\n\n- Prefer Chinese.\n", encoding="utf-8")
    (workspace / "AGENTS.md").write_text("- Use git worktrees.\n", encoding="utf-8")
    (repo_docs / "MEMORY.md").write_text("- Model training uses uv.\n", encoding="utf-8")

    store = MemoryStore(tmp_path / "memory.sqlite3")
    store.initialize()
    stats = seed_markdown_sources(
        store,
        global_memory_path=global_memory,
        workspace_root=workspace,
        repo_names=["model"],
    )

    assert stats.indexed_files == 3
    assert store.count_items() == 3
    results = store.recall("training uv", repo="model")
    assert results[0].bank_id == "repo:model"
    assert "Model training uses uv" in results[0].content
