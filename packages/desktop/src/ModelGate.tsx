import { useState, type FormEvent } from "react";
import { PROVIDERS, canContinue, type Provider } from "./model";

export type ModelSave = { provider: Provider; apiKey: string; model: string };

export function ModelGate({ onSave }: { onSave: (input: ModelSave) => void }) {
  const [provider, setProvider] = useState<Provider>("deepseek");
  const [apiKey, setApiKey] = useState("");
  const [model, setModel] = useState("");

  function submit(event: FormEvent) {
    event.preventDefault();
    if (!canContinue(provider, apiKey)) return;
    onSave({ provider, apiKey, model });
  }

  return (
    <form onSubmit={submit}>
      <h1>先选一个模型</h1>
      <label htmlFor="provider">模型</label>
      <select
        id="provider"
        value={provider}
        onChange={(event) => setProvider(event.target.value as Provider)}
      >
        {PROVIDERS.map((name) => (
          <option key={name} value={name}>{name}</option>
        ))}
      </select>
      <label htmlFor="api-key">API Key</label>
      <input
        id="api-key"
        type="password"
        value={apiKey}
        autoComplete="off"
        onChange={(event) => setApiKey(event.target.value)}
      />
      <label htmlFor="model-name">模型名称</label>
      <input
        id="model-name"
        value={model}
        autoComplete="off"
        onChange={(event) => setModel(event.target.value)}
      />
      <button className="primary" type="submit" disabled={!canContinue(provider, apiKey)}>继续</button>
    </form>
  );
}
