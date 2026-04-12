# AGENTS

## 语言与执行
- 全程使用中文交流。
- 本仓所有 Python、pytest、脚本命令统一使用 `uv`。
- 默认 Python 版本固定为 `3.11`。

## Public Repo 安全边界
- 本仓是 public git repo；不得提交本机 SQLite 记忆库、会话 transcript、日志、secrets、API key、私钥或 `.env` 内容。
- 示例配置只能放通用字段；具体私有路径只允许出现在用户本机未跟踪的 `config.toml`。
- 本仓不自动改写用户的全局 Markdown 记忆文件、任何仓库的 `docs/MEMORY.md` 或已安装 skills。

## 设计边界
- 不使用 MCP、Hindsight runtime、外部云记忆服务或 Codex 之外的本地模型服务。
- Markdown 记忆真源优先；本仓提供索引、召回、自动保留与候选生成。
- skill 候选只能写入候选目录，不得自动安装。

## 验证
- 初始化：`uv sync --python 3.11 --extra dev`
- 测试：`uv run --python 3.11 python -m pytest -q`
