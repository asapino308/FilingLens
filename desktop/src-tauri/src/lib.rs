use std::net::TcpListener;
use std::sync::Mutex;
use std::io::Write;
use std::path::Path;
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

fn write_investigation_export(directory: &Path, filename: &str, content: &str) -> Result<String, String> {
    if filename.len() > 160 || !filename.ends_with(".md") || filename.contains("..")
        || !filename.bytes().all(|c| c.is_ascii_alphanumeric() || b"-_.".contains(&c)) {
        return Err("Invalid investigation filename.".into());
    }
    if content.len() > 2_000_000 {
        return Err("This investigation is too large to export in one file.".into());
    }
    std::fs::create_dir_all(directory).map_err(|_| "Could not create the investigation export folder.")?;
    let name = format!("{}-{}.md", filename.trim_end_matches(".md"), uuid::Uuid::new_v4());
    let path = directory.join(name);
    let mut file = std::fs::OpenOptions::new().write(true).create_new(true).open(&path)
        .map_err(|_| "Could not create the investigation file.")?;
    file.write_all(content.as_bytes()).map_err(|_| "Could not finish saving the investigation.")?;
    Ok(path.to_string_lossy().into_owned())
}

#[tauri::command]
async fn export_investigation(app: tauri::AppHandle, filename: String, content: String) -> Result<String, String> {
    let directory = app.path().app_data_dir().map_err(|_| "Could not locate local app storage.")?.join("exports");
    write_investigation_export(&directory, &filename, &content)
}

#[tauri::command]
async fn show_investigation_exports(app: tauri::AppHandle) -> Result<(), String> {
    let directory = app.path().app_data_dir().map_err(|_| "Could not locate local app storage.")?.join("exports");
    #[cfg(target_os = "macos")]
    {
        std::process::Command::new("open").arg(directory).spawn().map_err(|_| "Could not show exports in Finder.")?;
        Ok(())
    }
    #[cfg(not(target_os = "macos"))]
    {
        let _ = directory;
        Err("Open the displayed export folder in your file manager.".into())
    }
}

#[cfg_attr(mobile, tauri::mobile_entry_point)]
pub fn run() {
    tauri::Builder::default()
        .plugin(tauri_plugin_shell::init())
        .plugin(tauri_plugin_opener::init())
        .invoke_handler(tauri::generate_handler![backend_info, export_investigation, show_investigation_exports])
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

#[cfg(test)]
mod tests {
    use super::write_investigation_export;

    #[test]
    fn exports_preserve_text_and_never_overwrite_an_existing_file() {
        let directory = std::env::temp_dir().join(format!("filinglens-export-{}", uuid::Uuid::new_v4()));
        let first = write_investigation_export(&directory, "AAPL-cash-2025.md", "# Evidence\nExact source text").unwrap();
        let second = write_investigation_export(&directory, "AAPL-cash-2025.md", "Second review").unwrap();
        assert_ne!(first, second);
        assert_eq!(std::fs::read_to_string(first).unwrap(), "# Evidence\nExact source text");
        assert_eq!(std::fs::read_to_string(second).unwrap(), "Second review");
        std::fs::remove_dir_all(directory).unwrap();
    }

    #[test]
    fn exports_reject_path_traversal_and_oversized_content() {
        let directory = std::env::temp_dir().join(format!("filinglens-export-{}", uuid::Uuid::new_v4()));
        for name in ["../outside.md", "/tmp/outside.md", "file.html", "file name.md"] {
            assert!(write_investigation_export(&directory, name, "text").is_err());
        }
        assert!(write_investigation_export(&directory, "valid.md", &"x".repeat(2_000_001)).is_err());
        assert!(!directory.exists());
    }
}
