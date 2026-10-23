# 忆桥分身（手机） / MemRelay mobile

分身 + 记忆。手机不采集、没有动态。提问走加密信箱，由在线的桌面回答；电脑不在线时只能看已经同步下来的记忆。

## 配对

1. 在电脑上启动同步服务（默认只监听本机）：

```bash
uv run memrelay-sync
# 同一局域网的手机：uv run memrelay-sync --host 0.0.0.0 --port 8790
```

2. 桌面设置里点「生成配对码」，或：

```bash
uv run memrelay sync pair --server http://127.0.0.1:8790
```

3. 用手机相机扫描电脑上的配对二维码，或把整行 `mr1.…` 粘贴到「配对内容」。同步服务地址要填手机能够访问的地址（真机不是 `127.0.0.1`）。密钥只在这行字里，不会发给服务器。

局域网：在电脑上执行 `memrelay-sync --host 0.0.0.0 --port 8790`（先退出已经占用 8790 的桌面自动启动）。不要把 8790 暴露到公网：没有 TLS，配对码只有 8 位。

## 运行

```bash
cd packages/mobile
npm install
npm run dev
```

打开 `http://127.0.0.1:1421`。生产包：`npm run build`，静态文件在 `dist/`。这是一个 PWA（`manifest.webmanifest` + `sw.js`）。

Capacitor 工程已经在 `ios/` 和 `android/`（`io.memrelay.mobile`）。PWA 仍然用 `npm run dev`。用 Xcode 或 Android Studio 打开前先同步网页：

```bash
npm install
npm run cap:sync
npx cap open ios      # 需要 macOS、Xcode、CocoaPods（第一次 pod install）
npx cap open android  # 需要 Android SDK
```

`shortcut: no push notifications and no store signing, add them when a device build is actually shipped.`

## English

The phone browses decrypted vault files and asks through the ciphertext relay. The sync server stores ciphertext only. Paste the desktop pairing string (`mr1.<vault_id>.<code>.<fernet-key>`). The default server bind is loopback; pass `--host 0.0.0.0` and the LAN URL for a real phone. Offline, the app keeps the last pull in `localStorage` and shows 电脑不在线，先看看记忆.

Screens are not shared with the desktop package. `shortcut: extract packages/shell-ui when a third client needs the same screens.`
