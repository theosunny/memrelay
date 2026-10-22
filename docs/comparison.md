# MemRelay vs OpenViking vs Supermemory vs Basic Memory vs Mem0

> **English summary.** MemRelay is a *relay + twin* for a person who already uses many off-the-shelf AI agents: one reviewed Markdown vault, connectors, capture/import, and `answer_as_me` / `draft_as_me`. OpenViking and Supermemory are *memory engines* (storage, extraction, retrieval). Basic Memory is the Markdown engine MemRelay already runs as a separate process. Mem0 is an in-app memory library for builders. **Retrieval default:** keep **Basic Memory** (local Markdown + AGPL subprocess, matches MemRelay's file vault). Use **OpenViking** when you want stronger session/intent retrieval and accept a server; treat **Supermemory** as a parallel cloud MCP or a future optional backend — not a replacement for the review inbox. **Peers:** Mem0 OpenMemory MCP occupied a similar "shared MCP memory" niche but was **sunset in 2026**; few products combine auto-connect + human review + twin tools the way MemRelay does. Details in §6–§7. Sources cited below (checked 2026-10).

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


---

## 6. 检索引擎建议（Basic Memory vs Supermemory vs 其他）

**问题：** MemRelay 底层检索该绑谁？

| 候选 | 适合 MemRelay 的理由 | 不适合当默认的理由 | 建议角色 |
|---|---|---|---|
| **Basic Memory（默认）** | 记忆已是本机 Markdown；BM 直接索引同一 vault；AGPL 只作子进程；导入器已在用；无账号、可离线 | 检索管线不如商业/大型引擎花哨（重排、意图分析） | **默认 `backend=basic-memory`** |
| **OpenViking** | `search(mode="context")`、会话上下文、意图分析文档完整；可映射 `remember` | 需要部署/服务；MCP 带 **`forget`**，绝不能接到网关；与「文件即真相」模型有张力 | **可选后端**（适配器已占位，完整接入未做） |
| **Supermemory** | 远程 MCP 开箱即用；语义检索成熟 | 云端 OAuth spaces；模型可 `forget_memory`；[2026-09 停掉 Nova / Company Brain](https://supermemory.ai/blog/an-update-to-supermemory/)，产品面在收缩到 API | 用户可**并行**挂 MCP；或日后做可选后端，**同样必须挡 forget** |
| **Mem0（库 / 托管 MCP）** | 抽取与 ADD/UPDATE 语义可借鉴 | 面向应用开发者；托管记忆不在你磁盘；本地 OpenMemory MCP 已日落（见 §7） | 借鉴提示词与操作语义，不当默认存储 |
| **自研向量栈** | — | 明确在造轮子（§3） | **不要做** |

**结论（给选型用的三句话）：**

1. **日常默认继续 Basic Memory**——和 MemRelay「明文 vault + 人审 + 本机优先」一致，迁移成本最低。  
2. **要更强会话/意图检索时再接 OpenViking**，且只走 `remember` / `search(mode="context")`，永不暴露 `forget`。  
3. **Supermemory 适合「再挂一个云端共享记忆」**，不适合替换收件箱；若当后端，策略与 OV 相同。

配置：`backend = "basic-memory" | "local" | "openviking"`（见 `memrelay.backends`）。

---

## 7. 可用性与竞品格局（同类产品）

### 7.1 MemRelay 好不好用（相对同场）

| 维度 | MemRelay（v0.1 / main 上的 v0.2） | 典型 MCP 记忆服务（Mem0 托管、Supermemory MCP、已日落的 OpenMemory） |
|---|---|---|
| 装上就能接到多个 IDE | ✅ `connect --all` 写配置、备份、回滚；路径有出处 | 通常只给一个 MCP URL，**不**帮你改 Claude/Cursor/Codex 的本地文件 |
| 本机历史 / 导出包进记忆 | ✅ capture + import | 少见；多为对话里 `add_memory` |
| 人必须批准才入库 | ✅ 硬性 inbox | ❌ 模型常可直接 add/delete |
| 分身（像我一样答 / 只拟草稿） | ✅ `answer_as_me` / `draft_as_me` | ❌ 需自建 |
| 开箱体验 | 开发者预览：需 `uv` + 可选 BM；CLI 中英混排；未上 PyPI | 云端 MCP 往往「粘贴 URL 即用」，但数据主权与审核弱 |
| 成熟度 | 预览期；CI 三系统；检索委托 BM | 商业引擎更成熟，产品边界常变（见 SM Nova 停运、OpenMemory 日落） |

**诚实结论：** 若你只想「随便一个助手多记住一点事」，挂 Supermemory / Mem0 托管 MCP 更快。若你要**跨工具一份人审记忆 + 分身**，MemRelay 更贴；代价是安装与审核流程更重。

### 7.2 相近定位的产品（交叉智能体个人记忆）

同一窄缝——「多个现成智能体共用一份关于我的记忆」——近年主要选手：

| 名称 | 重叠点 | 关键差距 | 状态 / 来源 |
|---|---|---|---|
| **Mem0 OpenMemory MCP** | 本机 MCP，多客户端共享记忆，有仪表盘 | 模型可删；无人审队列；无分身工具；无 connect 写各 IDE 配置 | **已日落**（Mem0 文档 sunsetting；独立 `mem0-mcp` 归档；2026-07 从 monorepo 移除）。背景：[Contextely 说明](https://www.contextely.com/blog/openmemory-mcp-explained)、[Mem0 openmemory 目录提示改用 self-hosted server](https://github.com/mem0ai/mem0/tree/main/openmemory) |
| **Mem0 托管 MCP** | 跨 Claude/Cursor 等的共享记忆 | 云端；非 Markdown vault；无 MemRelay 式审核/分身 | https://mcp.mem0.ai/mcp/ （见 [Mem0 Claude Code 指南](https://mem0.ai/library/coding-agents/claude-code-memory)） |
| **Supermemory MCP** | 跨助手共享记忆 | 云端；有 forget；Nova 个人知识 App 已停 | https://supermemory.ai/docs/supermemory-mcp/mcp ；停运说明 https://supermemory.ai/blog/an-update-to-supermemory/ |
| **OpenViking** | 强记忆/检索/agent 集成 | 引擎+团队上下文库，不是「个人多 IDE 一键接入 + 人审分身」产品 | https://github.com/volcengine/OpenViking |
| **Basic Memory** | 本机 Markdown + MCP | 不做多客户端 connect/capture/twin | https://github.com/basicmachines-co/basic-memory |
| **MCP 官方 memory server** | 本地 JSONL 知识图 | 极简，无审核/接入生态 | `@modelcontextprotocol/server-memory`（见业界综述如 [Pathrule](https://www.pathrule.io/writing/memory-mcp-servers-for-ai-coding-agents)） |
| **各厂商自带记忆**（如 Claude Code Auto Memory） | 单工具内记得住 | **不跨工具** | 例如 Claude Code `MEMORY.md`（业界对比文常提及） |

**缺口仍在：** 「自动改各客户端配置 + 本地采集/导入 + 强制人审 + 分身答/拟 + 明文可同步文件」绑在一起的开源产品很少；最接近的 OpenMemory MCP 已退出维护，这反而强化了 MemRelay 坚持 **relay + twin、引擎可插拔** 的理由，而不是再做一个向量数据库。
