# Design: 忆桥分身产品壳（引擎开源 · 记忆整合 · N 面）

**Date:** 2026-10-22  
**Status:** Draft for review  
**Repo:** memrelay  
**Related:** [persona-design.md](../../persona-design.md), [architecture.md](../../architecture.md), [comparison.md](../../comparison.md)

## Problem

Current MemRelay is powerful as a **developer relay** (CLI, MCP, config.toml, capture agents) but feels far from the stated product: a **personal digital twin** with integrated memory. Non-programmer UX is missing. The twin should support **N faces** on one memory store, remain **open source** at the engine layer, and be usable by other “千面” products—not only our own shell.

## Goals

1. **Memory = integration** — one personal truth across tools/sessions; not another notes app.
2. **Twin = N faces** — many callable personas on the same vault (expression and/or task-oriented “skill-like” faces).
3. **Open engine** — Apache-2.0 MemRelay remains the relay + review policy + twin API; third-party 千面 products consume it as equals to our shell.
4. **Human shell** — desktop + mobile product that never leads with MCP/CLI.
5. **Delivery order** — local-first twin shell as product positioning; ship **desktop complete twin first**, mobile **ask + browse** next; **built-in lightweight E2E sync in v1**.

## Non-goals (v1)

- Replacing Basic Memory / building a new storage engine.
- Skill marketplace or full agent runtime for “办事面”.
- Multi-tenant collaborative editing of one vault.
- Auto-send of messages/email on the user’s behalf.
- Public cloud search over other people’s memories.
- Teaching users to edit `config.toml` as the primary path.

## §1 Positioning (two layers)

| Layer | What | Who |
|-------|------|-----|
| **MemRelay engine (OSS)** | Memory integration + review policy + twin capabilities | Developers; other 千面 products |
| **忆桥分身 shell (product)** | Desktop + mobile UI: ask, browse, quiet auto-capture | People (first user: theo) |

**Face (面):** a callable persona config on **one shared integrated vault**—not a separate memory database.

A face includes at least:

1. Name / scenario  
2. Visibility ceiling over memories  
3. Tone + refusal rules  
4. Capability switches (`answer`, `draft`, later tools)  
5. Audit identity (self / share link / third-party app)

Faces may be **expression-oriented** (answer/draft) or **task-oriented** (skill-like “help me do X”); v1 treats the latter as a **direction**, not a skill store. v1 ships at least the **self** face; N faces are first-class in the model.

Channels (Cursor, Claude Code, …) remain **connectors**, not faces.

## §2 Desktop information architecture (v1 shell)

Tray-resident app; main window three entries (human copy only):

1. **分身** — chat as current face; switcher for N faces (self required).  
2. **记忆** — search, timeline, type filters; provenance + confidence; “needs your eye” for sensitive/conflict.  
3. **动态** — readable digest of recent auto-applied memories (not raw logs).

Secondary: settings (data location, sync, models), export/backup.  
**Not** on home: terminal commands, MCP server list, toml editor.

**Mobile v1:** 分身 (ask) + 记忆 (browse) only; same faces + vault via sync.

## §3 Engine & 千面 integration

Stable engine surface (no forget/delete/send for agents):

- Memory: `recall` / `read` / `recent` / `propose` (writes still policy-gated)  
- Twin: face-scoped `answer` / `draft`  
- Faces: list / read face policy (create-face UI can be v1.1)

Access paths for 千面 products:

1. Local MCP / local API (existing clients keep working)  
2. Scoped share link (face-limited Q&A, audit + rate limit)—optional later if not blocking shell  
3. Language-agnostic HTTP/SDK—phase 2; must not block desktop shell

Shell = first-party client. Third-party clients cannot bypass review policy or face ceilings. Vault + face configs stay plain files (Markdown/TOML/JSON) for OSS and backup.

## §4 Sync & privacy (revised)

**v1 includes a first-party lightweight sync service:**

- E2E encryption; sync vault + face configs only; not a social cloud  
- Desktop as primary node; phone pairs via account or pairing code  
- Optional “point at a folder” remains for power users; **product default is built-in sync**  
- Conflicts → “needs your eye”; no silent overwrite  

Privacy:

- Prefer **zero-knowledge** server (no plaintext memories)  
- Twin disclosure + citations on every answer  
- Never auto-send; drafts only  
- Face ceilings enforced server-side/engine-side, not only in UI  
- Local audit log; minimal sync metadata  

Out of scope for sync: public search of others’ memories, multi-user co-edit, selling vault as generic netdisk.

## §5 v1 scope checklist

### In scope (v1)

- [ ] Desktop shell: tray + 分身 / 记忆 / 动态  
- [ ] Self face chat with citations + disclosure  
- [ ] Memory browse/search/timeline over existing vault  
- [ ] Quiet auto-capture using existing MemRelay engine (GLM/stub as configured)  
- [ ] Built-in E2E sync desktop ↔ mobile  
- [ ] Mobile: ask + browse  
- [ ] Keep OSS engine + MCP for Cursor and peers  
- [ ] Face model in config (N faces supported; UI may start with self)

### Explicitly later

- Face editor for many expression/task faces  
- 办事面 tool runtime / distilled-skill installer  
- Third-party HTTP SDK  
- Share-link “ask my twin” productization  
- Tray-only “mini mode” polish, browser extension, A2A

### Success criteria (v1)

1. A non-dev can install desktop, open 分身, ask “我偏好什么”, get a cited answer without seeing MCP.  
2. Phone shows the same memories after sync.  
3. Cursor `recall` / `propose_memory` still work against the same vault.  
4. Auto-applied digest visible under 动态; sensitive items surface for human glance.

## Architecture sketch

```text
[Desktop shell] [Mobile shell] [Cursor/MCP] [Other 千面 apps]
        \            |              |              /
         \           |              |             /
          v          v              v            v
              MemRelay engine (policy + twin + faces)
                          |
              Markdown vault (+ face configs)
                          ^
              E2E sync service (ciphertext)
```

Engine remains subprocess/library; shells never embed a second memory truth.

## Open questions (non-blocking for spec approval)

1. Sync account: email magic-link vs device pairing only?  
2. Desktop stack: Tauri vs Electron (prefer Tauri for size; decide in implementation plan)?  
3. Branding: keep「忆桥分身」vs separate consumer name?

## Approval record

- Product shape: desktop + mobile (A+B)  
- Positioning: route 1 (local twin shell); delivery order route 3 (desktop full → mobile ask/browse)  
- §1 revised: OSS engine + N faces + memory integration; 办事面 as skill-like *direction*  
- §2: three entries approved  
- §3: engine + 千面 access approved  
- §4: own lightweight E2E sync required in v1  
- §5: this scope section → write spec (this document)

