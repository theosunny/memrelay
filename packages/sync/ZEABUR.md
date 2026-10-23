# 部署到 Zeabur

当前线上地址：

| 服务 | Dockerfile | 地址 |
|---|---|---|
| 官网 | 仓库根目录 `Dockerfile.website` | `https://memrelay-web.preview.tencent-zeabur.cn` |
| 同步 | 仓库根目录 `Dockerfile.sync` | `https://memrelay-sync.preview.tencent-zeabur.cn` |

这次部署没有走 Zeabur GitHub App：那个 App 里只列出了另一个仓库。用的是仓库的公开 Git 地址，加上 Dockerfile 内容覆盖。同步的 `GET /health` 返回 `{"ok":true}`。

Zeabur 共享集群 2026-12-01 起暂停，2026-12-31 停止。在那之前要迁到别的主机，就改 `packages/website/urls.json` 里的 `website` 和 `sync`，并让 `packages/website/index.html` 里的地址跟它一致。

TLS 由 Zeabur 终结。容器里是 HTTP。不要把同步容器的端口直接暴露到公网：镜像设置了 `MEMRELAY_TRUST_PROXY=1`，这时客户端可以伪造 `X-Forwarded-For`。只在 Zeabur 的反向代理后面开这个变量。

## 同步服务

1. Zeabur → New Service → GitHub → `theosunny/memrelay`，选要部署的分支。
2. Dockerfile 路径填 `Dockerfile.sync`（不要用仓库根的默认 `Dockerfile`，根目录没有那个文件）。
3. 卷：挂到 `/data`。镜像里 `MEMRELAY_SYNC_DATA=/data`，密文和配对锁定都写在这里。`limits.json` 在这个目录，重启不会清掉配对锁定。
4. Networking → 生成域名，打开 HTTPS。记下 `https://` 开头的主机名，不要带路径，不要带结尾斜杠。这次的同步主机是 `memrelay-sync.preview.tencent-zeabur.cn`。
5. 变量已经在镜像里：`PORT`（Zeabur 注入）、`MEMRELAY_SYNC_DATA=/data`、`MEMRELAY_TRUST_PROXY=1`。进程监听 `0.0.0.0:$PORT`。
6. 打开 `https://你的域名/health`，应返回 `{"ok": true}`。

本机调试不要设 `PORT`，`memrelay-sync` 仍只听 `127.0.0.1:8790`。

## 官网

1. 再新建一个服务，同一个仓库。
2. Dockerfile 路径填 `Dockerfile.website`。
3. 不需要卷。Zeabur 注入 `PORT`，nginx 听这个端口。
4. 生成域名并打开 HTTPS。首页是官网，`/m/` 是手机网页版。
5. 下载按钮默认指向 `https://github.com/theosunny/memrelay/releases/latest`，文案是「即将发布」。浏览器能读到 Release 里的 `.dmg` 或 `.app.zip` 时，按钮改成「下载 macOS」并指向那个文件。没有安装包时，源码构建命令收在「从源码构建」里。
6. 改了 `packages/website` 之后，用同一个公开 Git 地址和 `Dockerfile.website` 重新构建这个官网服务。不用新建服务，域名保持 `https://memrelay-web.preview.tencent-zeabur.cn`。`/m/` 仍是手机网页版。导航（产品介绍、产品能力、定价、联系我们）要等这次重新构建之后才会出现在线上。

打 macOS 包：GitHub Actions → `release-macos` → Run workflow。推送 `v*` tag 时，未签名的 `.dmg` 和 `.app.zip` 会挂到对应 Release。没有 Apple 证书也能跑。不要把 `APPLE_SIGNING_IDENTITY` 设成空字符串。

## GitHub 仓库首页

仓库 About → Website 应为 `https://memrelay-web.preview.tencent-zeabur.cn`。本环境的 `gh` 令牌没有 `administration=write`，`PATCH` 返回 403。有仓库管理权限时：

- 打开仓库 → 齿轮 Settings（仓库页右侧 About 旁的齿轮）→ Website → 填 `https://memrelay-web.preview.tencent-zeabur.cn` → Save。
- 本机有写权限时：

```bash
gh api -X PATCH repos/theosunny/memrelay -f homepage='https://memrelay-web.preview.tencent-zeabur.cn'
```

## 换域名时要改的地方

- `packages/website/urls.json`（桌面和手机读这一个文件）
- `packages/website/index.html`（`npm run build` 会检查它和 `urls.json` 一致）
- `README.md` 和 `README.zh-CN.md` 顶部的官网链接
- 仓库 About → Website

已经装好的桌面或手机不用为了换域名重新编译：设置里的「同步服务」填 `https://…` 即可。空着则用 `http://127.0.0.1:8790`。改地址后在电脑上重新生成配对码。钥匙只留在设备上。
