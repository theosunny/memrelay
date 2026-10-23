import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it, vi } from "vitest";
import { ChatThread } from "./ChatThread";

describe("ChatThread", () => {
  it("sends the sample ask and does not open settings", async () => {
    const onSend = vi.fn();
    const user = userEvent.setup();
    render(<ChatThread messages={[]} draft="" onDraft={vi.fn()} onSend={onSend} disabled={false} />);
    expect(screen.queryByRole("dialog")).toBeNull();
    await user.click(screen.getByRole("button", { name: "我偏好什么？" }));
    expect(onSend).toHaveBeenCalledWith("我偏好什么？");
  });
});
