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

fn api_up() -> bool {
    std::net::TcpStream::connect_timeout(
        &std::net::SocketAddr::from(([127, 0, 0, 1], 8787)),
        Duration::from_millis(400),
    )
    .is_ok()
}

fn ensure_shell(token_file: &std::path::Path) -> Result<String, String> {
    if let Some(parent) = token_file.parent() {
        std::fs::create_dir_all(parent).map_err(|e| e.to_string())?;
    }
    if !api_up() {
        // shortcut: PATH must contain memrelay; bundle a sidecar when installers ship
        std::process::Command::new("memrelay")
            .args(["shell-api", "--port", "8787", "--token-file"])
            .arg(token_file)
            .stdin(std::process::Stdio::null())
            .stdout(std::process::Stdio::null())
            .stderr(std::process::Stdio::null())
            .spawn()
            .map_err(|_| "本机服务没有启动".to_string())?;
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
