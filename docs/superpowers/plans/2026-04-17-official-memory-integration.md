# 2026-04-17 官方记忆源接入收敛

## 目标

- 将官方 Codex Memories 明确为运行时上游来源，确认 Markdown 已退役为 fallback/复写 runtime source 的角色。
- 在文档中落地配置与治理约束，补齐任务痕迹。

## 变更

- [x] 更新 `README.md`：明确 official memories upstream、`context` 无 Markdown 回退、Markdown 仅遗留 import/export 与人工审计用途。
- [x] 更新 `examples/climamind.config.example.toml`：使用 `official_memories_dir`，保留 `global_memory_path` 与 `workspace_root` 为 legacy 标注路径。
- [x] 更新 `AGENTS.md`：调整设计边界为官方记忆上游 + SQLite CLI 主控、Markdown 非运行时回退。
- [x] 更新 `docs/TODO.md`：完成 Markdown 退役/启动 wrapper 相关项，其余未完成项保留。
- [x] 更新 `docs/JOBS_DONE.md`：新增 2026-04-17 文档更新任务记录。
- [x] 更新 `docs/MEMORY.md`：新增稳定教训，强调 recall 必须先 seed 官方记忆、Markdown 仅 legacy。
- [x] 新增 `docs/superpowers/plans/2026-04-17-official-memory-integration.md` 作为任务交付文档。

## 验证

- [x] `uv run --python 3.11 python -m pytest -q`
- [x] `./scripts/pre_merge_gate.sh`
- [x] `git diff --check`
