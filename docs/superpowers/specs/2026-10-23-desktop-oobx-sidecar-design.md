# Design: 忆桥分身桌面产品化（OOBX · sidecar · 签名公证）

**Date:** 2026-10-23  
**Status:** Approved (locked with theo, 2026-10-23)  
**Repo:** memrelay  
**Related:** [2026-10-22-twin-product-shell-design.md](2026-10-22-twin-product-shell-design.md)

This is the out-of-box productization follow-on for the desktop shell. The twin-shell spec defines what the product is. This spec defines how a person on a Mac goes from a browser download to a cited twin answer without a terminal, and how the 分身 screen must feel while they do it.

## Goal

**Bundle-hide.** Double-click the consumer download and ask the twin. The engine is inside the app. Ports, tokens, and sync URLs are not on the home screen.

The level is not “polish the current form.” Two outcomes are required together:

1. **分身 is a consumer chat product.** A conversation thread, not a single question box with raw settings beside it. The interaction bar is a clean chat (DeepSeek chat / harness-style): messages, a composer, send, empty state, loading, and errors. That reference is for rhythm and completeness only. Do not copy DeepSeek’s brand, colors, or assets. Keep the warm paper UI already in the shell. Do not invent a new brand system in this phase.
2. **The path is closed.** Install → open → one-time model config if needed → ask → cited answer → browse 记忆 / 动态. No engineer knobs and no broken empty states on that path.

Either outcome alone fails this phase. A beautiful thread that cannot answer, and a working engine behind a form console, are both out of spec.

Approach is **a sidecar**. The macOS `.app` embeds a `memrelay` binary that can serve `shell-api`. The packaged app prefers that binary over `PATH` and `uv`.

## Success criteria

All of the following are in scope. Criteria 1 and 2 are jointly required.

1. **Chat thread.** 分身 shows a message thread (user and twin bubbles), a composer, and a send action. An empty thread offers a sample ask and does not open settings. A send shows a loading state in the thread. A finished turn shows the twin’s reply, the twin disclosure, and citations when the engine returned sources. Relaunching the app shows that thread again. The transcript is local UI state, not a second vault and not something the phone syncs.
2. **Closed ask path.** On a clean Mac, Chrome or Finder download of the consumer DMG, then double-click, is enough. No `xattr`, no right-click Open, no Terminal, no `uv`, no pre-existing `~/MemRelay`. After the one model screen, a send reaches the bundled engine and the reply renders in the thread. A vault that contains one note must produce a visible citation on that answer. An empty vault still returns a real engine answer (nothing remembered yet, plus the disclosure), and that empty reply does not by itself pass this criterion. A mocked bubble does not pass it either.
3. **Home stays three places:** 分身, 记忆, 动态. Empty 记忆 and 动态 have a short human empty state. They never auto-open Advanced.
4. **Everyday settings** are model, pair-phone sync, and about. Service URL, token, local sync URL, 使用本机, sync once, and open data dir sit in a collapsed Advanced group.
5. **Consumer artifact** is a Developer ID–signed and notarized DMG containing a signed app and signed sidecar binaries. If Apple credentials are missing, that pipeline fails and does not publish an unsigned build as the website download.

## Non-goals

- MCP, CLI, or `config.toml` teaching on the home screen.
- A consumer install that requires Terminal, `uv`, Homebrew, or a manual `memrelay init`.
- Visual polish that does not bundle the engine.
- A new brand system, a lime clone, or a redesign of 记忆 / 动态 into different products. Those two screens keep their jobs inside the same warm paper shell.
- Replacing the memory engine, editing many faces, or a skill store.
- Windows or Linux consumer packages. This phase’s consumer download is the notarized macOS DMG.
- Telling users to clear quarantine with `xattr`, or documenting right-click Open as the way to start the consumer app.

## First-run flow

1. The user downloads the notarized DMG in Chrome or Finder and opens the app with a normal double-click.
2. If no model is saved, one screen asks for a provider, an API key, and an optional model name. Nothing else is on that screen.
3. Providers are the engine presets already in `packages/core`: openai, deepseek, qwen, kimi, glm, and ollama. Cloud presets need a key before Continue. Ollama does not. The optional model name overrides that preset’s default. This phase adds no new providers.
4. The key is stored in the macOS Keychain under the app identity `io.memrelay.shell`. It is not written into the vault, not shown again on 分身, and not echoed in answers. On later launches the sidecar receives it through the preset’s existing environment variable.
5. Continue is the last question. The app then creates the vault, starts the bundled engine, and lands on 分身. No second wizard.
6. The empty thread offers one sample ask, 「我偏好什么？」. Choosing it sends that turn. The user can type their own instead. Settings stay closed.
7. The answer appears in the thread as in success criterion 2. 记忆 and 动态 are available from the same window.

Changing the model later happens in everyday settings, not as another first-run gate.

## Main UI and settings IA

Home information architecture does not change: **分身 / 记忆 / 动态**.

**分身** is the chat product inside the warm paper shell:

- Thread of user and twin messages, newest turn in view after send.
- Composer and a clear send action. Enter sends. The sample ask is a chip on the empty thread, not a settings link.
- Loading lives in the thread (the user bubble is already there; the twin side shows that it is answering).
- A completed twin message shows the answer, the disclosure, and any citations as part of the bubble, not as a debug panel.
- The thread for the self face is saved in the app data directory and restored on launch. It is not synced.

**记忆** and **动态** keep the roles from the twin-shell spec (browse with provenance; readable auto-applied digest). This phase only removes engineer debris and broken empty screens so the shell feels like one product. It does not restyle them into a new system.

**Settings** are secondary, reached on purpose, never opened by an empty vault or a failed ask.

| Group | Always visible | Contents |
| --- | --- | --- |
| Everyday | Yes | Model (provider, key, optional model name), sync (pair the phone), about (app version, notarized build) |
| Advanced | Collapsed | Service URL, token, local sync URL, 使用本机, sync once, open data dir |

Pair-phone stays the pairing string and its QR. The string is still the vault key. About does not list ports.

## Sidecar packaging

The consumer `.app` contains a Mach-O sidecar that implements the `memrelay` CLI used by the shell, including `shell-api` and vault `init`. It does not need system Python, `uv`, or a user-installed `memrelay`.

The same bundle contains a Mach-O for the local sync server, used only when the user chooses 使用本机. The default path does not start it.

Lookup for the packaged app:

1. The sidecar inside the `.app`.
2. Stop. Do not search `PATH`, Homebrew, `~/.local/bin`, or `uv`.

`tauri dev` on a developer machine may still use the repo environment. That build is not the consumer download.

The shell starts the engine on `127.0.0.1:8787` with a token file in the app data directory (mode `0600`). The window reads that token. The home screen never displays the host, the port, or the token. The content security policy continues to allow only that local shell API.

Both sidecars are signed with the same Developer ID as the app and pass Gatekeeper’s nested-code checks. How the Mach-O is frozen is an implementation choice inside those constraints.

## Signing and notarization

Users must not need `xattr`. A Chrome or Finder download opened with a double-click must run.

This phase includes **Developer ID Application** signing and **notarization** of the DMG, the `.app`, and the embedded sidecar binaries, then stapling the ticket to the DMG.

Prerequisites:

- An Apple Developer Program membership.
- A Developer ID Application certificate for the team.
- CI secrets for that certificate (`.p12` and its password), a non-empty `APPLE_SIGNING_IDENTITY` (`Developer ID Application: … (TEAMID)`), `APPLE_PROVIDER_SHORT_NAME` / team id, and notarytool credentials (Apple ID plus an app-specific password, or an App Store Connect API key). An empty `APPLE_SIGNING_IDENTITY` is a missing credential, not “sign with nothing.”
- Keychain entitlement so the app can store the model API key.

The consumer release job **fails closed**. If any of those secrets are missing or the notarization request is rejected, the job fails. It must not upload an unsigned or unnotarized DMG and call it the consumer download, and it must not move `/releases/latest` to such a build. The website download button keeps reading `/releases/latest` and therefore only receives a notarized asset after this phase ships.

Website and in-app download copy for that artifact must not tell people to run `xattr`, clear the quarantine flag, or right-click and choose Open. Local unsigned developer builds may still exist on a Mac workstation. They are not the consumer download and are not linked from the site.

## Sync defaults

The sync base URL is prefilled from `sync` in `packages/website/urls.json` (today `https://memrelay-sync.preview.tencent-zeabur.cn`). The product does not add a second consumer default.

Everyday sync is **pair the phone**. After a successful pair, the desktop syncs in the background. That sync does not take over 分身 and does not print URLs.

使用本机, the local base `http://127.0.0.1:8790`, and a one-shot sync stay in Advanced. Choosing 使用本机 starts the bundled sync server on that address. It does not ask the user to install anything.

Sync remains end-to-end ciphertext, as in the twin-shell spec. This phase does not change the pairing string, the vault key, or who may push.

## Data and vault

On first launch the app creates the vault itself under the Tauri app data directory. It does not require `~/MemRelay` or a prior `memrelay init`.

Open data dir (Advanced) reveals that folder in Finder. There is no vault-location step in first run and no vault picker on the home screen.

The engine remains the only memory writer. The chat transcript in app data is not a second store of record. Face config and notes stay the files the twin-shell spec already describes.

## Error states

| What happened | What the user sees | What stays hidden |
| --- | --- | --- |
| Sidecar not up | On the main window, a short line that the twin is not connected, plus 重试. Retry starts the bundled engine again. | Host, port, token, Advanced |
| Model or key rejected | In the thread, that the reply did not come back, with a way to the everyday model settings | Ports, token, env var names |
| Empty vault | A normal twin bubble: nothing is remembered yet, plus the disclosure | A dump of the vault path |
| Sync failed after pair | A quiet status on the sync settings, not a modal over 分身 | The local bind address, unless the user opened Advanced |
| Missing Apple credentials in CI | The consumer job fails. No unsigned asset is labeled as the download | A fallback “right-click Open” release |

An empty 分身, 记忆, or 动态 screen never opens Advanced by itself.

## Open questions

None. Freezing the sidecar into a Mach-O is an implementation detail bounded by the packaging and signing sections above, not a product choice left open.

## Relation to the twin-shell spec

[2026-10-22-twin-product-shell-design.md](2026-10-22-twin-product-shell-design.md) remains the product definition: one vault, N faces, OSS engine, desktop home of 分身 / 记忆 / 动态, mobile ask and browse, and built-in end-to-end sync. This document does not reopen those.

What that spec left open is now settled for the desktop shell, by shipping and by this approval:

- The desktop stack is Tauri. The consumer name on the app is 忆桥分身.
- Phone linking is the pairing string, not an email account.
- The engine is a sidecar process. The shell does not embed a second memory truth.

What this follow-on adds, and what the earlier spec did not decide:

- The consumer Mac path bundles that sidecar and refuses `PATH` / `uv`.
- First run is one model screen, then the chat. The vault is created in app data.
- 分身 is a persisted chat thread. Success requires that thread and a real cited answer together. An honest empty-vault reply is required too, and it is not a substitute for the citation.
- Everyday settings shrink to model, pair, and about. Engineer fields move under Advanced.
- The consumer DMG is signed and notarized, or it is not shipped. `xattr` is not a user step.

The twin-shell success line “a non-developer can install, ask, and get a cited answer without seeing MCP” is met only when both success criteria in this document pass on the notarized build.
