import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it, vi } from "vitest";
import { ModelGate } from "./ModelGate";

describe("ModelGate", () => {
  it("hides service settings and waits for a deepseek key", async () => {
    const onSave = vi.fn();
    const user = userEvent.setup();
    render(<ModelGate onSave={onSave} />);
    expect(screen.queryByLabelText("服务地址")).toBeNull();
    expect(screen.queryByRole("navigation")).toBeNull();
    const button = screen.getByRole("button", { name: "继续" });
    expect(button).toHaveProperty("disabled", true);
    await user.selectOptions(screen.getByLabelText("模型"), "deepseek");
    expect(button).toHaveProperty("disabled", true);
    await user.type(screen.getByLabelText("API Key"), "sk-test");
    expect(button).toHaveProperty("disabled", false);
    await user.click(button);
    expect(onSave).toHaveBeenCalledWith({ provider: "deepseek", apiKey: "sk-test", model: "" });
  });
});
