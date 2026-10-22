# 忆桥分身桌面壳 / MemRelay desktop shell

**Status:** Tray app with three home screens: 分身 / 记忆 / 动态.
The window talks only to the local shell API. 设置 also pairs a phone and runs one sync against `memrelay-sync` (default `http://127.0.0.1:8790`). The phone app is `packages/mobile`.

## What you need

- An initialized MemRelay vault (`memrelay init`, default `~/MemRelay`)
- `memrelay` on `PATH` (from this repo: `uv sync` at the root, then use `.venv/bin/memrelay`, or install the `packages/core` package)
- Node.js 20+
- Rust 1.90+ (current stable; Tauri 2.12 does not build on older compilers) and the platform webview: macOS uses the system WebKit; Linux needs `webkit2gtk-4.1` development packages

The app looks for `memrelay` on `PATH` and, if nothing is listening on `127.0.0.1:8787`, runs:

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

A release bundle (unsigned):

```bash
npm run tauri build
```

The app bundle lands under `src-tauri/target/release/bundle/`. macOS will warn until the app is signed and notarized. That signing step is not part of Phase 1.

## 在 macOS 上运行

1. 安装 Xcode 命令行工具、Rust、Node.js 20+。
2. 在仓库根目录执行 `uv sync`，并把 `.venv/bin` 加进 `PATH`，这样桌面程序才能找到 `memrelay`。
3. 进入 `packages/desktop`，执行 `npm install`，再执行 `npm run tauri dev`。
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

- No installer, code signing, or auto-update.
- `memrelay` is not bundled; it must be on `PATH`.
- Memory browse has search and a single note, not a timeline or type filter.
- JS client has no test runner yet.
- Sync settings need a running `memrelay-sync`. The pairing text includes the vault key; it is shown only in 设置. The phone pastes it. There is no QR image.
