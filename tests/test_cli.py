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
        ("retain-session", "--help"),
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
