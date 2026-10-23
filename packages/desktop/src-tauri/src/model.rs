use std::path::Path;

pub const KEYCHAIN_SERVICE: &str = "io.memrelay.shell";
pub const KEYCHAIN_ACCOUNT: &str = "model-api-key";

const CLOUD: [&str; 5] = ["openai", "deepseek", "qwen", "kimi", "glm"];

pub trait KeyStore {
    fn get(&self) -> Option<String>;
    fn set(&self, secret: &str) -> Result<(), String>;
}

#[allow(dead_code)]
pub struct MemoryKeyStore {
    inner: std::sync::Mutex<Option<String>>,
}

impl MemoryKeyStore {
    #[allow(dead_code)]
    pub fn new() -> Self {
        Self { inner: std::sync::Mutex::new(None) }
    }
}

impl KeyStore for MemoryKeyStore {
    fn get(&self) -> Option<String> {
        self.inner.lock().ok().and_then(|v| v.clone())
    }

    fn set(&self, secret: &str) -> Result<(), String> {
        *self.inner.lock().map_err(|e| e.to_string())? = Some(secret.to_string());
        Ok(())
    }
}

pub struct KeyringStore;

impl KeyStore for KeyringStore {
    fn get(&self) -> Option<String> {
        let entry = keyring::Entry::new(KEYCHAIN_SERVICE, KEYCHAIN_ACCOUNT).ok()?;
        match entry.get_password() {
            Ok(secret) if !secret.trim().is_empty() => Some(secret),
            _ => None,
        }
    }

    fn set(&self, secret: &str) -> Result<(), String> {
        let entry = keyring::Entry::new(KEYCHAIN_SERVICE, KEYCHAIN_ACCOUNT).map_err(|e| e.to_string())?;
        entry.set_password(secret).map_err(|e| e.to_string())
    }
}

#[derive(serde::Serialize, Clone)]
pub struct ModelStatus {
    pub configured: bool,
    pub provider: String,
    pub model: String,
}

impl ModelStatus {
    fn empty() -> Self {
        Self { configured: false, provider: String::new(), model: String::new() }
    }
}

pub fn validate_save(provider: &str, api_key: &str) -> Result<(), String> {
    if provider == "ollama" {
        return Ok(());
    }
    if CLOUD.contains(&provider) && !api_key.trim().is_empty() {
        return Ok(());
    }
    if CLOUD.contains(&provider) {
        return Err("需要 API Key".into());
    }
    Err("provider must be one of: openai, deepseek, qwen, kimi, glm, ollama".into())
}

pub fn read_status(app_data: &Path, store: &impl KeyStore) -> ModelStatus {
    let Ok(text) = std::fs::read_to_string(app_data.join("model.json")) else {
        return ModelStatus::empty();
    };
    let Ok(parsed) = serde_json::from_str::<serde_json::Value>(&text) else {
        return ModelStatus::empty();
    };
    let provider = parsed.get("provider").and_then(|v| v.as_str()).unwrap_or("").to_string();
    let model = parsed.get("model").and_then(|v| v.as_str()).unwrap_or("").to_string();
    let secret = store.get();
    ModelStatus {
        configured: is_configured(&provider, secret.as_deref()),
        provider,
        model,
    }
}

pub fn persist_model(
    app_data: &Path,
    store: &impl KeyStore,
    bin: &Path,
    provider: &str,
    api_key: &str,
    model_name: &str,
) -> Result<(), String> {
    validate_save(provider, api_key)?;
    let secret = api_key.trim();
    if !secret.is_empty() {
        store.set(secret)?;
    }
    let home = app_data.to_string_lossy().to_string();
    let output = std::process::Command::new(bin)
        .args(["configure-model", "--home", &home, "--provider", provider, "--model", model_name])
        .env("MEMRELAY_HOME", &home)
        .output()
        .map_err(|e| e.to_string())?;
    let stdout = String::from_utf8_lossy(&output.stdout).to_string();
    let stderr = String::from_utf8_lossy(&output.stderr).to_string();
    if !output.status.success() {
        return Err(scrub(&format!("{stderr}{stdout}"), secret));
    }
    let line = stdout
        .lines()
        .rev()
        .find(|line| line.trim_start().starts_with('{'))
        .unwrap_or("")
        .trim()
        .to_string();
    if !secret.is_empty() && line.contains(secret) {
        return Err("没有保存".into());
    }
    let parsed: serde_json::Value = serde_json::from_str(&line).map_err(|e| e.to_string())?;
    let body = serde_json::to_string_pretty(&serde_json::json!({
        "provider": parsed.get("provider").and_then(|v| v.as_str()).unwrap_or(provider),
        "model": parsed.get("model").and_then(|v| v.as_str()).unwrap_or(""),
        "api_key_env": parsed.get("api_key_env").and_then(|v| v.as_str()).unwrap_or(""),
    }))
    .map_err(|e| e.to_string())?;
    if !secret.is_empty() && body.contains(secret) {
        return Err("没有保存".into());
    }
    std::fs::create_dir_all(app_data).map_err(|e| e.to_string())?;
    std::fs::write(app_data.join("model.json"), body).map_err(|e| e.to_string())?;
    Ok(())
}

fn is_configured(provider: &str, secret: Option<&str>) -> bool {
    if provider == "ollama" {
        return true;
    }
    CLOUD.contains(&provider) && secret.is_some_and(|value| !value.trim().is_empty())
}

fn scrub(raw: &str, secret: &str) -> String {
    if !secret.is_empty() && raw.contains(secret) {
        return "没有保存".into();
    }
    let line = raw.trim();
    if line.is_empty() { "没有保存".into() } else { line.to_string() }
}

#[cfg(test)]
mod tests {
    use super::{MemoryKeyStore, KeyStore, validate_save};

    #[test]
    fn validate_save_rejects_empty_cloud_key() {
        assert!(validate_save("deepseek", "").is_err());
        assert!(validate_save("deepseek", "   ").is_err());
    }

    #[test]
    fn validate_save_accepts_ollama_without_key() {
        assert!(validate_save("ollama", "").is_ok());
    }

    #[test]
    fn memory_key_round_trips_the_secret() {
        let store = MemoryKeyStore::new();
        assert!(store.get().is_none());
        store.set("sk-test").unwrap();
        assert_eq!(store.get().as_deref(), Some("sk-test"));
    }
}
