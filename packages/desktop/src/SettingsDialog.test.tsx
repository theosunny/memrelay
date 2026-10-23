import { render, screen } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";
import { SettingsDialog } from "./SettingsDialog";

describe("SettingsDialog", () => {
  it("keeps engineer fields inside a closed Advanced group", () => {
    render(
      <SettingsDialog
        version="0.2.0"
        distribution="开发构建"
        provider="deepseek"
        model=""
        syncServer="https://memrelay-sync.preview.tencent-zeabur.cn"
        base="http://127.0.0.1:8787"
        token=""
        localSync="http://127.0.0.1:8790"
        pairCode=""
        pairing=""
        qr=""
        syncMsg=""
        onClose={vi.fn()}
        onSaveModel={vi.fn()}
        onPair={vi.fn()}
        onUseLocal={vi.fn()}
        onSyncOnce={vi.fn()}
        onOpenData={vi.fn()}
        onBase={vi.fn()}
        onToken={vi.fn()}
        onLocalSync={vi.fn()}
      />,
    );
    expect(screen.getByRole("button", { name: "生成配对码" })).toBeTruthy();
    const advanced = screen.getByText("高级").closest("details");
    expect(advanced?.open).toBe(false);
    expect(advanced?.textContent).toContain("服务地址");
    expect(advanced?.textContent).toContain("使用本机");
    expect(advanced?.textContent).toContain("同步一次");
    expect(advanced?.textContent).toContain("打开数据目录");
  });
});
