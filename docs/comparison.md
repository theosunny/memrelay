# MemRelay vs OpenViking vs Supermemory vs Basic Memory vs Mem0

> **English summary.** MemRelay is a *relay + twin* for a person who already uses many off-the-shelf AI agents: one reviewed Markdown vault, connectors, capture/import, and `answer_as_me` / `draft_as_me`. OpenViking and Supermemory are *memory engines* (storage, extraction, retrieval). Basic Memory is the Markdown engine MemRelay already runs as a separate process. Mem0 is an in-app memory library for builders. **Recommendation:** keep MemRelay as the relay+twin layer; treat OpenViking / Supermemory / Basic Memory as optional backends behind a thin adapter — do not rebuild their retrieval stacks inside MemRelay. Sources cited below (checked 2026-10).

中文正文如下。

---

## 1. 各自解决什么问题

| 项目 | 一句话定位 | 主要用户 | 记忆存在哪 | 写入谁说了算 |
|---|---|---|---|---|
| **MemRelay（忆桥）** | 把你用的多个现成智能体接到**一份你拥有的记忆**上，并逐渐成为你的数字分身 | 同时用 Claude Code / Cursor / Codex 等的人 | 本机 Markdown vault（可 Git/Syncthing） | **人审核**：一切先进 `inbox/` |
| **[OpenViking](https://github.com/volcengine/OpenViking)** | 给智能体用的**上下文数据库**：知识、记忆、技能统一成可检索文件系统 | 做 agent / agent 团队的开发者与团队 | 服务端命名空间（`viking://…`）+ 会话分层 | 模型可直接调 `remember`；会话 commit 后后台抽取 |
| **[Supermemory](https://supermemory.ai/)** | 给 MCP 兼容助手用的**共享记忆 API / MCP** | 需要跨助手共享上下文的个人与团队 | 云端 spaces | MCP 工具可 `add_memory` / `forget_memory` |
| **[Basic Memory](https://github.com/basicmachines-co/basic-memory)** | 本机 Markdown 知识库 + MCP 检索 / 导入 | 想用文件当第二大脑的人 | 本机 Markdown 项目 | 工具可写笔记；MemRelay 把它当**独立进程**调用 |
| **[Mem0](https://github.com/mem0ai/mem0)** | 嵌进应用的长期记忆库（抽取 + ADD/UPDATE/DELETE/NOOP） | 自己写 agent 应用的开发者 | 向量库 / 托管服务 | 应用代码写入 |

### 关键资料（请以官方页面为准）

- OpenViking 仓库：https://github.com/volcengine/OpenViking  
- OpenViking 文档首页：https://docs.openviking.ai/  
- OpenViking Memory：https://docs.openviking.ai/en/api/16-memory （`search(mode="context")`；旧 `/search/recall` 已弃用）  
- OpenViking 检索：https://github.com/volcengine/OpenViking/blob/main/docs/en/api/06-retrieval.md  
- OpenViking 智能体集成能力（含 MCP `remember` / `forget`）：https://github.com/volcengine/OpenViking/blob/main/docs/en/agent-integrations/16-capability-reference.md  
- Supermemory MCP：https://supermemory.ai/docs/supermemory-mcp/mcp （远程端点 `https://mcp.supermemory.ai/mcp`）  
- Supermemory 产品调整（2026-09-10，停掉 Company Brain 与 Nova，MCP 保留）：https://supermemory.ai/blog/an-update-to-supermemory/  
- Basic Memory：https://github.com/basicmachines-co/basic-memory  
- Mem0：https://github.com/mem0ai/mem0 ；论文 arXiv:2504.19413  

---

## 2. 能力对照（和 MemRelay 相关的部分）

| 能力 | MemRelay | OpenViking | Supermemory | Basic Memory | Mem0 |
|---|---|---|---|---|---|
| 多现成客户端一键接入（写 MCP 配置） | ✅ 核心 | 有若干 agent 集成，偏 OV 生态 | MCP URL 一次接入 | 自带 MCP，不帮你接 Cursor/Codex… | ❌ 库，不是连接器 |
| 本地会话采集 / 官方导出导入 | ✅ | 会话 commit → 抽取 | 文档/上传为主 | ✅ 导入器（ChatGPT/Claude 等） | 应用侧喂对话 |
| **人审收件箱** | ✅ 硬性 | 模型可直接 `remember` | 模型可直接 `add_memory` | 无强制审核层 | 无 |
| 禁止智能体删除记忆 | ✅ 网关无 delete；取代只标 `valid_to` | MCP 有 **`forget`** | MCP 有 **`forget_memory`** | 有写/删工具（取决于配置） | 有 DELETE 操作 |
| 分身 `answer_as_me` / 只出草稿的 `draft_as_me` | ✅ | 需自己拼 | 需自己拼 | ❌ | ❌ |
| 语义检索 / 重排 | 委托后端（默认 BM） | ✅ `find` / `search` + intent | ✅ `search_memory` | ✅ | ✅ |
| 画像 / 偏好自动层 | 核心画像 + 风格卡/原则 | profile / preferences / soul 等内置类型 | `get_profile` | 笔记结构自定 | 记忆条目 |
| 默认真源数据主权 | 文件在你磁盘 | 服务端（可自托管视部署而定） | 云端 OAuth spaces | 文件在你磁盘 | 自选存储 |
| 许可证 / 形态 | Apache-2.0，CLI+网关 | 开源引擎 + 文档站点（火山引擎） | 商业记忆 API；MCP 仍可用 | AGPL-3.0（MemRelay **不打包**，只子进程调用） | Apache-2.0 |

---

## 3. 该复用什么，该自己建什么

### 建议复用（不要在 MemRelay 里重做）

| 对方已有 | 为什么别重造 | MemRelay 怎么用 |
|---|---|---|
| OpenViking / Supermemory / Basic Memory / Mem0 的**向量检索、重排、会话抽取流水线** | 工程量大，对方持续迭代 | 做成**可选后端**：`search` / （批准后）`remember` 映射过去 |
| OpenViking 的 `search(mode="context")`、Mem0 的 FACT 抽取提示、BM 的 Markdown 索引 | 已有公开文档与实现 | 提示词可借鉴（注明出处）；检索走适配器 |
| Supermemory 远程 MCP | 适合「只想要一个共享记忆 URL」的用户 | 用户可**并行**接 SM MCP；MemRelay 不必吞并它 |

### 建议继续由 MemRelay 建设（对方不替代）

| MemRelay 层 | 对方缺什么 |
|---|---|
| **审核队列 + 白名单网关**（无 send、无 forget 暴露给智能体） | OV/SM 默认把写/删工具交给模型 |
| **跨客户端 connect / capture / import**（路径有出处、不猜封闭 App） | 引擎不管「你本机装了哪些 IDE」 |
| **数字分身**：时间维 `as_of`、风格卡、原则、`answer_as_me` 声明与拒答、`draft_as_me` 只出草稿、保真度 eval | 引擎提供记忆，不提供「像我一样答/拟」的完整产品面 |
| **本地优先的明文 vault + 回滚**（Dream git 快照） | 云端产品模型不同 |

### 什么时候算「MemRelay 在造轮子」

若接下来把大量精力花在这些事上，就是在重复造引擎，应停下来改接后端：

1. 自研一套通用 embedding + 重排服务，却对标 OpenViking / Supermemory / BM 已公开的检索管线；  
2. 再做一个「智能体直接 `remember` / `forget`」的 MCP，却丢掉收件箱；  
3. 做一个云端第二大脑 App 去对标 Nova —— 而 [Supermemory 已在 2026-09 停掉 Nova / Company Brain，转向记忆 API](https://supermemory.ai/blog/an-update-to-supermemory/)，说明「做个人知识 App」与「做记忆引擎」是两条路，MemRelay 应坚持 **relay + twin**，不要变成第三个 Nova。

---

## 4. 推荐架构

```text
  现成智能体 (Claude Code / Cursor / …)
           │  MCP stdio（白名单）
           ▼
     MemRelay 网关 + 收件箱 + 分身
           │  MemoryBackend 适配器
     ┌─────┼──────────────┐
     ▼     ▼              ▼
 Basic Memory   OpenViking(可选)   （未来：Supermemory 等）
 (默认，本机)   remember/search
```

- **默认**：`backend = "basic-memory"`（现状）。  
- **可选**：`backend = "openviking"` —— 适配器把批准后的写入映射为 OV `remember`，检索映射为 `search(mode="context")`；**不**把 OV 的 `forget` 接到 MemRelay 网关。收件箱仍挡在所有写入前面。  
- Supermemory：更适合用户在客户端里**额外**挂 `https://mcp.supermemory.ai/mcp`；若日后做适配器，同样必须挡住 `forget_memory`，且写入先过 inbox。

代码入口见 `packages/core/src/memrelay/backends/`（接口 + BM 实现 + OV 占位桩）。完整集成尚未开始；见 [architecture.md](architecture.md)。

---

## 5. 结论

| 问题 | 答案 |
|---|---|
| MemRelay 还要不要做？ | **要。** 缺口在「多人用的现成智能体 ↔ 一份人审记忆 ↔ 分身」，不是缺另一个向量库。 |
| 要不要 fork / 重写 OpenViking 或 Supermemory？ | **不要。** 当可选后端。 |
| 和 Basic Memory 什么关系？ | 继续默认后端；AGPL 进程隔离不变。 |
| 和 Mem0 什么关系？ | 借鉴抽取/更新操作语义（已在 consolidate / extract 注明出处），不当成连接器替代品。 |

更新于 2026-10-18；链接以各项目当时公开文档为准。
