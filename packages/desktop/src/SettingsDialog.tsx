import { useState, type FormEvent, type KeyboardEvent } from "react";
import { PROVIDERS, type Provider } from "./model";

export type ModelDraft = { provider: string; apiKey: string; model: string };

export function SettingsDialog({
  version,
  distribution,
  provider,
  model,
  syncServer,
  base,
  token,
  localSync,
  pairCode,
  pairing,
  qr,
  syncMsg,
  onClose,
  onSaveModel,
  onPair,
  onUseLocal,
  onSyncOnce,
  onOpenData,
  onBase,
  onToken,
  onLocalSync,
}: {
  version: string;
  distribution: string;
  provider: string;
  model: string;
  syncServer: string;
  base: string;
  token: string;
  localSync: string;
  pairCode: string;
  pairing: string;
  qr: string;
  syncMsg: string;
  onClose: () => void;
  onSaveModel: (input: ModelDraft) => void;
  onPair: () => void;
  onUseLocal: () => void;
  onSyncOnce: () => void;
  onOpenData: () => void;
  onBase: (value: string) => void;
  onToken: (value: string) => void;
  onLocalSync: (value: string) => void;
}) {
  const [chosen, setChosen] = useState(provider);
  const [apiKey, setApiKey] = useState("");
  const [modelName, setModelName] = useState(model);

  function trap(event: KeyboardEvent<HTMLFormElement>) {
    if (event.key === "Escape") {
      onClose();
      return;
    }
    if (event.key !== "Tab") return;
    const items = [...event.currentTarget.querySelectorAll<HTMLElement>("input, textarea, select, button")].filter(
      (el) => !el.hasAttribute("disabled"),
    );
    const first = items[0];
    const last = items[items.length - 1];
    if (event.shiftKey && document.activeElement === first) {
      event.preventDefault();
      last?.focus();
    } else if (!event.shiftKey && document.activeElement === last) {
      event.preventDefault();
      first?.focus();
    }
  }

  function saveModel(event: FormEvent) {
    event.preventDefault();
    onSaveModel({ provider: chosen, apiKey, model: modelName });
  }

  return (
    <div className="dialog" role="presentation">
      <form role="dialog" aria-modal="true" aria-labelledby="settings-title" onSubmit={saveModel} onKeyDown={trap}>
        <h2 id="settings-title">设置</h2>
        <label htmlFor="settings-provider">模型</label>
        <select
          id="settings-provider"
          value={PROVIDERS.includes(chosen as Provider) ? chosen : PROVIDERS[0]}
          onChange={(event) => setChosen(event.target.value)}
        >
          {PROVIDERS.map((name) => (
            <option key={name} value={name}>{name}</option>
          ))}
        </select>
        <label htmlFor="settings-api-key">API Key</label>
        <input
          id="settings-api-key"
          type="password"
          value={apiKey}
          autoComplete="off"
          onChange={(event) => setApiKey(event.target.value)}
        />
        <label htmlFor="settings-model">模型名称</label>
        <input
          id="settings-model"
          value={modelName}
          autoComplete="off"
          onChange={(event) => setModelName(event.target.value)}
        />
        <div className="actions">
          <button className="primary" type="submit">保存模型</button>
          <button className="gear" type="button" onClick={onPair}>生成配对码</button>
        </div>
        {syncServer.startsWith("http://127.0.0.1") ? null : <p className="meta">{syncServer}</p>}
        {pairCode ? <p>配对码 {pairCode}</p> : null}
        {qr ? <img className="qr" alt="配对二维码" src={qr} width={192} height={192} /> : null}
        {qr ? <p className="meta">用手机相机扫描。扫不到就粘贴下面的文字。</p> : null}
        {pairing ? <textarea readOnly value={pairing} aria-label="配对内容" /> : null}
        <p className="meta">{version} {distribution}</p>
        {syncMsg ? <p className="meta">{syncMsg}</p> : null}
        <details>
          <summary>高级</summary>
          <label htmlFor="base">服务地址</label>
          <input id="base" type="text" value={base} onChange={(event) => onBase(event.target.value)} autoComplete="off" />
          <label htmlFor="token">令牌</label>
          <input id="token" type="password" value={token} onChange={(event) => onToken(event.target.value)} autoComplete="off" />
          <label htmlFor="local-sync">本机同步</label>
          <input id="local-sync" type="text" value={localSync} onChange={(event) => onLocalSync(event.target.value)} autoComplete="off" />
          <div className="actions">
            <button className="gear" type="button" onClick={onUseLocal}>使用本机</button>
            <button className="gear" type="button" onClick={onSyncOnce}>同步一次</button>
            <button className="gear" type="button" onClick={onOpenData}>打开数据目录</button>
          </div>
        </details>
        <div className="actions">
          <button className="gear" type="button" onClick={onClose}>关闭</button>
        </div>
      </form>
    </div>
  );
}
