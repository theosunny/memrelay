import { describe, expect, it } from "vitest";
import { canContinue, PROVIDERS } from "./model";

describe("canContinue", () => {
  it("lists only the engine presets", () => {
    expect(PROVIDERS).toEqual(["openai", "deepseek", "qwen", "kimi", "glm", "ollama"]);
  });

  it("blocks a cloud provider until a key exists", () => {
    expect(canContinue("deepseek", "")).toBe(false);
    expect(canContinue("deepseek", "sk-test")).toBe(true);
  });

  it("lets ollama continue without a key", () => {
    expect(canContinue("ollama", "")).toBe(true);
  });
});
