import { render, screen } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";

vi.mock("@tauri-apps/api/core", () => ({
  invoke: vi.fn(async (cmd: string) => {
    if (cmd === "model_status") return { configured: true, provider: "ollama", model: "" };
    if (cmd === "shell_config") {
      return { base: "http://127.0.0.1:8787", token: "t", ready: false, detail: "分身暂时没连上" };
    }
    throw new Error(cmd);
  }),
}));

import App from "./App";

describe("App", () => {
  beforeEach(() => {
    localStorage.clear();
    vi.stubGlobal("fetch", vi.fn(async () => {
      throw new Error("down");
    }));
  });

  it("keeps settings closed when the shell is down", async () => {
    render(<App />);
    expect(await screen.findByRole("navigation", { name: "主导航" })).toBeTruthy();
    expect(screen.queryByRole("dialog")).toBeNull();
  });
});
