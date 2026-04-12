from __future__ import annotations

import os
import tomllib
from dataclasses import dataclass
from pathlib import Path
from typing import Any


DEFAULT_REPO_NAMES = [
    "automation",
    "attio-backup",
    "backend",
    "client",
    "climamind-deployments",
    "model",
    "pool-manager",
    "sales",
    "website",
]


@dataclass(frozen=True)
class MemoryConfig:
    data_dir: Path
    database_path: Path
    global_memory_path: Path | None = None
    workspace_root: Path | None = None
    repo_names: tuple[str, ...] = ()


def default_data_dir() -> Path:
    codex_home = os.environ.get("CODEX_HOME")
    if codex_home:
        return Path(codex_home).expanduser() / "memory"
    return Path.home() / ".codex" / "memory"


def load_config(path: str | Path | None = None) -> MemoryConfig:
    data: dict[str, Any] = {}
    if path:
        config_path = Path(path).expanduser()
    else:
        config_path = default_data_dir() / "config.toml"
    if config_path.exists():
        data = tomllib.loads(config_path.read_text(encoding="utf-8"))

    data_dir = Path(data.get("data_dir") or default_data_dir()).expanduser()
    database_path = Path(data.get("database_path") or data_dir / "memory.sqlite3").expanduser()
    global_memory_raw = data.get("global_memory_path")
    workspace_raw = data.get("workspace_root")
    repo_names = tuple(data.get("repo_names") or DEFAULT_REPO_NAMES)
    return MemoryConfig(
        data_dir=data_dir,
        database_path=database_path,
        global_memory_path=Path(global_memory_raw).expanduser() if global_memory_raw else None,
        workspace_root=Path(workspace_raw).expanduser() if workspace_raw else None,
        repo_names=repo_names,
    )
