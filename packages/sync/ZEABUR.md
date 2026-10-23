# 部署到 Zeabur

两个服务，都从本仓库创建。域名是占位，**CONFIGURE AFTER DEPLOY**：Zeabur 给出真实域名后，改下面「部署之后要改的地方」。

| 服务 | Dockerfile | 占位域名 |
|---|---|---|
| 官网 | 仓库根目录 `Dockerfile.website` | `https://memrelay.zeabur.app` |
| 同步 | 仓库根目录 `Dockerfile.sync` | `https://memrelay-sync.zeabur.app` |

TLS 由 Zeabur 终结。容器里是 HTTP。不要把同步容器的端口直接暴露到公网：镜像设置了 `MEMRELAY_TRUST_PROXY=1`，这时客户端可以伪造 `X-Forwarded-For`。只在 Zeabur 的反向代理后面开这个变量。

## 同步服务

1. Zeabur → New Service → GitHub → `theosunny/memrelay`，选要部署的分支。
2. Dockerfile 路径填 `Dockerfile.sync`（不要用仓库根的默认 `Dockerfile`，根目录没有那个文件）。
3. 卷：挂到 `/data`。镜像里 `MEMRELAY_SYNC_DATA=/data`，密文和配对锁定都写在这里。`limits.json` 在这个目录，重启不会清掉配对锁定。
4. Networking → 生成域名，打开 HTTPS。记下 `https://….zeabur.app`，不要带路径，不要带结尾斜杠。
5. 变量已经在镜像里：`PORT`（Zeabur 注入）、`MEMRELAY_SYNC_DATA=/data`、`MEMRELAY_TRUST_PROXY=1`。进程监听 `0.0.0.0:$PORT`。
6. 打开 `https://你的域名/health`，应返回 `{"ok": true}`。

本机调试不要设 `PORT`，`memrelay-sync` 仍只听 `127.0.0.1:8790`。

## 官网

1. 再新建一个服务，同一个仓库。
2. Dockerfile 路径填 `Dockerfile.website`。
3. 不需要卷。Zeabur 注入 `PORT`，nginx 听这个端口。
4. 生成域名并打开 HTTPS。首页是官网，`/m/` 是手机网页版。
5. 下载按钮默认指向 `https://github.com/theosunny/memrelay/releases/latest`，文案是「即将发布」。浏览器能读到 Release 里的 `.dmg` 或 `.app.zip` 时，按钮改成「下载 macOS」并指向那个文件。没有安装包时，页面上有从源码构建的命令。

打 macOS 包：GitHub Actions → `release-macos` → Run workflow。推送 `v*` tag 时，未签名的 `.dmg` 和 `.app.zip` 会挂到对应 Release。没有 Apple 证书也能跑。不要把 `APPLE_SIGNING_IDENTITY` 设成空字符串。

## GitHub 仓库首页

Cloud agent 的 `gh` 只能读，不能改 About。部署出真实官网域名后，二选一：

- 打开仓库 → 齿轮 Settings（仓库页右侧 About 旁的齿轮）→ Website → 填 `https://memrelay.zeabur.app`（或 Zeabur 实际给的域名）→ Save。
- 本机有写权限时：

```bash
gh api -X PATCH repos/theosunny/memrelay -f homepage='https://memrelay.zeabur.app'
```

把命令里的域名换成真实官网。这是 **CONFIGURE AFTER DEPLOY**。

## 部署之后要改的地方

Zeabur 的域名如果不是上面的占位，改这几处再发一版：

- `packages/website/urls.json`（桌面和手机读这一个文件）
- `packages/website/index.html`（`npm run build` 会检查它和 `urls.json` 一致）
- `README.md` 和 `README.zh-CN.md` 顶部的官网链接

已经装好的桌面或手机不用为了换域名重新编译：设置里的「同步服务」填 `https://…` 即可。空着则用 `http://127.0.0.1:8790`。改地址后在电脑上重新生成配对码。钥匙只留在设备上。
