# 忆桥分身桌面壳 / MemRelay desktop shell

**Status:** Tray app with three home screens: 分身 / 记忆 / 动态.
The window talks only to the local shell API. 设置 also pairs a phone and runs one sync against `memrelay-sync`. The 同步服务 field starts at the official URL in `packages/website/urls.json` (`https://memrelay-sync.preview.tencent-zeabur.cn`). 使用本机 fills `http://127.0.0.1:8790`, which is what the app starts when that port is free. The phone app is `packages/mobile`.

## What you need

- An initialized MemRelay vault (`memrelay init`, default `~/MemRelay`)
- `memrelay` installed where a Finder launch can see it (not only a shell `PATH`). `uv tool install` puts it in `~/.local/bin/memrelay`. Homebrew's `/opt/homebrew/bin/memrelay` and `/usr/local/bin/memrelay` count too, as does `MEMRELAY_BIN`, or a copy next to the app binary (`Contents/MacOS/memrelay`).
- Optional `memrelay-sync` in the same kind of place (`~/.local/bin/memrelay-sync` or `MEMRELAY_SYNC_BIN`). The app starts it on `127.0.0.1:8790` when that port is free.
- Node.js 20+ and Rust 1.90+ to build. macOS uses the system WebKit. Linux dev needs `webkit2gtk-4.1`.

The app starts that `memrelay` with an absolute path, so a GUI launch does not use the terminal `PATH`. If nothing is listening on `127.0.0.1:8787`, it runs:

```bash
memrelay shell-api --port 8787 --token-file <app data>/shell-api.token
```

The token file is mode `0600`. The window reads that token. It never shows MCP, config files, or terminal commands on the home screens.

Closing the window hides it in the tray. Quit from the tray menu (退出).

## Run on macOS

```bash
xcode-select --install
curl --proto '=https' --tlsv1.2 -sSf https://sh.rustup.rs | sh
# from the memrelay repo root, so `memrelay` is on PATH
uv sync
export PATH="$(pwd)/.venv/bin:$PATH"

cd packages/desktop
npm install
npm run tauri dev
```

## Build a macOS .app and .dmg

On a Mac, from `packages/desktop`:

```bash
npm install
npm run tauri build
```

Unsigned artifacts:

- `src-tauri/target/release/bundle/macos/忆桥分身.app`
- `src-tauri/target/release/bundle/dmg/忆桥分身_0.1.0_aarch64.dmg` (or `x64`, matching the Mac you built on)

`bundle.targets` is `app` and `dmg`. `signingIdentity` and `providerShortName` are `null`, so the local build is unsigned. `shortcut: no Apple certificate in this repo, set the env vars below when you have a Developer ID.`

```bash
export APPLE_SIGNING_IDENTITY="Developer ID Application: Your Name (TEAMID)"
export APPLE_PROVIDER_SHORT_NAME="TEAMID"
npm run tauri build
```

Gatekeeper will warn on the unsigned app. Right-click the `.app` and choose Open the first time. Entitlements for a signed build are `src-tauri/Entitlements.plist` (network client only).

Install the engines before opening the app from Finder:

```bash
uv tool install "git+https://github.com/theosunny/memrelay#subdirectory=packages/core"
uv tool install "git+https://github.com/theosunny/memrelay#subdirectory=packages/sync"
```

`shortcut: the app does not download Python. Those two commands are the install.` A LAN phone cannot use the auto-started sync server. Quit the app, then run `memrelay-sync --host 0.0.0.0 --port 8790` and put that Mac's LAN URL in the phone. Do not publish port 8790 on the internet: there is no TLS, and pair codes are short.

## 在 macOS 上运行

1. 安装 Xcode 命令行工具、Rust、Node.js 20+。
2. 在仓库根目录执行 `uv tool install`（见上面的英文安装命令），让 `memrelay` 出现在 `~/.local/bin`。从访达打开时不看终端的 PATH。
3. 进入 `packages/desktop`，执行 `npm install`。开发用 `npm run tauri dev`。安装包用 `npm run tauri build`，未签名的 `.app` 和 `.dmg` 在 `src-tauri/target/release/bundle/`。
4. 第一次打开会启动本机服务。三个入口是 **分身**、**记忆**、**动态**。问「我偏好什么」时，回答带依据和分身说明。
5. 关掉窗口只会藏到菜单栏。要退出，用托盘里的「退出」。

如果 8787 端口上已经有别的程序，桌面不会再启动一份服务，设置里需要自己贴令牌。

## Dev without the tray

The Vite screen alone does not start the API:

```bash
# terminal A, from the repo root
uv run memrelay shell-api --port 8787
# token path is printed once; paste it into 设置

cd packages/desktop && npm install && npm run dev
```

Open `http://127.0.0.1:1420`. The content security policy inside the tray app allows only port **8787**. Changing the port in 设置 works in the browser preview, not inside the packaged window.

## Skipped

- No Apple notarization in CI. The committed config signs nothing until `APPLE_SIGNING_IDENTITY` is set.
- Python is not frozen into the `.app`. shortcut: a sidecar freeze is a new packaging pipeline, do that when `uv tool install` is not acceptable.
- Memory browse has search and a single note, not a timeline or type filter.
- JS client has no test runner yet.
- 设置 shows a QR of the pairing string and the same text underneath. The string is the vault key.
