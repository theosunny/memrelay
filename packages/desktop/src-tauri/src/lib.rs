mod model;
use model::KeyStore;

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

fn find_tool(name: &str) -> Option<PathBuf> {
    let mode = launch_mode();
    let env_key = if name == "memrelay" { "MEMRELAY_BIN" } else { "MEMRELAY_SYNC_BIN" };
    let from_env = if mode == LaunchMode::Dev {
        std::env::var_os(env_key).map(PathBuf::from)
    } else {
        None
    };
    let home = if mode == LaunchMode::Dev {
        std::env::var_os("HOME").map(PathBuf::from)
    } else {
        None
    };
    let exe = std::env::current_exe().ok().and_then(|p| p.parent().map(|d| d.to_path_buf()));
    let mut paths = tool_candidates(name, mode, from_env.as_deref(), home.as_deref(), exe.as_deref());
    if mode == LaunchMode::Dev {
        if let Some(path) = std::env::var_os("PATH") {
            for dir in std::env::split_paths(&path) {
                paths.push(dir.join(name));
            }
        }
    }
    // shortcut: no .exe suffix, add one when a Windows bundle is built
    paths.into_iter().find(|p| p.is_file())
}

pub struct StartupPlan {
    pub shell: bool,
    pub sync: bool,
}

pub fn startup_plan(local_sync_requested: bool) -> StartupPlan {
    StartupPlan { shell: true, sync: local_sync_requested }
}

fn spawn_detached(bin: &std::path::Path, args: &[&str], env: &[(&str, &str)]) -> Result<(), String> {
    let mut cmd = std::process::Command::new(bin);
    cmd.args(args)
        .stdin(std::process::Stdio::null())
        .stdout(std::process::Stdio::null())
        .stderr(std::process::Stdio::null());
    for (key, value) in env {
        cmd.env(key, value);
    }
    cmd.spawn().map(|_| ()).map_err(|_| "分身暂时没连上".to_string())
}

fn saved_model(app_data: &std::path::Path) -> Option<serde_json::Value> {
    let text = std::fs::read_to_string(app_data.join("model.json")).ok()?;
    serde_json::from_str(&text).ok()
}

fn child_env(app_data: &std::path::Path) -> Vec<(String, String)> {
    let mut env = vec![("MEMRELAY_HOME".into(), app_data.to_string_lossy().to_string())];
    let Some(parsed) = saved_model(app_data) else {
        return env;
    };
    let name = parsed.get("api_key_env").and_then(|v| v.as_str()).unwrap_or("");
    if name.is_empty() {
        return env;
    }
    if let Some(secret) = model::KeyringStore.get() {
        if !secret.trim().is_empty() {
            env.push((name.to_string(), secret));
        }
    }
    env
}

fn init_vault(app_data: &std::path::Path, bin: &std::path::Path) -> Result<(), String> {
    let Some(parsed) = saved_model(app_data) else {
        return Ok(());
    };
    let provider = parsed.get("provider").and_then(|v| v.as_str()).unwrap_or("");
    if provider.is_empty() {
        return Err("分身暂时没连上".into());
    }
    let model_name = parsed.get("model").and_then(|v| v.as_str()).unwrap_or("");
    let home = app_data.to_string_lossy().to_string();
    let output = std::process::Command::new(bin)
        .args(["configure-model", "--home", &home, "--provider", provider, "--model", model_name])
        .env("MEMRELAY_HOME", &home)
        .output()
        .map_err(|_| "分身暂时没连上".to_string())?;
    if output.status.success() {
        Ok(())
    } else {
        Err("分身暂时没连上".into())
    }
}

fn tighten_token(path: &std::path::Path) {
    #[cfg(unix)]
    {
        use std::os::unix::fs::PermissionsExt;
        if path.is_file() {
            let _ = std::fs::set_permissions(path, std::fs::Permissions::from_mode(0o600));
        }
    }
}

fn ensure_shell(app_data: &std::path::Path, token_file: &std::path::Path) -> Result<String, String> {
    if let Some(parent) = token_file.parent() {
        std::fs::create_dir_all(parent).map_err(|_| "分身暂时没连上".to_string())?;
    }
    let Some(bin) = find_tool("memrelay") else {
        return Err("分身暂时没连上".into());
    };
    if app_data.join("model.json").is_file() && !app_data.join("vault").is_dir() {
        init_vault(app_data, &bin)?;
    }
    if !api_up() {
        let env = child_env(app_data);
        let pairs: Vec<(&str, &str)> = env.iter().map(|(key, value)| (key.as_str(), value.as_str())).collect();
        let token_arg = token_file.to_string_lossy().to_string();
        spawn_detached(
            &bin,
            &["shell-api", "--port", "8787", "--token-file", &token_arg],
            &pairs,
        )?;
        for _ in 0..40 {
            if api_up() {
                break;
            }
            std::thread::sleep(Duration::from_millis(250));
        }
    }
    if !api_up() {
        return Err("分身暂时没连上".into());
    }
    // shortcut: a process already bound to 8787 is reused, even if it is not ours; pick a free port if that collides
    tighten_token(token_file);
    Ok(std::fs::read_to_string(token_file).unwrap_or_default().trim().to_string())
}

fn shell_down() -> ShellConfig {
    ShellConfig {
        base: BASE.into(),
        token: String::new(),
        ready: false,
        detail: "分身暂时没连上".into(),
    }
}

#[tauri::command]
fn model_status(app: tauri::AppHandle) -> model::ModelStatus {
    match app.path().app_data_dir() {
        Ok(dir) => model::read_status(&dir, &model::KeyringStore),
        Err(_) => model::ModelStatus {
            configured: false,
            provider: String::new(),
            model: String::new(),
        },
    }
}

#[tauri::command]
fn save_model(app: tauri::AppHandle, provider: String, api_key: String, model: String) -> Result<(), String> {
    let dir = app.path().app_data_dir().map_err(|e| e.to_string())?;
    let Some(bin) = find_tool("memrelay") else {
        return Err("没有找到分身程序".into());
    };
    model::persist_model(&dir, &model::KeyringStore, &bin, &provider, &api_key, &model)
}

#[tauri::command]
fn shell_config(app: tauri::AppHandle) -> ShellConfig {
    let plan = startup_plan(false);
    if !plan.shell {
        return shell_down();
    }
    if plan.sync {
        // Local sync starts only after the user chooses 使用本机.
    }
    let app_data = match app.path().app_data_dir() {
        Ok(dir) => dir,
        Err(_) => return shell_down(),
    };
    if !model::read_status(&app_data, &model::KeyringStore).configured {
        return shell_down();
    }
    let token_file: PathBuf = app_data.join("shell-api.token");
    match ensure_shell(&app_data, &token_file) {
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

#[tauri::command]
fn use_local_sync(_app: tauri::AppHandle) -> Result<(), String> {
    if port_up(8790) {
        return Ok(());
    }
    let Some(bin) = find_tool("memrelay-sync") else {
        return Err("分身暂时没连上".into());
    };
    spawn_detached(&bin, &["--host", "127.0.0.1", "--port", "8790"], &[])
}

#[tauri::command]
fn open_data_dir(app: tauri::AppHandle) -> Result<(), String> {
    let dir = app.path().app_data_dir().map_err(|_| "没有打开数据目录".to_string())?;
    let vault = dir.join("vault");
    std::fs::create_dir_all(&vault).map_err(|_| "没有打开数据目录".to_string())?;
    std::process::Command::new("/usr/bin/open")
        .arg(&vault)
        .spawn()
        .map(|_| ())
        .map_err(|_| "没有打开数据目录".to_string())
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
        .invoke_handler(tauri::generate_handler![
            shell_config,
            model_status,
            save_model,
            read_transcript,
            write_transcript,
            use_local_sync,
            open_data_dir
        ])
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
    use super::{startup_plan, tool_candidates, LaunchMode};
    use std::path::{Path, PathBuf};

    #[test]
    fn consumer_startup_does_not_launch_sync() {
        let plan = startup_plan(false);
        assert!(plan.shell);
        assert!(!plan.sync);
    }

    #[test]
    fn dev_candidates_include_user_installs() {
        let got = tool_candidates(
            "memrelay",
            LaunchMode::Dev,
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
}
