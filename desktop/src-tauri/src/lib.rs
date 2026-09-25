use std::net::TcpListener;
use std::sync::Mutex;
use tauri::{Manager, State};
use tauri_plugin_shell::process::CommandChild;
use tauri_plugin_shell::ShellExt;

struct BackendState {
    port: u16,
    token: String,
    child: Mutex<Option<CommandChild>>,
}

#[derive(serde::Serialize)]
struct BackendInfo {
    port: u16,
    token: String,
}

#[tauri::command]
fn backend_info(state: State<'_, BackendState>) -> BackendInfo {
    BackendInfo { port: state.port, token: state.token.clone() }
}

#[cfg_attr(mobile, tauri::mobile_entry_point)]
pub fn run() {
    tauri::Builder::default()
        .plugin(tauri_plugin_shell::init())
        .plugin(tauri_plugin_opener::init())
        .invoke_handler(tauri::generate_handler![backend_info])
        .setup(|app| {
            let listener = TcpListener::bind("127.0.0.1:0")?;
            let port = listener.local_addr()?.port();
            drop(listener);
            let token = format!("{}{}", uuid::Uuid::new_v4(), uuid::Uuid::new_v4());
            let (_events, mut child) = app.shell().sidecar("filinglens-api")?
                .args(["--port", &port.to_string(), "--token-stdin"])
                .spawn()?;
            child.write(format!("{token}\n").as_bytes())?;
            app.manage(BackendState { port, token, child: Mutex::new(Some(child)) });
            Ok(())
        })
        .build(tauri::generate_context!())
        .expect("FilingLens failed to initialize")
        .run(|app, event| {
            if let tauri::RunEvent::Exit = event {
                if let Some(state) = app.try_state::<BackendState>() {
                    if let Ok(mut child) = state.child.lock() {
                        if let Some(process) = child.take() { let _ = process.kill(); }
                    }
                }
            }
        });
}
