# Memory（memory）

## 定义

本文件是 `memory` 的仓库级长期工程记忆。

这里只记录 `memory` 特有、可复用、能避免同类问题重复发生的稳定教训、失败模式、根因、预防动作与验证要求。若本次暴露的是指令误用与正确用法，也应记录在这里。merge 前必须回看并按需更新，但平时一旦确认某条教训稳定成立，也应直接补入，不必等到 merge 当下；工作区通用规则仍以工作区根 `AGENTS.md` 为准，这里不复制跨仓通用条目。

## Active Memory

### 1. 合并前必须完成复盘落盘

- 适用范围：所有准备进入 `main` 的变更。
- 问题模式：问题只在聊天或脑中复盘，没有进入仓库真源，下次又重复踩坑。
- 根因：复盘结论没有挂到合并路径上，也没有落到可执行检查。
- 预防动作：使用 `$merge-retro-guard` 更新本文件，必要时补 `scripts/pre_merge_gate.sh`、`docs/ARCHITECTURE.md` 与 `docs/JOBS_DONE.md`。
- 合并前验证：确认本文件已覆盖本次新增的稳定教训，并且仓库 pre-merge gate 已通过。

### 2. Hook 输出必须按事件 schema 分流

- 适用范围：`src/codex_memory/hooks.py` 中所有 Codex lifecycle hook 输出。
- 问题模式：把 `SessionStart` / `UserPromptSubmit` 的 `hookSpecificOutput` 输出形状复用到 `Stop`，会触发 Codex `stop.command.output` 的 `additionalProperties: false` 校验并报 invalid stop hook JSON output。
- 根因：不同 hook event 的 stdout schema 不同，`Stop` 只允许 `continue`、`decision`、`reason`、`stopReason`、`suppressOutput`、`systemMessage` 等顶层字段；调试元数据不能放进 stdout。
- 预防动作：`Stop` 只输出 Codex 允许的最小 JSON，保留统计与诊断只能写入测试断言、stderr 或内部存储，不能新增未登记顶层字段。
- 合并前验证：运行 `uv run --python 3.11 python -m pytest -q`，并用真实配置 smoke `codex-memory hook stop`，确认 `transcript_path: null` 与有效 transcript 都返回合法 JSON。

### 3. Hook 输入路径必须先验证为文件

- 适用范围：所有从 Codex hook payload 读取本地路径并进一步解析的代码。
- 问题模式：`transcript_path: null` 或空字符串被转成 `Path("") == "."`，目录存在但不可作为 transcript 读取，导致 hook 抛异常且 stdout 不是合法 JSON。
- 根因：只检查 `exists()` 不足以区分缺失值、目录与真实文件。
- 预防动作：解析 transcript 前使用 `Path.is_file()` 作为快速失败条件；缺失、空值、目录都按无 transcript 处理并返回合法 hook JSON。
- 合并前验证：测试覆盖 `transcript_path: None`，并运行真实配置 smoke。

### 4. memory dream 的主入口必须是 CLI 报告，不再人工遍历 Markdown 当主流程

- 适用范围：`codex-memory dream-report`、daily memory dream automation、`memory-dream` skill，以及任何周期性整理记忆的流程。
- 问题模式：如果 dream 继续先人工遍历全局 `memory.md`、工作区 `AGENTS.md` 和各仓 `docs/MEMORY.md`，SQLite 里的候选、retained session events、imported-event 噪声和索引健康就会变成旁路，最终无法退役 Markdown 真源。
- 根因：旧 dream 流程把 Markdown 当长期真源，把 `codex-memory` 只当辅助召回层；这和 CLI-first 迁移目标冲突。
- 预防动作：周期整理必须先运行 `codex-memory dream-report --json`，并以其中的 `status`、`seed`、`context`、`candidates` 与 `imported_events` 作为日报指标和决策入口。Markdown 只作为 legacy import/export 与必要人工审计材料，不再作为主审查面。
- 合并前验证：`uv run --python 3.11 python -m pytest -q tests/test_cli.py -k dream_report` 通过，并用本机配置 smoke `uv run --python 3.11 codex-memory dream-report --config "${CODEX_HOME}/memory/config.toml" --repo memory --query "memory dream cli" --json`。

### 5. 会话事件只能归档，不得进入长期召回索引

- 适用范围：`MemoryStore.retain_session`、Codex hook stop retain、`import-conversations` 和 `imported-events prune`。
- 问题模式：把每条 user/assistant transcript 片段写成 `memory_items.kind = session_event`，会让过程性中间状态、工具进度和用户临时提示淹没 durable `preference`、`constraint`、`lesson`。
- 根因：把会话归档表 `sessions/session_events` 和长期召回索引 `memory_items` 混成同一个写面，导致 recall 既要服务长期记忆，又要背负原始对话检索。
- 预防动作：`retain_session` 只把 transcript 写入 `sessions/session_events` 作为审计归档；只有人工或自动抽取出的 `candidate` 可以进入 `memory_items`，等待 promote/reject。`imported-events prune` 只保留 legacy `session_event` 清理能力，不应成为新写入路径。
- 合并前验证：测试必须断言 hook/import 后 `session_events` 有归档记录，但 `memory_items` 中 `kind = session_event` 为 `0`；同时保留 legacy prune 测试覆盖旧 `session_event` item。

### 6. runtime recall 必须基于已刷新官方记忆运行

- 适用范围：`seed`、`context`、`dream-report`、Hook 注入链路。
- 问题模式：若 `recall` 仍把 Markdown 作为并列运行时源，官方记忆上游将与本地运行时行为脱节，迁移指标失真。
- 根因：运行时路径已经切为官方 `official_memories_dir`，继续容许 Markdown 回退会造成重复/冲突的真源语义。
- 预防动作：
  - `seed`、`context`、`dream-report`、recall-injection hooks（`session-start`/`user-prompt-submit`）负责刷新官方 `official_memories_dir`，写入 SQLite 索引。
  - `recall` 只读取 SQLite，不执行 Markdown fallback；Markdown 仅保留导入导出与人工审计用途。
- 合并前验证：`uv run --python 3.11 python -m pytest -q tests/test_cli.py -k fallback` 与 `context --json` 相关场景通过，确认无 Markdown fallback 的可观察表现。
