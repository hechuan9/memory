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
