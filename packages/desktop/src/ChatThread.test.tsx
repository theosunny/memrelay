import { cleanup, render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, describe, expect, it, vi } from "vitest";
import { ChatThread } from "./ChatThread";

describe("ChatThread", () => {
  afterEach(() => cleanup());

  it("sends the sample ask and does not open settings", async () => {
    const onSend = vi.fn();
    const user = userEvent.setup();
    render(<ChatThread messages={[]} draft="" onDraft={vi.fn()} onSend={onSend} disabled={false} />);
    expect(screen.queryByRole("dialog")).toBeNull();
    await user.click(screen.getByRole("button", { name: "我偏好什么？" }));
    expect(onSend).toHaveBeenCalledWith("我偏好什么？");
  });

  it("opens everyday model settings from a rejected answer", async () => {
    const onOpenModel = vi.fn();
    const user = userEvent.setup();
    render(
      <ChatThread
        messages={[{ id: "1", role: "twin", text: "这次没有答上来。", error: "model" }]}
        draft=""
        onDraft={vi.fn()}
        onSend={vi.fn()}
        disabled={false}
        onOpenModel={onOpenModel}
      />,
    );
    await user.click(screen.getByRole("button", { name: "去填写模型" }));
    expect(onOpenModel).toHaveBeenCalledOnce();
  });

  it("keeps the disclosure when the vault has no matching memory", () => {
    render(
      <ChatThread
        messages={[{
          id: "1",
          role: "twin",
          text: "我不知道——我的记忆里没有相关内容。",
          disclosure: "我是用户的 AI 分身（MemRelay）。",
        }]}
        draft=""
        onDraft={vi.fn()}
        onSend={vi.fn()}
        disabled={false}
      />,
    );
    expect(screen.getByText("我是用户的 AI 分身（MemRelay）。").className).toBe("disclosure");
    expect(screen.queryByRole("button", { name: "去填写模型" })).toBeNull();
  });
});
