# MemRelay（忆桥）

[English](README.md) · 许可证：Apache-2.0 · 状态：**预览前（v0.1 开发中，私有）**

**让你所有的 AI 智能体共用一份个人记忆。** MemRelay 把 Claude Code、Cursor、Claude Desktop 等支持 MCP 的智能体接到同一个由你掌控的 Markdown 记忆库；每条记忆都有出处，每次写入都先进收件箱等你审核。

不重复造轮子：记忆库由 [Basic Memory](https://github.com/basicmachines-co/basic-memory) 管理，MemRelay 以独立程序方式通过 MCP stdio 调用它。MemRelay 补上现有项目没有组合起来的部分：

- **网关**：只暴露白名单工具（`get_profile`、`recall`、`read_memory`、`recent`、`propose_memory`）。智能体只能读已审核的记忆、提议新记忆；提议写入 `inbox/`，你批准前不会进入正式记忆。
- **接入（connect）**：在 Windows / macOS / Linux 上为各智能体写 MCP 配置，自动备份、一条命令回滚。
- **采集（capture）**：增量读取本地智能体历史（首个来源：Claude Code 会话日志），经可插拔抽取器（LLM 或离线规则桩）生成候选记忆。
- **审核（review）**：`memrelay inbox list / show / approve / reject`。
- **画像（profile）**：从已审核记忆生成精简核心画像，注入到不支持 MCP 的智能体。

快速开始与目录结构见英文 README。Basic Memory 为 AGPL-3.0-or-later，**不随本项目分发**，详见 `NOTICE`。
