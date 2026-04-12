import json
import subprocess
import sys


def run_cli(*args, input_text=None, cwd=None):
    return subprocess.run(
        [sys.executable, "-m", "codex_memory.cli", *args],
        cwd=cwd,
        input=input_text,
        capture_output=True,
        text=True,
        check=False,
    )


def test_all_help_commands_run():
    for args in [
        ("--help",),
        ("seed", "--help"),
        ("recall", "--help"),
        ("context", "--help"),
        ("hook", "--help"),
        ("retain-session", "--help"),
        ("import-conversations", "--help"),
        ("imported-events", "--help"),
        ("candidates", "--help"),
        ("skill-candidates", "--help"),
        ("status", "--help"),
    ]:
        result = run_cli(*args)
        assert result.returncode == 0, result.stderr
        assert "codex-memory" in result.stdout


def test_seed_and_recall_json_with_fixture_config(tmp_path):
    workspace = tmp_path / "workspace"
    repo = workspace / "model"
    repo_docs = repo / "docs"
    repo_docs.mkdir(parents=True)
    global_memory = tmp_path / "memory.md"
    db_path = tmp_path / "memory.sqlite3"
    config = tmp_path / "config.toml"

    global_memory.write_text("- Use Chinese for replies.\n", encoding="utf-8")
    (workspace / "AGENTS.md").write_text("- Use uv for Python commands.\n", encoding="utf-8")
    (repo_docs / "MEMORY.md").write_text("- Model workflows read docs/ENVIRONMENT.md first.\n", encoding="utf-8")
    config.write_text(
        f"""
data_dir = "{tmp_path.as_posix()}"
database_path = "{db_path.as_posix()}"
global_memory_path = "{global_memory.as_posix()}"
workspace_root = "{workspace.as_posix()}"
repo_names = ["model"]
""".strip(),
        encoding="utf-8",
    )

    seed = run_cli("seed", "--config", str(config), "--json")
    assert seed.returncode == 0, seed.stderr

    recall = run_cli(
        "recall",
        "--config",
        str(config),
        "--repo",
        "model",
        "--query",
        "model uv environment",
        "--json",
    )
    assert recall.returncode == 0, recall.stderr
    payload = json.loads(recall.stdout)
    assert payload["results"][0]["bank_id"] == "repo:model"


def test_context_uses_recall_before_markdown_fallback(tmp_path):
    workspace = tmp_path / "workspace"
    repo = workspace / "backend"
    repo_docs = repo / "docs"
    repo_docs.mkdir(parents=True)
    global_memory = tmp_path / "memory.md"
    db_path = tmp_path / "memory.sqlite3"
    config = tmp_path / "config.toml"

    global_memory.write_text("- Use Chinese for replies.\n", encoding="utf-8")
    (workspace / "AGENTS.md").write_text("- Use uv for Python commands.\n", encoding="utf-8")
    (repo_docs / "MEMORY.md").write_text("- Backend changes run pre_merge_gate.\n", encoding="utf-8")
    config.write_text(
        f"""
data_dir = "{tmp_path.as_posix()}"
database_path = "{db_path.as_posix()}"
global_memory_path = "{global_memory.as_posix()}"
workspace_root = "{workspace.as_posix()}"
repo_names = ["backend"]
""".strip(),
        encoding="utf-8",
    )
    assert run_cli("seed", "--config", str(config), "--json").returncode == 0

    result = run_cli(
        "context",
        "--config",
        str(config),
        "--repo",
        "backend",
        "--query",
        "backend pre_merge_gate",
        "--json",
    )

    assert result.returncode == 0, result.stderr
    payload = json.loads(result.stdout)
    assert payload["mode"] == "recall"
    assert payload["results"][0]["bank_id"] == "repo:backend"


def test_context_falls_back_to_markdown_when_recall_is_empty(tmp_path):
    workspace = tmp_path / "workspace"
    repo = workspace / "backend"
    repo_docs = repo / "docs"
    repo_docs.mkdir(parents=True)
    global_memory = tmp_path / "memory.md"
    config = tmp_path / "config.toml"

    global_memory.write_text("- Use Chinese for replies.\n", encoding="utf-8")
    (workspace / "AGENTS.md").write_text("- Use uv for Python commands.\n", encoding="utf-8")
    (repo_docs / "MEMORY.md").write_text("- Backend changes run pre_merge_gate.\n", encoding="utf-8")
    config.write_text(
        f"""
data_dir = "{tmp_path.as_posix()}"
database_path = "{(tmp_path / "memory.sqlite3").as_posix()}"
global_memory_path = "{global_memory.as_posix()}"
workspace_root = "{workspace.as_posix()}"
repo_names = ["backend"]
""".strip(),
        encoding="utf-8",
    )

    result = run_cli(
        "context",
        "--config",
        str(config),
        "--repo",
        "backend",
        "--query",
        "backend pre_merge_gate",
        "--json",
    )

    assert result.returncode == 0, result.stderr
    payload = json.loads(result.stdout)
    assert payload["mode"] == "fallback-markdown"
    assert payload["results"][0]["bank_id"] == "repo:backend"


def test_hook_session_start_emits_additional_context(tmp_path):
    workspace = tmp_path / "workspace"
    repo = workspace / "backend"
    repo_docs = repo / "docs"
    repo_docs.mkdir(parents=True)
    global_memory = tmp_path / "memory.md"
    config = tmp_path / "config.toml"

    global_memory.write_text("- Always reply in Chinese.\n", encoding="utf-8")
    (workspace / "AGENTS.md").write_text("- Use uv for Python commands.\n", encoding="utf-8")
    (repo_docs / "MEMORY.md").write_text("- Backend changes run pre_merge_gate.\n", encoding="utf-8")
    config.write_text(
        f"""
data_dir = "{tmp_path.as_posix()}"
database_path = "{(tmp_path / "memory.sqlite3").as_posix()}"
global_memory_path = "{global_memory.as_posix()}"
workspace_root = "{workspace.as_posix()}"
repo_names = ["backend"]
""".strip(),
        encoding="utf-8",
    )

    result = run_cli(
        "hook",
        "session-start",
        "--config",
        str(config),
        input_text=json.dumps({"hook_event_name": "SessionStart", "cwd": str(repo), "source": "startup"}),
    )

    assert result.returncode == 0, result.stderr
    payload = json.loads(result.stdout)
    context = payload["hookSpecificOutput"]["additionalContext"]
    assert payload["hookSpecificOutput"]["hookEventName"] == "SessionStart"
    assert "recalled memory context" in context
    assert "Backend changes run pre_merge_gate" in context


def test_hook_user_prompt_submit_uses_prompt_as_query(tmp_path):
    workspace = tmp_path / "workspace"
    repo = workspace / "model"
    repo_docs = repo / "docs"
    repo_docs.mkdir(parents=True)
    global_memory = tmp_path / "memory.md"
    config = tmp_path / "config.toml"

    global_memory.write_text("- Keep replies concise.\n", encoding="utf-8")
    (repo_docs / "MEMORY.md").write_text("- Model runs must use AWS training pool.\n", encoding="utf-8")
    config.write_text(
        f"""
data_dir = "{tmp_path.as_posix()}"
database_path = "{(tmp_path / "memory.sqlite3").as_posix()}"
global_memory_path = "{global_memory.as_posix()}"
workspace_root = "{workspace.as_posix()}"
repo_names = ["model"]
""".strip(),
        encoding="utf-8",
    )

    result = run_cli(
        "hook",
        "user-prompt-submit",
        "--config",
        str(config),
        input_text=json.dumps(
            {
                "hook_event_name": "UserPromptSubmit",
                "cwd": str(repo),
                "prompt": "start model training",
            }
        ),
    )

    assert result.returncode == 0, result.stderr
    payload = json.loads(result.stdout)
    context = payload["hookSpecificOutput"]["additionalContext"]
    assert payload["hookSpecificOutput"]["hookEventName"] == "UserPromptSubmit"
    assert "Model runs must use AWS training pool" in context


def test_hook_user_prompt_submit_falls_back_for_chinese_prompt(tmp_path):
    workspace = tmp_path / "workspace"
    repo = workspace / "model"
    repo_docs = repo / "docs"
    repo_docs.mkdir(parents=True)
    global_memory = tmp_path / "memory.md"
    config = tmp_path / "config.toml"

    global_memory.write_text("- Keep replies concise.\n", encoding="utf-8")
    (repo_docs / "MEMORY.md").write_text("- Model runs must use AWS training pool.\n", encoding="utf-8")
    config.write_text(
        f"""
data_dir = "{tmp_path.as_posix()}"
database_path = "{(tmp_path / "memory.sqlite3").as_posix()}"
global_memory_path = "{global_memory.as_posix()}"
workspace_root = "{workspace.as_posix()}"
repo_names = ["model"]
""".strip(),
        encoding="utf-8",
    )

    result = run_cli(
        "hook",
        "user-prompt-submit",
        "--config",
        str(config),
        input_text=json.dumps(
            {
                "hook_event_name": "UserPromptSubmit",
                "cwd": str(repo),
                "prompt": "启动训练前要注意什么",
            }
        ),
    )

    assert result.returncode == 0, result.stderr
    payload = json.loads(result.stdout)
    context = payload["hookSpecificOutput"]["additionalContext"]
    assert "Model runs must use AWS training pool" in context


def test_hook_user_prompt_submit_filters_boilerplate_and_caps_context(tmp_path):
    workspace = tmp_path / "workspace"
    repo = workspace / "model"
    repo_docs = repo / "docs"
    repo_docs.mkdir(parents=True)
    global_memory = tmp_path / "memory.md"
    config = tmp_path / "config.toml"

    global_memory.write_text("- Keep replies concise.\n", encoding="utf-8")
    (repo_docs / "MEMORY.md").write_text(
        "\n".join(
            [
                "- 本文件是 `model` 的仓库级长期工程记忆。",
                "- 这里只记录 `model` 特有、可复用、能避免同类问题重复发生的稳定教训。",
                "- Model training starts from docs/ENVIRONMENT.md and uses AWS training pool.",
                "- Model publish checks must compare evaluation summaries before promotion.",
                "- Model container paths must point at /workspace/model.",
                "- Model cleanup must preserve selected artifacts.",
                "- Model release notes must mention the selected model version.",
                "- Model fallback rules must not hide invalid action failures.",
                "- Model dataset changes must update architecture docs.",
                "- Model smoke tests must finish before promotion.",
            ]
        )
        + "\n",
        encoding="utf-8",
    )
    config.write_text(
        f"""
data_dir = "{tmp_path.as_posix()}"
database_path = "{(tmp_path / "memory.sqlite3").as_posix()}"
global_memory_path = "{global_memory.as_posix()}"
workspace_root = "{workspace.as_posix()}"
repo_names = ["model"]
""".strip(),
        encoding="utf-8",
    )

    result = run_cli(
        "hook",
        "user-prompt-submit",
        "--config",
        str(config),
        input_text=json.dumps(
            {
                "hook_event_name": "UserPromptSubmit",
                "cwd": str(repo),
                "prompt": "start model training",
            }
        ),
    )

    assert result.returncode == 0, result.stderr
    context = json.loads(result.stdout)["hookSpecificOutput"]["additionalContext"]
    memory_lines = [line for line in context.splitlines() if line.startswith("- ")]
    assert len(memory_lines) <= 6
    assert "本文件是" not in context
    assert "这里只记录" not in context
    assert len(context) <= 2200
    assert "Model training starts from docs/ENVIRONMENT.md" in context


def test_hook_stop_retains_transcript_session(tmp_path):
    config = tmp_path / "config.toml"
    transcript = tmp_path / "session.jsonl"
    config.write_text(
        f'data_dir = "{tmp_path.as_posix()}"\ndatabase_path = "{(tmp_path / "memory.sqlite3").as_posix()}"\n',
        encoding="utf-8",
    )
    _write_session(
        transcript,
        cwd="/workspace/climamind/backend",
        messages=[
            ("user", "Remember that backend deploys read docs/ENVIRONMENT.md first."),
            ("assistant", "I will use that as the deploy starting point."),
        ],
    )

    result = run_cli(
        "hook",
        "stop",
        "--config",
        str(config),
        input_text=json.dumps({"hook_event_name": "Stop", "cwd": "/workspace/climamind/backend", "transcript_path": str(transcript)}),
    )

    assert result.returncode == 0, result.stderr
    payload = json.loads(result.stdout)
    assert payload["continue"] is True
    assert payload["hookSpecificOutput"]["hookEventName"] == "Stop"
    assert payload["hookSpecificOutput"]["retained"]["events_written"] == 2

    recall = run_cli(
        "recall",
        "--config",
        str(config),
        "--repo",
        "backend",
        "--query",
        "backend deploy environment",
        "--json",
    )
    assert recall.returncode == 0, recall.stderr
    assert "backend deploys read docs/ENVIRONMENT.md first" in recall.stdout


def test_retain_session_cli_writes_candidate(tmp_path):
    config = tmp_path / "config.toml"
    db_path = tmp_path / "memory.sqlite3"
    config.write_text(
        f'data_dir = "{tmp_path.as_posix()}"\ndatabase_path = "{db_path.as_posix()}"\n',
        encoding="utf-8",
    )
    payload = {
        "repo": "backend",
        "cwd": "/workspace/backend",
        "summary": "Backend deploy workflow discussion.",
        "events": [{"role": "user", "content": "Deploy backend"}],
        "candidates": [
            {
                "kind": "workflow",
                "content": "Backend deploy work should read docs/ENVIRONMENT.md.",
                "evidence": "Session summary",
                "tags": ["repo:backend"],
            }
        ],
    }

    retain = run_cli(
        "retain-session",
        "--config",
        str(config),
        "--stdin-json",
        input_text=json.dumps(payload),
    )
    assert retain.returncode == 0, retain.stderr

    candidates = run_cli("candidates", "list", "--config", str(config), "--repo", "backend", "--json")
    assert candidates.returncode == 0, candidates.stderr
    output = json.loads(candidates.stdout)
    assert output["candidates"][0]["kind"] == "workflow"


def test_import_conversations_cli_dry_run_is_default(tmp_path):
    config = tmp_path / "config.toml"
    db_path = tmp_path / "memory.sqlite3"
    archive = tmp_path / "archived_sessions"
    archive.mkdir()
    config.write_text(
        f'data_dir = "{tmp_path.as_posix()}"\ndatabase_path = "{db_path.as_posix()}"\n',
        encoding="utf-8",
    )
    _write_session(
        archive / "rollout-sample.jsonl",
        cwd="/workspace/climamind/backend",
        messages=[
            ("user", "Before backend changes, read docs/ENVIRONMENT.md."),
            ("assistant", "I will check the environment guide first."),
        ],
    )

    result = run_cli(
        "import-conversations",
        "--config",
        str(config),
        "--input-dir",
        str(archive),
        "--json",
    )

    assert result.returncode == 0, result.stderr
    payload = json.loads(result.stdout)
    assert payload["mode"] == "dry-run"
    assert payload["would_write_sessions"] == 1
    assert payload["sessions_written"] == 0


def test_import_conversations_cli_rejects_write_with_dry_run(tmp_path):
    config = tmp_path / "config.toml"
    archive = tmp_path / "archived_sessions"
    archive.mkdir()
    config.write_text(f'data_dir = "{tmp_path.as_posix()}"\n', encoding="utf-8")

    result = run_cli(
        "import-conversations",
        "--config",
        str(config),
        "--input-dir",
        str(archive),
        "--write",
        "--dry-run",
    )

    assert result.returncode == 1
    assert "--write and --dry-run cannot be used together" in result.stderr


def test_imported_events_prune_cli_dry_run(tmp_path):
    config = tmp_path / "config.toml"
    config.write_text(
        f'data_dir = "{tmp_path.as_posix()}"\ndatabase_path = "{(tmp_path / "memory.sqlite3").as_posix()}"\n',
        encoding="utf-8",
    )
    retained = run_cli(
        "retain-session",
        "--config",
        str(config),
        "--stdin-json",
        input_text=json.dumps(
            {
                "repo": "automation",
                "summary": "Imported noisy event",
                "events": [{"role": "user", "content": "Automation: daily memory dream\nAutomation ID: automation-3"}],
                "tags": ["imported", "codex-conversation"],
            }
        ),
    )
    assert retained.returncode == 0, retained.stderr

    result = run_cli("imported-events", "prune", "--config", str(config), "--json")

    assert result.returncode == 0, result.stderr
    payload = json.loads(result.stdout)
    assert payload["mode"] == "dry-run"
    assert payload["matched"] == 1
    assert payload["pruned"] == 0


def _write_session(path, *, cwd, messages):
    lines = [
        {
            "type": "session_meta",
            "timestamp": "2026-04-12T00:00:00Z",
            "payload": {"id": path.stem, "cwd": cwd},
        }
    ]
    for role, text in messages:
        lines.append(
            {
                "type": "response_item",
                "timestamp": "2026-04-12T00:00:00Z",
                "payload": {
                    "type": "message",
                    "role": role,
                    "content": [{"type": "input_text", "text": text}],
                },
            }
        )
    path.write_text("\n".join(json.dumps(line) for line in lines), encoding="utf-8")
