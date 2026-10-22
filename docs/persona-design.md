# Persona & product design — automatic shared memory + digital twin

MemRelay（忆桥）的产品默认是：**少动手、全自动、仍守住底线**。人工审核是可选升级，不是日常负担。

## Goals

1. **Any agent reads one shared memory** — Markdown vault on your disk; MCP gateway for Claude Code / Cursor / Codex / Gemini CLI / …
2. **Digital twin** — `answer_as_me` / `draft_as_me` (draft only), style card, principles, reflect/dream.
3. **Default fully automatic** — trusted high-confidence proposals land in the vault without clicking approve every time.
4. **Safety rails always on** — never auto-send; never expose forget/delete to agents; quarantine risky writes.

## `review.mode` (config.toml `[review]`)

| Mode | Behaviour |
|------|-----------|
| **`auto` (default)** | Auto-approve high-confidence proposals from trusted local capture (`claude-code`, `codex`, `gemini-cli`, `cursor`) and allowlisted MCP agents; also memrelay-generated reflections / export-import when configured. Quarantine (stay in inbox as `needs_attention`): secrets/PII redaction, injection flags, confidence < `min_confidence` (0.55), sensitivity personal/secret, notes about other people (`type=person`), SUPERSEDE contradictions, profile-file replaces. Visibility=`private` alone is OK (most memories are private). |
| **`assist`** | Auto only for trusted + high confidence; everything else waits in inbox (older “recommended” hybrid). |
| **`strict`** | Everything waits in inbox (legacy all-human review). |

Switch back to all-human review:

```toml
[review]
mode = "strict"
```

Or assist: `mode = "assist"`. Check with `memrelay status` / `memrelay doctor`.

## Never automatic

- **Send / post / email** — MemRelay has no send path; `draft_as_me` returns text only.
- **forget / delete** — not in the MCP whitelist; consolidation SUPERSEDE only marks `valid_to` after human (or never auto-applies SUPERSEDE).
- Overwriting locked / hand-written `profile/*` files.

## Observability

- Desktop notification (optional, `review.notify`) when something auto-applies.
- `memrelay status` — mode, inbox / `needs_attention` counts, recent auto-applied.
- Auto-applied log: data dir `state/auto-applied.jsonl`.
- Weekly reflect includes an auto-applied digest for skimming.

## Relation to engines

Basic Memory / OpenViking / Supermemory / Mem0 are optional **engines**. MemRelay stays the **relay + twin + review policy** layer. See [comparison.md](comparison.md).
