# Desktop OOBX Sidecar Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** A notarized macOS app that double-clicks into a chat thread, asks the bundled engine, and shows a cited answer without a terminal or `xattr`.

**Architecture:** The Tauri shell keeps one memory engine as a Mach-O sidecar. First launch writes model choice into the app-data config, stores the API key in the Keychain, and passes it to the sidecar through the preset’s existing environment variable. Release builds resolve only binaries inside the `.app`. `tauri dev` may still use the repo environment. The consumer vault uses the in-process `local` backend so the app does not shell out to `basic-memory`.

**Tech Stack:** Tauri 2, React 19, Vite 6, Vitest, Rust (`keyring` 3), Python 3.12, PyInstaller 6.11.1, `notarytool`, existing `memrelay` shell API on `127.0.0.1:8787`.

## Global Constraints

- Bundle-hide: double-click asks the twin; the engine is inside the app; ports, tokens, and sync URLs are not on the home screen.
- Sidecar: embed `memrelay` (shell-api capable) in the macOS `.app`; the packaged app does not search `PATH`, Homebrew, `~/.local/bin`, or `uv`.
- First run is one screen: provider, API key, optional model name. Then no second wizard.
- Providers are only `openai`, `deepseek`, `qwen`, `kimi`, `glm`, `ollama`. Cloud presets require a key. Ollama does not. Add no new providers.
- The API key goes to the macOS Keychain under identity `io.memrelay.shell`. It is not written into the vault, not shown on 分身, and not echoed in answers.
- Everyday settings: model, pair phone, about. Advanced stays collapsed: service URL, token, local sync URL, 使用本机, sync once, open data dir.
- Home stays 分身 / 记忆 / 动态. Empty 分身 offers 「我偏好什么？」 and never opens settings.
- 分身 is a chat thread: bubbles, composer, Enter sends, loading in the thread, disclosure, citations. The self-face transcript persists in the app data directory and is not synced.
- Success criteria 1 and 2 are jointly required. An empty-vault reply does not replace a cited answer. A mocked bubble does not pass.
- Sidecar down: the main window says the twin is not connected and offers 重试. Do not show `127.0.0.1`, the port, or the token.
- Sync URL is prefilled from `packages/website/urls.json` field `sync` (`https://memrelay-sync.preview.tencent-zeabur.cn`). Pair phone is primary. After pair, sync in the background without taking over 分身. 使用本机 uses `http://127.0.0.1:8790` and starts the bundled sync server only then.
- Shell API stays `http://127.0.0.1:8787`. The CSP allows only that origin.
- Vault is created under the Tauri app data directory. Do not require `~/MemRelay`.
- Keep the warm paper UI (`#f3efe6`, `#fffdf8`, accent `#0f6e6b`). Do not invent a new brand and do not copy DeepSeek marks.
- Product name stays 忆桥分身. Bundle identifier stays `io.memrelay.shell`.
- Consumer desktop vault backend is `local`. Do not bundle or require the `basic-memory` CLI.
- Consumer DMG is Developer ID signed, notarized, and stapled, including both sidecar binaries. Users must not need `xattr`. Site and release notes must not say `xattr` or right-click Open.
- If any required Apple secret is missing or notarization fails, the consumer job exits non-zero and does not upload a download.
- Out of scope: MCP/CLI teaching on home, a terminal install, Windows/Linux consumer packages, a new memory engine, a face editor.

---

## File map

| File | Action | Responsibility |
| --- | --- | --- |
| `packages/core/src/memrelay/setup_model.py` | Create | Write `persona_llm`, optional model override, and `backend = "local"` under `MEMRELAY_HOME`. Never write the API key. |
| `packages/core/src/memrelay/cli.py` | Modify | Add `configure-model`. |
| `packages/core/tests/test_setup_model.py` | Create | Provider, key-not-stored, vault init, local backend. |
| `packages/desktop/src/model.ts` | Create | Provider list and Continue rules. |
| `packages/desktop/src/model.test.ts` | Create | Those rules. |
| `packages/desktop/src/ModelGate.tsx` | Create | The only first-run screen. |
| `packages/desktop/src/ModelGate.test.tsx` | Create | Continue disabled until the key rule passes. No port fields. |
| `packages/desktop/src-tauri/src/model.rs` | Create | Keychain trait, `model_status`, `save_model`. |
| `packages/desktop/src-tauri/src/lib.rs` | Modify | Register commands. Stop searching `PATH` in release. Stop auto-starting sync. |
| `packages/desktop/src-tauri/Cargo.toml` | Modify | Add `keyring` 3. |
| `packages/desktop/src/chat.ts` | Create | Thread transitions and transcript JSON. |
| `packages/desktop/src/chat.test.ts` | Create | Sample ask, loading, citations, reload. |
| `packages/desktop/src/ChatThread.tsx` | Create | Bubbles, composer, chip. |
| `packages/desktop/src/ChatThread.test.tsx` | Create | Chip sends; settings dialog is absent. |
| `packages/desktop/src/errors.ts` | Create | The spec’s user-facing strings. |
| `packages/desktop/src/errors.test.ts` | Create | Strings do not contain hosts, ports, or `xattr`. |
| `packages/desktop/src/SettingsDialog.tsx` | Create | Everyday vs Advanced. |
| `packages/desktop/src/SettingsDialog.test.tsx` | Create | Advanced is closed; pair does not show the shell port. |
| `packages/desktop/src/App.tsx` | Modify | Wire gate, thread, settings, errors. Never auto-open settings. |
| `packages/core/src/memrelay/twin.py` | Modify only if Task 6’s citation test fails | Current `_llm_cited` already returns `None` when the model prose has no valid `[n]`, which is the rules fallback. Do not change refusal strings. |
| `.gitignore` | Modify | Ignore the frozen `resources/memrelay` and `resources/memrelay-sync` binaries. |
| `packages/desktop/src/styles.css` | Modify | Thread layout on the existing paper colors. |
| `packages/desktop/src/api.ts` | Modify | Classify ask failures. Do not put the token on screen. |
| `packages/desktop/vitest.config.ts` | Create | jsdom test runner. |
| `packages/desktop/package.json` | Modify | `npm test`. |
| `packages/desktop/sidecar/memrelay_entry.py` | Create | PyInstaller entry for `memrelay`. |
| `packages/desktop/sidecar/memrelay_sync_entry.py` | Create | PyInstaller entry for `memrelay-sync`. |
| `packages/desktop/sidecar/build-macos.sh` | Create | Freeze both Mach-O files on aarch64. |
| `packages/desktop/src-tauri/tauri.conf.json` | Modify | Bundle `resources/memrelay` and `resources/memrelay-sync`. |
| `packages/desktop/src-tauri/Entitlements.plist` | Modify | Keychain access group. No app sandbox. |
| `.github/workflows/release-macos.yml` | Modify | Fail closed, sign, notarize, staple, ASCII asset names. |
| `packages/website/index.html` | Modify | Remove right-click / quarantine install copy. |
| `README.md` | Modify | Consumer download is the notarized DMG. |
| `README.zh-CN.md` | Modify | Same, in Chinese. |
| `packages/desktop/README.md` | Modify | Local unsigned builds are not the consumer download. |
| `docs/superpowers/plans/2026-10-23-desktop-oobx-e2e.md` | Do not create | The manual checklist is Task 9 of this plan. |

Commits in this plan use `git commit -s` because `ci.yml` rejects a missing `Signed-off-by` trailer.

## Task 1: Model prefs, Keychain, first-run screen

**Files:**
- Create: `packages/core/src/memrelay/setup_model.py`
- Modify: `packages/core/src/memrelay/cli.py`
- Test: `packages/core/tests/test_setup_model.py`
- Create: `packages/desktop/src/model.ts`
- Test: `packages/desktop/src/model.test.ts`
- Create: `packages/desktop/src/ModelGate.tsx`
- Test: `packages/desktop/src/ModelGate.test.tsx`
- Create: `packages/desktop/src-tauri/src/model.rs`
- Modify: `packages/desktop/src-tauri/src/lib.rs`
- Modify: `packages/desktop/src-tauri/Cargo.toml`
- Modify: `packages/desktop/package.json`
- Modify: `packages/desktop/package-lock.json`
- Modify: `packages/desktop/src/App.tsx`
- Create: `packages/desktop/vitest.config.ts`

**Interfaces:**
- Consumes: `memrelay.llm.PRESETS`, `Config.save`, `Vault.init`, Tauri `AppHandle.path().app_data_dir()`.
- Produces:
  - `configure_model(home: Path, provider: str, model: str) -> dict` with keys `provider`, `model`, `api_key_env`, `vault`.
  - CLI `memrelay configure-model --home <dir> --provider <name> --model <optional>` prints one JSON object on stdout.
  - `canContinue(provider: Provider, apiKey: string): boolean`
  - `PROVIDERS` exactly `["openai","deepseek","qwen","kimi","glm","ollama"]`
  - Rust `model_status(app) -> ModelStatus { configured, provider, model }`
  - Rust `save_model(app, provider: String, api_key: String, model: String) -> Result<(), String>`
  - Keychain service `io.memrelay.shell`, account `model-api-key`. The secret is never in `config.toml` or `model.json`.

- [ ] **Step 1: Write the failing Python test**

```python
import json
from pathlib import Path

from memrelay.config import Config
from memrelay.setup_model import configure_model


def test_deepseek_writes_preset_and_not_the_key(tmp_path: Path, monkeypatch):
    monkeypatch.delenv("MEMRELAY_HOME", raising=False)
    info = configure_model(tmp_path, "deepseek", "deepseek-chat")
    assert info["api_key_env"] == "DEEPSEEK_API_KEY"
    text = (tmp_path / "config" / "config.toml").read_text(encoding="utf-8")
    assert 'persona_llm = "deepseek"' in text
    assert 'backend = "local"' in text
    assert "sk-" not in text
    assert (tmp_path / "vault").is_dir()
    monkeypatch.setenv("MEMRELAY_HOME", str(tmp_path))
    loaded = Config.load()
    assert loaded.persona_llm == "deepseek"
    assert loaded.llm.model_override == "deepseek-chat"
    assert loaded.backend == "local"


def test_ollama_allows_empty_env_name(tmp_path: Path):
    info = configure_model(tmp_path, "ollama", "")
    assert info["api_key_env"] == ""


def test_unknown_provider_rejected(tmp_path: Path):
    try:
        configure_model(tmp_path, "claude", "")
    except ValueError as exc:
        assert "openai" in str(exc)
    else:
        raise AssertionError("expected ValueError")
```

- [ ] **Step 2: Run the Python test and confirm it fails**

Run: `uv run pytest packages/core/tests/test_setup_model.py -q`

Expected: FAIL with `ModuleNotFoundError: No module named 'memrelay.setup_model'`

- [ ] **Step 3: Implement `configure_model` and the CLI**

`packages/core/src/memrelay/setup_model.py`:

```python
import json
import os
from pathlib import Path

from .config import Config
from .llm import PRESETS
from .vault import Vault

PROVIDERS = ("openai", "deepseek", "qwen", "kimi", "glm", "ollama")


def configure_model(home: Path, provider: str, model: str) -> dict:
    if provider not in PRESETS or provider not in PROVIDERS:
        raise ValueError("provider must be one of: " + ", ".join(PROVIDERS))
    previous = os.environ.get("MEMRELAY_HOME")
    os.environ["MEMRELAY_HOME"] = str(home)
    try:
        cfg = Config.load()
        cfg.persona_llm = provider
        cfg.backend = "local"
        cfg.llm.model_override = model.strip()
        cfg.llm.api_key_env = PRESETS[provider]["api_key_env"]
        Vault(cfg.vault).init()
        cfg.save()
        return {
            "provider": provider,
            "model": cfg.llm.model_override,
            "api_key_env": cfg.llm.api_key_env,
            "vault": str(cfg.vault),
        }
    finally:
        if previous is None:
            os.environ.pop("MEMRELAY_HOME", None)
        else:
            os.environ["MEMRELAY_HOME"] = previous


def main_json(home: Path, provider: str, model: str) -> None:
    print(json.dumps(configure_model(home, provider, model), ensure_ascii=False), flush=True)
```

Add this command next to `shell_api_cmd` in `packages/core/src/memrelay/cli.py`:

```python
@app.command("configure-model")
def configure_model_cmd(
    home: Path = typer.Option(..., "--home"),
    provider: str = typer.Option(..., "--provider"),
    model: str = typer.Option("", "--model"),
) -> None:
    """Write persona provider into MEMRELAY_HOME. The API key is not accepted here."""
    from .setup_model import main_json

    main_json(home, provider, model)
```

- [ ] **Step 4: Run the Python test and confirm it passes**

Run: `uv run pytest packages/core/tests/test_setup_model.py -q`

Expected: `3 passed`

- [ ] **Step 5: Add Vitest and the failing Continue-rule test**

`packages/desktop/vitest.config.ts`:

```ts
import { defineConfig } from "vitest/config";
import react from "@vitejs/plugin-react";

export default defineConfig({
  plugins: [react()],
  test: { environment: "jsdom", globals: false },
});
```

Add to `packages/desktop/package.json` scripts: `"test": "vitest run"`.

Install: `npm install -D vitest jsdom @testing-library/react @testing-library/user-event` from `packages/desktop`.

`packages/desktop/src/model.test.ts`:

```ts
import { describe, expect, it } from "vitest";
import { canContinue, PROVIDERS } from "./model";

describe("canContinue", () => {
  it("lists only the engine presets", () => {
    expect(PROVIDERS).toEqual(["openai", "deepseek", "qwen", "kimi", "glm", "ollama"]);
  });

  it("blocks a cloud provider until a key exists", () => {
    expect(canContinue("deepseek", "")).toBe(false);
    expect(canContinue("deepseek", "sk-test")).toBe(true);
  });

  it("lets ollama continue without a key", () => {
    expect(canContinue("ollama", "")).toBe(true);
  });
});
```

- [ ] **Step 6: Run the Vitest file and confirm it fails**

Run: `npm test -- src/model.test.ts` from `packages/desktop`

Expected: FAIL with `Failed to resolve import "./model"`

- [ ] **Step 7: Implement the rule and the first-run screen**

`packages/desktop/src/model.ts`:

```ts
export const PROVIDERS = ["openai", "deepseek", "qwen", "kimi", "glm", "ollama"] as const;
export type Provider = (typeof PROVIDERS)[number];

export function canContinue(provider: Provider, apiKey: string): boolean {
  if (provider === "ollama") return true;
  return apiKey.trim().length > 0;
}
```

`packages/desktop/src/ModelGate.tsx` renders only a provider `<select id="provider">`, `<input id="api-key" type="password">`, `<input id="model-name">`, and `<button type="submit">继续</button>`. The button is `disabled={!canContinue(provider, apiKey)}`. The form has no inputs named base, token, or sync. On submit it calls `onSave({ provider, apiKey, model })`.

`packages/desktop/src/ModelGate.test.tsx` renders `<ModelGate onSave={vi.fn()} />`, expects `screen.queryByLabelText("服务地址")` to be null, and expects the 继续 button to be disabled until the key field has text when the provider is `deepseek`.

- [ ] **Step 8: Implement Keychain storage in Rust**

Add to `packages/desktop/src-tauri/Cargo.toml` dependencies:

```toml
keyring = "3"
```

`packages/desktop/src-tauri/src/model.rs` defines:

```rust
pub const KEYCHAIN_SERVICE: &str = "io.memrelay.shell";
pub const KEYCHAIN_ACCOUNT: &str = "model-api-key";

pub trait KeyStore {
    fn get(&self) -> Option<String>;
    fn set(&self, secret: &str) -> Result<(), String>;
}

pub struct MemoryKeyStore {
    inner: std::sync::Mutex<Option<String>>,
}

impl KeyStore for MemoryKeyStore {
    fn get(&self) -> Option<String> {
        self.inner.lock().ok().and_then(|v| v.clone())
    }
    fn set(&self, secret: &str) -> Result<(), String> {
        *self.inner.lock().map_err(|e| e.to_string())? = Some(secret.to_string());
        Ok(())
    }
}

pub fn validate_save(provider: &str, api_key: &str) -> Result<(), String> {
    const CLOUD: [&str; 5] = ["openai", "deepseek", "qwen", "kimi", "glm"];
    if provider == "ollama" {
        return Ok(());
    }
    if CLOUD.contains(&provider) && !api_key.trim().is_empty() {
        return Ok(());
    }
    if CLOUD.contains(&provider) {
        return Err("需要 API Key".into());
    }
    Err("provider must be one of: openai, deepseek, qwen, kimi, glm, ollama".into())
}
```

`save_model` calls `validate_save`, stores a non-empty key with `keyring::Entry::new(KEYCHAIN_SERVICE, KEYCHAIN_ACCOUNT)`, then runs the resolved `memrelay` binary (Task 3’s `find_tool`) as `configure-model --home <app_data_dir> --provider <provider> --model <model>` with `MEMRELAY_HOME` set to the app data dir. Parse the single JSON line. Write `app_data_dir/model.json` containing only `provider`, `model`, and `api_key_env`. Refuse to write the file if the JSON contains the raw key string.

`model_status` reads `model.json`. `configured` is true when `provider` is `ollama`, or when `provider` is a cloud preset and `KeyStore::get` returns a non-empty string.

Unit test in `model.rs`: `validate_save("deepseek", "")` is `Err`, `validate_save("ollama", "")` is `Ok`, and a `MemoryKeyStore` round-trips the secret. Do not call the real Keychain in that test.

Declare `mod model;` in `lib.rs` and add `model_status` and `save_model` to `tauri::generate_handler![]`.

- [ ] **Step 9: Show the gate before any shell connection**

In `App.tsx`, on mount call `invoke("model_status")`. When `configured` is false, render `<ModelGate>` and nothing else (no nav, no settings). `onSave` calls `invoke("save_model", { provider, apiKey, model })`. Do not call `loadShellConfig` until that command resolves. Do not call `setSettings(true)` from this screen.

- [ ] **Step 10: Run the tests**

Run: `uv run pytest packages/core/tests/test_setup_model.py -q`

Expected: `3 passed`

Run: `npm test -- src/model.test.ts src/ModelGate.test.tsx` from `packages/desktop`

Expected: PASS

Run: `cargo test --manifest-path packages/desktop/src-tauri/Cargo.toml validate_save memory_key -- --test-threads=1`

Expected: PASS

- [ ] **Step 11: Commit**

```bash
git add packages/core/src/memrelay/setup_model.py packages/core/src/memrelay/cli.py packages/core/tests/test_setup_model.py packages/desktop/src/model.ts packages/desktop/src/model.test.ts packages/desktop/src/ModelGate.tsx packages/desktop/src/ModelGate.test.tsx packages/desktop/src-tauri/src/model.rs packages/desktop/src-tauri/src/lib.rs packages/desktop/src-tauri/Cargo.toml packages/desktop/src/App.tsx packages/desktop/package.json packages/desktop/package-lock.json packages/desktop/vitest.config.ts
git commit -s -m "feat(desktop): ask for a model before the twin starts"
```

## Task 2: Vault auto-init, and never auto-open settings

**Files:**
- Modify: `packages/desktop/src-tauri/src/lib.rs`
- Modify: `packages/desktop/src/App.tsx`
- Test: `packages/desktop/src-tauri/src/lib.rs` (`startup_plan` test)
- Test: `packages/desktop/src/App.test.tsx`

**Interfaces:**
- Consumes: `save_model` from Task 1, existing `shell_config`.
- Produces:
  - `startup_plan(local_sync_requested: bool) -> StartupPlan { shell: bool, sync: bool }`
  - `shell_config` creates `app_data_dir/vault` by running `configure-model` only when `model.json` is missing the vault, otherwise it only starts `shell-api` when the model is already configured.
  - `ShellConfig.detail` on failure is `分身暂时没连上` and does not include a filesystem path.

- [ ] **Step 1: Write the failing Rust test**

```rust
#[test]
fn consumer_startup_does_not_launch_sync() {
    let plan = startup_plan(false);
    assert!(plan.shell);
    assert!(!plan.sync);
}
```

- [ ] **Step 2: Run it and confirm it fails**

Run: `cargo test --manifest-path packages/desktop/src-tauri/Cargo.toml consumer_startup_does_not_launch_sync -- --exact`

Expected: FAIL with `cannot find function startup_plan`

- [ ] **Step 3: Implement startup and vault init**

```rust
pub struct StartupPlan {
    pub shell: bool,
    pub sync: bool,
}

pub fn startup_plan(local_sync_requested: bool) -> StartupPlan {
    StartupPlan { shell: true, sync: local_sync_requested }
}
```

Delete the `ensure_sync()` call inside `shell_config`. `shell_config` sets `MEMRELAY_HOME` to `app.path().app_data_dir()` for the child. If `app_data_dir/vault` does not exist and `model.json` exists, run `<memrelay> configure-model` again with the saved provider and model (empty key path; the key stays in the Keychain). Then spawn `shell-api --port 8787 --token-file <app_data>/shell-api.token` with the preset env var from `model.json` set to the Keychain secret. Token file mode stays `0600`.

Replace the missing-binary error:

```rust
return Err("分身暂时没连上".into());
```

Remove the sentence that mentions `~/.local/bin/memrelay`.

- [ ] **Step 4: Stop the UI from opening settings when the shell is down**

Delete this line from the mount effect in `App.tsx`:

```tsx
if (!cfg.ready) setSettings(true);
```

`packages/desktop/src/App.test.tsx` renders `App` with `invoke` mocked so `model_status` returns `{ configured: true, provider: "ollama", model: "" }` and `shell_config` returns `{ base: "http://127.0.0.1:8787", token: "t", ready: false, detail: "分身暂时没连上" }`. Assert `screen.queryByRole("dialog")` is null and `screen.getByRole("navigation", { name: "主导航" })` is present.

- [ ] **Step 5: Run the tests**

Run: `cargo test --manifest-path packages/desktop/src-tauri/Cargo.toml consumer_startup_does_not_launch_sync -- --exact`

Expected: PASS

Run: `npm test -- src/App.test.tsx` from `packages/desktop`

Expected: PASS

- [ ] **Step 6: Commit**

```bash
git add packages/desktop/src-tauri/src/lib.rs packages/desktop/src/App.tsx packages/desktop/src/App.test.tsx
git commit -s -m "feat(desktop): init the vault in app data without opening settings"
```

## Task 3: Consumer sidecar lookup fails closed

**Files:**
- Modify: `packages/desktop/src-tauri/src/lib.rs`
- Test: `packages/desktop/src-tauri/src/lib.rs`

**Interfaces:**
- Consumes: `tool_candidates` in `lib.rs`.
- Produces: `LaunchMode::{Consumer, Dev}` and `launch_mode() -> LaunchMode`. `find_tool` uses `launch_mode()`. Consumer candidates are only `<exe_dir>/<name>` and `<exe_dir>/../Resources/<name>`.

- [ ] **Step 1: Replace the existing candidate test with a consumer test that fails**

Keep the current dev-order assertions under the name `dev_candidates_include_user_installs`. Add:

```rust
#[test]
fn consumer_candidates_are_only_inside_the_app() {
    let got = tool_candidates(
        "memrelay",
        LaunchMode::Consumer,
        Some(Path::new("/opt/custom/memrelay")),
        Some(Path::new("/Users/me")),
        Some(Path::new("/App.app/Contents/MacOS")),
    );
    assert_eq!(
        got,
        vec![
            PathBuf::from("/App.app/Contents/MacOS/memrelay"),
            PathBuf::from("/App.app/Contents/MacOS/../Resources/memrelay"),
        ]
    );
}
```

Change `tool_candidates`’s signature in the test to the new one so this does not compile yet.

- [ ] **Step 2: Run it and confirm it fails**

Run: `cargo test --manifest-path packages/desktop/src-tauri/Cargo.toml consumer_candidates_are_only_inside_the_app -- --exact`

Expected: FAIL with a compile error on `LaunchMode`

- [ ] **Step 3: Implement the two lookup modes**

```rust
#[derive(Clone, Copy, PartialEq, Eq)]
pub enum LaunchMode {
    Consumer,
    Dev,
}

pub fn launch_mode() -> LaunchMode {
    if cfg!(debug_assertions) {
        LaunchMode::Dev
    } else {
        LaunchMode::Consumer
    }
}

pub fn tool_candidates(
    name: &str,
    mode: LaunchMode,
    from_env: Option<&std::path::Path>,
    home: Option<&std::path::Path>,
    exe_dir: Option<&std::path::Path>,
) -> Vec<PathBuf> {
    let mut bundled = Vec::new();
    if let Some(dir) = exe_dir {
        bundled.push(dir.join(name));
        bundled.push(dir.join("../Resources").join(name));
    }
    if mode == LaunchMode::Consumer {
        return bundled;
    }
    let mut out = Vec::new();
    if let Some(path) = from_env {
        out.push(path.to_path_buf());
    }
    out.extend(bundled);
    if let Some(home) = home {
        out.push(home.join(".local/bin").join(name));
    }
    out.push(PathBuf::from("/opt/homebrew/bin").join(name));
    out.push(PathBuf::from("/usr/local/bin").join(name));
    out
}
```

`find_tool` passes `launch_mode()`. In `LaunchMode::Dev` it still appends `PATH`, matching today’s behavior. In `LaunchMode::Consumer` it does not read `PATH`, `MEMRELAY_BIN`, or `HOME`.

- [ ] **Step 4: Run the Rust tests**

Run: `cargo test --manifest-path packages/desktop/src-tauri/Cargo.toml --lib candidates -- --test-threads=1`

Expected: `dev_candidates_include_user_installs` and `consumer_candidates_are_only_inside_the_app` PASS

- [ ] **Step 5: Commit**

```bash
git add packages/desktop/src-tauri/src/lib.rs
git commit -s -m "fix(desktop): resolve the consumer sidecar only inside the app"
```

## Task 4: 分身 chat thread

**Files:**
- Create: `packages/desktop/src/chat.ts`
- Test: `packages/desktop/src/chat.test.ts`
- Create: `packages/desktop/src/ChatThread.tsx`
- Test: `packages/desktop/src/ChatThread.test.tsx`
- Modify: `packages/desktop/src/App.tsx`
- Modify: `packages/desktop/src/styles.css`
- Modify: `packages/desktop/src-tauri/src/lib.rs`

**Interfaces:**
- Consumes: `askTwin` and `Answer` from `packages/desktop/src/api.ts`. `SAMPLE_ASK` is `我偏好什么？`.
- Produces:
  - `ChatMessage` with `id`, `role: "user" | "twin"`, `text`, optional `pending`, `disclosure`, `citations`, `error: "model" | undefined`
  - `pushUser(messages, text)`, `markPending(messages)`, `finishTwin(messages, answer)`, `failTwin(messages)`, `parseTranscript(raw)`, `serializeTranscript(messages)`
  - Rust `read_transcript(app) -> String` and `write_transcript(app, body: String) -> Result<(), String>` using `app_data_dir/transcript-self.json`

- [ ] **Step 1: Write the failing thread tests**

```ts
import { describe, expect, it } from "vitest";
import { SAMPLE_ASK, finishTwin, markPending, parseTranscript, pushUser, serializeTranscript } from "./chat";

const answer = {
  answer: "你喜欢抹茶。",
  citations: [{ n: 1, id: "饮品.md", title: "饮品", snippet: "偏好：抹茶。" }],
  disclosure: "我是用户的 AI 分身（MemRelay），依据其已审核的记忆作答，可能不准确，不代表本人表态或承诺。",
  confidence: 0.8,
  refused: false,
  face_id: "self",
};

describe("thread", () => {
  it("sends the sample ask into a user bubble and a pending twin bubble", () => {
    const next = markPending(pushUser([], SAMPLE_ASK));
    expect(next[0]).toMatchObject({ role: "user", text: "我偏好什么？" });
    expect(next[1]).toMatchObject({ role: "twin", pending: true });
  });

  it("keeps citations and disclosure on the finished twin bubble", () => {
    const done = finishTwin(markPending(pushUser([], SAMPLE_ASK)), answer);
    expect(done[1].pending).toBe(false);
    expect(done[1].citations?.[0].title).toBe("饮品");
    expect(done[1].disclosure).toContain("AI 分身");
  });

  it("round-trips the transcript", () => {
    const done = finishTwin(markPending(pushUser([], "你好")), answer);
    expect(parseTranscript(serializeTranscript(done))).toEqual(done);
  });
});
```

- [ ] **Step 2: Run it and confirm it fails**

Run: `npm test -- src/chat.test.ts` from `packages/desktop`

Expected: FAIL with `Failed to resolve import "./chat"`

- [ ] **Step 3: Implement the pure transitions**

`packages/desktop/src/chat.ts` uses `crypto.randomUUID()` for `id`. `finishTwin` replaces the last message when it is a pending twin bubble; it copies `answer.answer`, `answer.disclosure`, and `answer.citations`. `parseTranscript` returns `[]` when `raw` is empty or not an array. `serializeTranscript` is `JSON.stringify`.

- [ ] **Step 4: Render the thread and persist it**

`ChatThread` props: `{ messages: ChatMessage[]; draft: string; onDraft: (value: string) => void; onSend: (text: string) => void; disabled: boolean }`.

- Empty `messages`: a button named `我偏好什么？` calls `onSend(SAMPLE_ASK)`.
- Each message is `<article class="bubble user">` or `<article class="bubble twin">`.
- A pending twin bubble text is `正在回答…`.
- Citations render as `<ol>` items `[n] title` plus the snippet. Disclosure is `<p class="disclosure">`.
- The composer is `<textarea id="composer">`. Enter without Shift, and without `event.nativeEvent.isComposing`, calls `onSend(draft)`.
- The view scrolls the last article into view after `messages` changes.

`App.tsx` replaces the single `answer` card. On mount after the model gate, `invoke("read_transcript")` then `parseTranscript`. After every `finishTwin` or `failTwin`, `invoke("write_transcript", { body: serializeTranscript(messages) })`.

Rust commands:

```rust
#[tauri::command]
fn read_transcript(app: tauri::AppHandle) -> String {
    let Ok(dir) = app.path().app_data_dir() else { return String::new() };
    std::fs::read_to_string(dir.join("transcript-self.json")).unwrap_or_default()
}

#[tauri::command]
fn write_transcript(app: tauri::AppHandle, body: String) -> Result<(), String> {
    let dir = app.path().app_data_dir().map_err(|e| e.to_string())?;
    std::fs::create_dir_all(&dir).map_err(|e| e.to_string())?;
    std::fs::write(dir.join("transcript-self.json"), body).map_err(|e| e.to_string())
}
```

Register both in `generate_handler`.

CSS, appended to `styles.css`, uses only the existing paper tokens:

```css
.thread { display: flex; flex-direction: column; gap: 0.75rem; min-height: 24rem; }
.bubble { max-width: 36rem; padding: 0.8rem 1rem; border-radius: 16px; background: #fffdf8; }
.bubble.user { margin-left: auto; background: #efe7d8; }
.composer { display: flex; gap: 0.5rem; margin-top: 0.8rem; }
.composer textarea { flex: 1; min-height: 3.2rem; border-radius: 12px; border: 1px solid #d9d1c3; background: #fffdf8; }
.chip { border: 1px solid #d9d1c3; background: #fffdf8; border-radius: 999px; padding: 0.35rem 0.9rem; }
```

`ChatThread.test.tsx`: render with `messages={[]}`; the dialog role is absent; clicking `我偏好什么？` calls `onSend` with that string.

- [ ] **Step 5: Run the frontend tests**

Run: `npm test -- src/chat.test.ts src/ChatThread.test.tsx` from `packages/desktop`

Expected: PASS

- [ ] **Step 6: Commit**

```bash
git add packages/desktop/src/chat.ts packages/desktop/src/chat.test.ts packages/desktop/src/ChatThread.tsx packages/desktop/src/ChatThread.test.tsx packages/desktop/src/App.tsx packages/desktop/src/styles.css packages/desktop/src-tauri/src/lib.rs
git commit -s -m "feat(desktop): make 分身 a persisted chat thread"
```

## Task 5: Everyday settings, pair, quiet sync

**Files:**
- Create: `packages/desktop/src/SettingsDialog.tsx`
- Test: `packages/desktop/src/SettingsDialog.test.tsx`
- Modify: `packages/desktop/src/App.tsx`
- Modify: `packages/desktop/src-tauri/src/lib.rs`

**Interfaces:**
- Consumes: `pairSync`, `runSync`, `initialSync()` from `urls.sync`, `save_model`, `LaunchMode`.
- Produces:
  - `use_local_sync(app) -> Result<(), String>` spawns bundled `memrelay-sync --host 127.0.0.1 --port 8790` only.
  - `open_data_dir(app) -> Result<(), String>` runs `/usr/bin/open` on `app_data_dir/vault`.
  - After a successful `pairSync`, `App` calls `runSync()` without `setTab` and without `setSettings(true)`. Success does not set a banner. Failure sets `syncMsg` to `同步没有完成` inside the dialog only.

- [ ] **Step 1: Write the failing settings test**

```tsx
import { render, screen } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";
import { SettingsDialog } from "./SettingsDialog";

describe("SettingsDialog", () => {
  it("keeps engineer fields inside a closed Advanced group", () => {
    render(
      <SettingsDialog
        version="0.2.0"
        distribution="开发构建"
        provider="deepseek"
        model=""
        syncServer="https://memrelay-sync.preview.tencent-zeabur.cn"
        base="http://127.0.0.1:8787"
        token=""
        localSync="http://127.0.0.1:8790"
        pairCode=""
        pairing=""
        qr=""
        syncMsg=""
        onClose={vi.fn()}
        onSaveModel={vi.fn()}
        onPair={vi.fn()}
        onUseLocal={vi.fn()}
        onSyncOnce={vi.fn()}
        onOpenData={vi.fn()}
        onBase={vi.fn()}
        onToken={vi.fn()}
        onLocalSync={vi.fn()}
      />,
    );
    expect(screen.getByRole("button", { name: "生成配对码" })).toBeTruthy();
    const advanced = screen.getByText("高级").closest("details");
    expect(advanced?.open).toBe(false);
    expect(advanced?.textContent).toContain("服务地址");
    expect(advanced?.textContent).toContain("使用本机");
    expect(advanced?.textContent).toContain("同步一次");
    expect(advanced?.textContent).toContain("打开数据目录");
  });
});
```

- [ ] **Step 2: Run it and confirm it fails**

Run: `npm test -- src/SettingsDialog.test.tsx` from `packages/desktop`

Expected: FAIL with `Failed to resolve import "./SettingsDialog"`

- [ ] **Step 3: Build the dialog and the two commands**

Everyday section, in order: provider select, password input labeled `API Key`, optional model input, button `保存模型`, button `生成配对码`, the existing QR image and pairing `<textarea aria-label="配对内容">` when `pairing` is non-empty, and about text `{version}` plus `{distribution}`.

Advanced is `<details><summary>高级</summary>…</details>` with no `open` attribute. Inside: service URL, token, local sync URL, buttons 使用本机, 同步一次, 打开数据目录.

`use_local_sync` uses `find_tool("memrelay-sync")` and `spawn_detached`. If the binary is missing it returns `分身暂时没连上`. It does not print the bind address to the webview.

`open_data_dir` creates `app_data_dir/vault` if needed and opens that directory.

`App` passes `distribution` from `import.meta.env.VITE_DISTRIBUTION === "notarized" ? "已公证" : "开发构建"`. Version comes from `@tauri-apps/api/app` `getVersion()`, falling back to `0.2.0` when the import throws in Vitest.

`生成配对码` calls `pairSync(syncServer)` with the prefilled official URL, then `runSync()`. On `runSync` rejection, set `syncMsg` to `同步没有完成` and leave the dialog’s open state unchanged. Do not put `8787` or `127.0.0.1:8787` in `syncMsg`.

- [ ] **Step 4: Run the settings test**

Run: `npm test -- src/SettingsDialog.test.tsx` from `packages/desktop`

Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add packages/desktop/src/SettingsDialog.tsx packages/desktop/src/SettingsDialog.test.tsx packages/desktop/src/App.tsx packages/desktop/src-tauri/src/lib.rs
git commit -s -m "feat(desktop): split everyday settings from advanced sync controls"
```

## Task 6: Error states from the spec

**Files:**
- Create: `packages/desktop/src/errors.ts`
- Test: `packages/desktop/src/errors.test.ts`
- Modify: `packages/desktop/src/App.tsx`
- Modify: `packages/desktop/src/api.ts`
- Test: `packages/core/tests/test_oobx_answer.py`
- Modify: `packages/core/src/memrelay/twin.py` only when the test below fails

**Interfaces:**
- Consumes: `ChatMessage.error`, `shell_config`, `finishTwin`, `failTwin`.
- Produces: `COPY` with `sidecarDown = "分身暂时没连上"`, `retry = "重试"`, `modelRejected = "这次没有答上来。"`, `openModel = "去填写模型"`, `syncFailed = "同步没有完成"`, `memoryEmpty = "还没有记忆。问过分身后，写下来的才会出现在这里。"`, `activityEmpty = "过去几天没有自动写入的记忆。"`.

- [ ] **Step 1: Write the failing copy test**

```ts
import { describe, expect, it } from "vitest";
import { COPY } from "./errors";

describe("COPY", () => {
  it("hides hosts and quarantine instructions", () => {
    const blob = Object.values(COPY).join("\n");
    expect(blob).not.toContain("127.0.0.1");
    expect(blob).not.toContain("8787");
    expect(blob).not.toContain("xattr");
    expect(blob).not.toContain("右键");
    expect(COPY.sidecarDown).toBe("分身暂时没连上");
    expect(COPY.modelRejected).toBe("这次没有答上来。");
  });
});
```

- [ ] **Step 2: Run it and confirm it fails**

Run: `npm test -- src/errors.test.ts` from `packages/desktop`

Expected: FAIL with `Failed to resolve import "./errors"`

- [ ] **Step 3: Implement the strings and wire them**

`errors.ts` exports `COPY` with the seven strings above.

In `App.tsx`:

- When `shell_config.ready` is false, show `<p role="status">{COPY.sidecarDown}</p>` and `<button type="button">{COPY.retry}</button>`. The button calls `loadShellConfig()` again. It does not call `setSettings`.
- `askTwin` rejection calls `failTwin`, which sets the pending twin bubble’s `text` to `COPY.modelRejected` and `error` to `"model"`. That bubble also renders a button `去填写模型` that opens settings. The settings dialog opens on the everyday model fields, not with Advanced `open`.
- `catch` in `refresh` for 记忆 / 动态 uses `COPY.sidecarDown` on the main window, not “请检查设置里的地址和令牌”.
- Empty memory list renders `COPY.memoryEmpty` instead of only `没有找到记忆。` when the query is empty.
- Empty activity digest renders `COPY.activityEmpty`.
- A twin bubble whose `text` contains `我不知道——我的记忆里没有相关内容` still renders `disclosure`. That is the empty-vault state. Do not replace it with a settings link.

`api.ts` `askTwin` stays a POST to `/v1/twin/ask`. Do not catch inside `api.ts`; let `App` classify.

- [ ] **Step 4: Lock the cited-answer fallback in the engine**

`packages/core/tests/test_oobx_answer.py`:

```python
from pathlib import Path

import pytest

from memrelay.faces import ensure_default_faces
from memrelay.schema import Note
from memrelay.twin import answer_as_me
from memrelay.vault import Vault


class SearchOnly:
    async def search(self, query: str, limit: int = 10):
        return ["notes/drink.md"]


@pytest.mark.asyncio
async def test_note_is_cited_when_the_model_returns_no_markers(tmp_path: Path):
    vault = Vault(tmp_path)
    vault.init()
    ensure_default_faces(vault)
    path = tmp_path / "notes" / "drink.md"
    path.parent.mkdir(parents=True)
    path.write_text(
        Note(title="饮品", body="偏好：抹茶。", status="active", visibility="private").to_markdown(),
        encoding="utf-8",
    )

    class Bare:
        name = "bare"

        def complete(self, system: str, user: str) -> str:
            return "你喜欢抹茶。"

    result = await answer_as_me(
        "我偏好什么？", vault=vault, backend=SearchOnly(), llm=Bare(), face_id="self"
    )
    titles = [c["title"] for c in result["citations"]]
    assert "饮品" in titles
    assert "AI 分身" in result["disclosure"]
```

`retrieve` reads the markdown file `backend.search` returns. It does not call `get_note`. `face_id="self"` needs `ensure_default_faces`, which writes `.memrelay/faces/self.toml`. `Note.to_markdown` is the writer in `schema.py`.

`_llm_cited` in `twin.py` already returns `None` when the model prose has no valid `[n]` markers (`test_llm_answer_citation_guard` covers “我是 CEO。”). That `None` is the rules fallback, so this test should pass with no engine edit. If it fails because uncited prose is treated as unknown, change only that return to `None`. Do not change the `UNKNOWN` branch or the refusal strings.

- [ ] **Step 5: Run the tests**

Run: `npm test -- src/errors.test.ts` from `packages/desktop`

Expected: PASS

Run: `uv run pytest packages/core/tests/test_oobx_answer.py -q`

Expected: `1 passed`

- [ ] **Step 6: Commit**

```bash
git add packages/desktop/src/errors.ts packages/desktop/src/errors.test.ts packages/desktop/src/App.tsx packages/desktop/src/api.ts packages/core/tests/test_oobx_answer.py packages/core/src/memrelay/twin.py
git commit -s -m "feat(desktop): show friendly failures and keep citations"
```

## Task 7: Freeze the sidecars with PyInstaller

**Files:**
- Create: `packages/desktop/sidecar/memrelay_entry.py`
- Create: `packages/desktop/sidecar/memrelay_sync_entry.py`
- Create: `packages/desktop/sidecar/build-macos.sh`
- Modify: `packages/desktop/src-tauri/tauri.conf.json`
- Modify: `.gitignore`

**Interfaces:**
- Consumes: console scripts `memrelay = memrelay.cli:app` and `memrelay-sync = memrelay_sync.app:main`.
- Produces: executable files `packages/desktop/src-tauri/resources/memrelay` and `packages/desktop/src-tauri/resources/memrelay-sync`. `tauri.conf.json` `bundle.resources` lists both. `tauri dev` does not require them. `tauri build` fails if they are missing.

- [ ] **Step 1: Add the entry scripts**

`packages/desktop/sidecar/memrelay_entry.py`:

```python
from memrelay.cli import app

if __name__ == "__main__":
    app()
```

`packages/desktop/sidecar/memrelay_sync_entry.py`:

```python
from memrelay_sync.app import main

if __name__ == "__main__":
    raise SystemExit(main())
```

- [ ] **Step 2: Add the freeze script**

`packages/desktop/sidecar/build-macos.sh`:

```bash
#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")"
root="$(cd ../../.. && pwd)"
uv venv --python 3.12 .venv
uv pip install --python .venv/bin/python \
  "pyinstaller==6.11.1" \
  "$root/packages/core" \
  "$root/packages/sync"
rm -rf build dist
.venv/bin/pyinstaller --noconfirm --clean --onefile --name memrelay \
  --collect-submodules memrelay \
  --hidden-import uvicorn.logging \
  --hidden-import uvicorn.loops.auto \
  --hidden-import uvicorn.protocols.http.auto \
  --hidden-import uvicorn.lifespan.on \
  memrelay_entry.py
.venv/bin/pyinstaller --noconfirm --clean --onefile --name memrelay-sync \
  --collect-submodules memrelay_sync \
  --hidden-import uvicorn.logging \
  --hidden-import uvicorn.loops.auto \
  --hidden-import uvicorn.protocols.http.auto \
  --hidden-import uvicorn.lifespan.on \
  memrelay_sync_entry.py
dest="$root/packages/desktop/src-tauri/resources"
mkdir -p "$dest"
cp dist/memrelay dist/memrelay-sync "$dest/"
chmod 755 "$dest/memrelay" "$dest/memrelay-sync"
"$dest/memrelay" --help >/dev/null
"$dest/memrelay-sync" --help >/dev/null
```

`chmod +x` the script. It is macOS aarch64 only because `macos-latest` in the consumer workflow is arm64. Do not run it on the Ubuntu CI job.

- [ ] **Step 3: Point Tauri at the resources**

In `packages/desktop/src-tauri/tauri.conf.json` `bundle`, add:

```json
"resources": [
  "resources/memrelay",
  "resources/memrelay-sync"
]
```

Leave `beforeBuildCommand` as `npm run build`. The release workflow runs `build-macos.sh` before `npm run tauri build`. A checkout without those two files cannot produce a consumer bundle; that failure is correct.

- [ ] **Step 4: Smoke the frozen binary on a Mac**

Run: `packages/desktop/sidecar/build-macos.sh`

Then:

```bash
tmpdir=$(mktemp -d)
packages/desktop/src-tauri/resources/memrelay configure-model --home "$tmpdir" --provider ollama --model ""
test -d "$tmpdir/vault"
```

Expected: exit 0, and `config.toml` contains `backend = "local"`.

- [ ] **Step 5: Commit the scripts, not the frozen binaries**

Add `packages/desktop/src-tauri/resources/memrelay` and `memrelay-sync` to `.gitignore` if they are not already ignored. Commit the Python entries, the shell script, the `tauri.conf.json` resources list, and the gitignore lines.

```bash
git add packages/desktop/sidecar/memrelay_entry.py packages/desktop/sidecar/memrelay_sync_entry.py packages/desktop/sidecar/build-macos.sh packages/desktop/src-tauri/tauri.conf.json .gitignore
git commit -s -m "build(desktop): freeze memrelay and memrelay-sync with PyInstaller"
```

## Task 8: Sign, notarize, staple, fail closed

**Files:**
- Modify: `.github/workflows/release-macos.yml`
- Modify: `packages/desktop/src-tauri/Entitlements.plist`
- Modify: `packages/website/index.html`
- Modify: `README.md`
- Modify: `README.zh-CN.md`
- Modify: `packages/desktop/README.md`

**Interfaces:**
- Consumes: asset copy step that already writes `MemRelay-${version}-aarch64.dmg` and `MemRelay-${version}-macos.zip`.
- Produces: a job that exits 1 before `tauri build` when any required secret is empty, and that uploads only after `stapler validate` succeeds. Required secret names, all non-empty strings in the GitHub Actions environment:

  - `APPLE_CERTIFICATE` (base64-encoded Developer ID Application `.p12`)
  - `APPLE_CERTIFICATE_PASSWORD`
  - `APPLE_SIGNING_IDENTITY` (`Developer ID Application: … (TEAMID)`, never `""`)
  - `APPLE_PROVIDER_SHORT_NAME` (10-character team id)
  - `APPLE_TEAM_ID` (same team id)
  - `APPLE_ID`
  - `APPLE_APP_SPECIFIC_PASSWORD`

  No other secret is required. Do not invent values for these.

- [ ] **Step 1: Add the keychain entitlement without sandboxing**

Replace `packages/desktop/src-tauri/Entitlements.plist` with:

```xml
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
  <key>com.apple.security.network.client</key>
  <true/>
  <key>keychain-access-groups</key>
  <array>
    <string>$(AppIdentifierPrefix)io.memrelay.shell</string>
  </array>
</dict>
</plist>
```

Do not add `com.apple.security.app-sandbox`. Sandbox would block the sidecar spawn.

- [ ] **Step 2: Replace the release workflow body**

The job stays `runs-on: macos-latest` and `contents: write`. Before Node setup, a step `Require Apple credentials` runs:

```bash
required=(
  APPLE_CERTIFICATE
  APPLE_CERTIFICATE_PASSWORD
  APPLE_SIGNING_IDENTITY
  APPLE_PROVIDER_SHORT_NAME
  APPLE_TEAM_ID
  APPLE_ID
  APPLE_APP_SPECIFIC_PASSWORD
)
for name in "${required[@]}"; do
  if [ -z "${!name}" ]; then
    echo "missing Apple secret: $name" >&2
    exit 1
  fi
done
```

Next step imports the certificate into a job-local keychain. `KEYCHAIN_PASSWORD` is `$(openssl rand -base64 24)` in that step, not a repository secret:

```bash
echo "$APPLE_CERTIFICATE" | base64 --decode > "$RUNNER_TEMP/cert.p12"
security create-keychain -p "$KEYCHAIN_PASSWORD" "$RUNNER_TEMP/app.keychain"
security default-keychain -s "$RUNNER_TEMP/app.keychain"
security unlock-keychain -p "$KEYCHAIN_PASSWORD" "$RUNNER_TEMP/app.keychain"
security set-keychain-settings -lut 21600 "$RUNNER_TEMP/app.keychain"
security import "$RUNNER_TEMP/cert.p12" -k "$RUNNER_TEMP/app.keychain" -P "$APPLE_CERTIFICATE_PASSWORD" -T /usr/bin/codesign
security set-key-partition-list -S apple-tool:,apple:,codesign: -s -k "$KEYCHAIN_PASSWORD" "$RUNNER_TEMP/app.keychain"
```

Then `packages/desktop/sidecar/build-macos.sh`. Then codesign both resources:

```bash
codesign --force --options runtime --timestamp \
  --sign "$APPLE_SIGNING_IDENTITY" \
  packages/desktop/src-tauri/resources/memrelay \
  packages/desktop/src-tauri/resources/memrelay-sync
```

`npm run tauri build` in `packages/desktop` with env:

```bash
APPLE_SIGNING_IDENTITY
APPLE_PROVIDER_SHORT_NAME
VITE_DISTRIBUTION=notarized
```

Do not pass an empty `APPLE_SIGNING_IDENTITY`. After the bundle exists:

```bash
codesign --verify --strict --verbose=2 "packages/desktop/src-tauri/target/release/bundle/macos/忆桥分身.app"
xcrun notarytool submit "$MEMRELAY_DMG" \
  --apple-id "$APPLE_ID" \
  --password "$APPLE_APP_SPECIFIC_PASSWORD" \
  --team-id "$APPLE_TEAM_ID" \
  --wait
xcrun stapler staple "$MEMRELAY_DMG"
xcrun stapler validate "$MEMRELAY_DMG"
```

`softprops/action-gh-release@v2` runs only if the staple step succeeded. `prerelease: false`. `body` is:

```text
Notarized macOS build of 忆桥分身.
Double-click the disk image to install.
Assets: MemRelay-<version>-aarch64.dmg and MemRelay-<version>-macos.zip.
```

Generate `<version>` from `packages/desktop/package.json` in the same step that copies the ASCII filenames. Keep those filenames. Delete the sentences “Unsigned”, “Gatekeeper will warn”, “right-click the app and choose Open”, and “No Apple notarization.”

- [ ] **Step 3: Remove quarantine instructions from the download copy**

In `packages/website/index.html`, delete the sentence `第一次请右键打开。` The source-build `<details>` may still show `npm run tauri build` for developers, and must say the website button is the notarized disk image, not that local bundle.

In `README.md` and `README.zh-CN.md`, the download section points at `/releases/latest` and does not tell the reader to right-click or run `xattr`.

In `packages/desktop/README.md`, replace the Gatekeeper right-click paragraph with: a local `npm run tauri build` without the Apple secrets is a developer bundle and is not the file the website links to.

Search the four files for `xattr`, `右键打开`, and `right-click`. The consumer sentences are gone. A mention that the CI job refuses to publish when secrets are missing is allowed.

- [ ] **Step 4: Confirm the workflow text**

Run:

```bash
rg -n "xattr|右键|right-click|Unsigned macOS" .github/workflows/release-macos.yml packages/website/index.html README.md README.zh-CN.md packages/desktop/README.md
```

Expected: no matches in those files. `release-macos.yml` contains every name in the required-secret list.

- [ ] **Step 5: Commit**

```bash
git add .github/workflows/release-macos.yml packages/desktop/src-tauri/Entitlements.plist packages/website/index.html README.md README.zh-CN.md packages/desktop/README.md
git commit -s -m "ci: notarize the macOS download or fail closed"
```

Do not push a `v*` tag in this task. Tagging publishes a release, and the job will fail until the seven secrets exist.

## Task 9: Notarized DMG checklist

**Files:**
- Modify: none. This task is the manual acceptance run after Task 8 is green on a tag.

**Interfaces:**
- Consumes: the release URL printed by the green `release-macos` run, `COPY`, `SAMPLE_ASK`, and the vault path `~/Library/Application Support/io.memrelay.shell/vault`.

- [ ] **Step 1: Confirm the job failed closed or shipped stapled**

If the seven Apple secrets are absent, open the Actions run and confirm the step `Require Apple credentials` exited 1 and that no new asset was uploaded to `/releases/latest`. Stop. That is the expected result until a human adds the secrets. Do not upload an unsigned DMG to fill the gap.

When the secrets exist and the run is green:

- [ ] **Step 2: Install by double-click**

On a Mac user account that has never installed 忆桥分身, download `MemRelay-<version>-aarch64.dmg` in Chrome from the release page. Open the DMG from Finder. Copy `忆桥分身.app` to `/Applications`. Double-click it. Do not run `xattr`. Expected: the app opens. Gatekeeper does not offer only “Move to Trash”.

- [ ] **Step 3: Pass the one model screen**

Expected: the first window has provider, API Key, optional model name, and 继续. It has no service URL and no token field. Choose `deepseek` or another cloud preset, enter a real key, and continue. Expected: the next view is 分身 / 记忆 / 动态, and settings is closed.

- [ ] **Step 4: Empty vault**

Click `我偏好什么？`. Expected: a user bubble with that text, then a twin bubble whose disclosure contains `AI 分身`, and whose answer contains `我不知道` or the equivalent engine sentence that nothing is remembered. Settings did not open. This step alone does not accept the build.

- [ ] **Step 5: Cited answer**

Quit the app. Write this file to `~/Library/Application Support/io.memrelay.shell/vault/notes/drink.md`:

```markdown
---
title: 饮品
type: preference
status: active
visibility: private
---

偏好：抹茶。
```

Launch the app again with a double-click. Expected: the previous thread is still there. Send `我偏好什么？` again. Expected: the new twin bubble shows disclosure `AI 分身` and a citation whose title is `饮品`. The bubble is not a hardcoded fixture; the note file is the only source of `抹茶`.

- [ ] **Step 6: Memory, activity, and a quiet pair**

Open 记忆. Expected: the drink note or the empty copy from `COPY.memoryEmpty` if search has not loaded it yet, and no settings dialog. Open 动态. Expected: no settings dialog. Open 设置 on purpose. Expected: 高级 is collapsed. Generate a pairing code. Expected: 分身 stays the underlying page, the QR is inside settings, and a sync failure shows `同步没有完成` only there.

- [ ] **Step 7: Record the result in the commit that tags the release**

The tag message lists the release URL, `MemRelay-<version>-aarch64.dmg`, `MemRelay-<version>-macos.zip`, and that Steps 2 through 6 passed. Do not tag if Step 5 failed.

## Self-review

| Spec success criterion | Tasks |
| --- | --- |
| 1. Chat thread, sample ask, loading, disclosure, citations, persisted transcript, no settings on empty | Task 4. Empty state does not open settings: Task 2 and Task 4 tests. |
| 2. Double-click notarized DMG, one model screen, real engine answer, citation when a note exists, empty reply insufficient, no mock | Task 1 (model screen and key), Task 2 (app-data vault), Task 3 (bundled lookup only), Task 6 (citation fallback), Task 7 (PyInstaller), Task 8 (notarize or fail), Task 9 Steps 2–5. |
| 3. Home remains 分身 / 记忆 / 动态; empty screens do not open Advanced | Task 2 test, Task 6 empty copy, Task 9 Step 6. |
| 4. Everyday model + pair + about; Advanced holds service URL, token, local URL, 使用本机, sync once, open data dir | Task 5. |
| 5. Signed, notarized, stapled DMG and sidecars; missing secrets do not become the website download | Task 8. Task 9 Step 1 is the fail-closed observation. |

Error-table rows: sidecar down and 重试 in Task 6; model rejection in Task 6; empty vault bubble in Task 6 and Task 9 Step 4; sync failure inside settings in Task 5; missing Apple credentials in Task 8.

No product choice is left open. PyInstaller 6.11.1 is the freezer. The `local` backend is the consumer vault. Apple secret names are fixed above.
