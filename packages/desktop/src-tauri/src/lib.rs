use std::path::PathBuf;
use std::time::Duration;

use tauri::menu::{Menu, MenuItem};
use tauri::tray::TrayIconBuilder;
use tauri::{Manager, WindowEvent};

const BASE: &str = "http://127.0.0.1:8787";

struct TrayReady(bool);

#[derive(serde::Serialize)]
struct ShellConfig {
    base: String,
    token: String,
    ready: bool,
    detail: String,
}

fn port_up(port: u16) -> bool {
    std::net::TcpStream::connect_timeout(
        &std::net::SocketAddr::from(([127, 0, 0, 1], port)),
        Duration::from_millis(400),
    )
    .is_ok()
}

fn api_up() -> bool {
    port_up(8787)
}

fn tool_candidates(
    name: &str,
    from_env: Option<&std::path::Path>,
    home: Option<&std::path::Path>,
    exe_dir: Option<&std::path::Path>,
) -> Vec<PathBuf> {
    let mut out = Vec::new();
    if let Some(path) = from_env {
        out.push(path.to_path_buf());
    }
    if let Some(dir) = exe_dir {
        out.push(dir.join(name));
        out.push(dir.join("../Resources").join(name));
    }
    if let Some(home) = home {
        out.push(home.join(".local/bin").join(name));
    }
    out.push(PathBuf::from("/opt/homebrew/bin").join(name));
    out.push(PathBuf::from("/usr/local/bin").join(name));
    out
}

fn find_tool(name: &str) -> Option<PathBuf> {
    let env_key = if name == "memrelay" { "MEMRELAY_BIN" } else { "MEMRELAY_SYNC_BIN" };
    let from_env = std::env::var_os(env_key).map(PathBuf::from);
    let home = std::env::var_os("HOME").map(PathBuf::from);
    let exe = std::env::current_exe().ok().and_then(|p| p.parent().map(|d| d.to_path_buf()));
    let mut paths = tool_candidates(name, from_env.as_deref(), home.as_deref(), exe.as_deref());
    if let Some(path) = std::env::var_os("PATH") {
        for dir in std::env::split_paths(&path) {
            paths.push(dir.join(name));
        }
    }
    // shortcut: no .exe suffix, add one when a Windows bundle is built
    paths.into_iter().find(|p| p.is_file())
}

fn spawn_detached(bin: &std::path::Path, args: &[&str]) -> Result<(), String> {
    std::process::Command::new(bin)
        .args(args)
        .stdin(std::process::Stdio::null())
        .stdout(std::process::Stdio::null())
        .stderr(std::process::Stdio::null())
        .spawn()
        .map(|_| ())
        .map_err(|_| "本机服务没有启动".to_string())
}

fn ensure_sync() {
    if port_up(8790) {
        return;
    }
    // shortcut: loopback only. LAN needs `memrelay-sync --host 0.0.0.0` after quitting, or this process keeps 8790.
    if let Some(bin) = find_tool("memrelay-sync") {
        let _ = spawn_detached(&bin, &["--host", "127.0.0.1", "--port", "8790"]);
    }
}

fn ensure_shell(token_file: &std::path::Path) -> Result<String, String> {
    if let Some(parent) = token_file.parent() {
        std::fs::create_dir_all(parent).map_err(|e| e.to_string())?;
    }
    if !api_up() {
        let Some(bin) = find_tool("memrelay") else {
            return Err("还没找到本机程序。安装后它在 ~/.local/bin/memrelay，从访达打开时也会到那里找。".into());
        };
        spawn_detached(&bin, &["shell-api", "--port", "8787", "--token-file", &token_file.to_string_lossy()])?;
        for _ in 0..40 {
            if api_up() {
                break;
            }
            std::thread::sleep(Duration::from_millis(250));
        }
    }
    if !api_up() {
        return Err("本机服务没有启动".into());
    }
    // shortcut: a process already bound to 8787 is reused, even if it is not ours; pick a free port if that collides
    Ok(std::fs::read_to_string(token_file)
        .unwrap_or_default()
        .trim()
        .to_string())
}

#[tauri::command]
fn shell_config(app: tauri::AppHandle) -> ShellConfig {
    ensure_sync();
    let token_file: PathBuf = match app.path().app_data_dir() {
        Ok(dir) => dir.join("shell-api.token"),
        Err(_) => {
            return ShellConfig {
                base: BASE.into(),
                token: String::new(),
                ready: false,
                detail: "本机服务没有启动".into(),
            };
        }
    };
    match ensure_shell(&token_file) {
        Ok(token) => ShellConfig {
            base: BASE.into(),
            token: token.clone(),
            ready: api_up() && !token.is_empty(),
            detail: if token.is_empty() {
                "需要填写令牌".into()
            } else {
                String::new()
            },
        },
        Err(detail) => ShellConfig {
            base: BASE.into(),
            token: String::new(),
            ready: false,
            detail,
        },
    }
}

fn show_main(app: &tauri::AppHandle) {
    if let Some(window) = app.get_webview_window("main") {
        let _ = window.show();
        let _ = window.unminimize();
        let _ = window.set_focus();
    }
}

fn install_tray(app: &tauri::AppHandle) -> Result<(), String> {
    let show = MenuItem::with_id(app, "show", "显示", true, None::<&str>).map_err(|e| e.to_string())?;
    let quit = MenuItem::with_id(app, "quit", "退出", true, None::<&str>).map_err(|e| e.to_string())?;
    let menu = Menu::with_items(app, &[&show, &quit]).map_err(|e| e.to_string())?;
    let mut builder = TrayIconBuilder::new()
        .menu(&menu)
        .tooltip("忆桥分身")
        .on_menu_event(|app, event| match event.id.as_ref() {
            "show" => show_main(app),
            "quit" => app.exit(0),
            _ => {}
        })
        .on_tray_icon_event(|tray, event| {
            if let tauri::tray::TrayIconEvent::Click {
                button: tauri::tray::MouseButton::Left,
                button_state: tauri::tray::MouseButtonState::Up,
                ..
            } = event
            {
                show_main(tray.app_handle());
            }
        });
    if let Some(icon) = app.default_window_icon() {
        builder = builder.icon(icon.clone());
    }
    builder.build(app).map_err(|e| e.to_string())?;
    Ok(())
}

#[cfg_attr(mobile, tauri::mobile_entry_point)]
pub fn run() {
    tauri::Builder::default()
        .invoke_handler(tauri::generate_handler![shell_config])
        .setup(|app| {
            let ready = install_tray(app.handle()).is_ok();
            app.manage(TrayReady(ready));
            Ok(())
        })
        .on_window_event(|window, event| {
            if let WindowEvent::CloseRequested { api, .. } = event {
                let hide = window.try_state::<TrayReady>().is_some_and(|s| s.0);
                if hide {
                    api.prevent_close();
                    let _ = window.hide();
                }
            }
        })
        .run(tauri::generate_context!())
        .expect("error while running 忆桥分身");
}

#[cfg(test)]
mod tests {
    use super::tool_candidates;
    use std::path::Path;

    #[test]
    fn candidates_check_env_then_app_then_user_bin() {
        let got = tool_candidates(
            "memrelay",
            Some(Path::new("/opt/custom/memrelay")),
            Some(Path::new("/Users/me")),
            Some(Path::new("/App.app/Contents/MacOS")),
        );
        assert_eq!(got[0], Path::new("/opt/custom/memrelay"));
        assert_eq!(got[1], Path::new("/App.app/Contents/MacOS/memrelay"));
        assert!(got.iter().any(|p| p == Path::new("/Users/me/.local/bin/memrelay")));
        assert!(got.iter().any(|p| p == Path::new("/opt/homebrew/bin/memrelay")));
        assert!(got.iter().any(|p| p == Path::new("/usr/local/bin/memrelay")));
    }
}
