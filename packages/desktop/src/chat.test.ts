import { describe, expect, it } from "vitest";
import { SAMPLE_ASK, finishTwin, markPending, parseTranscript, pushUser, serializeTranscript } from "./chat";

const answer = {
  answer: "你喜欢抹茶。",
  citations: [{ n: 1, id: "饮品.md", title: "饮品", snippet: "偏好：抹茶。" }],
  disclosure: "我是用户的 AI 分身（MemRelay），依据其已审核的记忆作答，可能不准确，不代表本人表态或承诺。",
  confidence: 0.8,
  refused: false,
  face_id: "self",
};

describe("thread", () => {
  it("sends the sample ask into a user bubble and a pending twin bubble", () => {
    const next = markPending(pushUser([], SAMPLE_ASK));
    expect(next[0]).toMatchObject({ role: "user", text: "我偏好什么？" });
    expect(next[1]).toMatchObject({ role: "twin", pending: true });
  });

  it("keeps citations and disclosure on the finished twin bubble", () => {
    const done = finishTwin(markPending(pushUser([], SAMPLE_ASK)), answer);
    expect(done[1].pending).toBe(false);
    expect(done[1].citations?.[0].title).toBe("饮品");
    expect(done[1].disclosure).toContain("AI 分身");
  });

  it("round-trips the transcript", () => {
    const done = finishTwin(markPending(pushUser([], "你好")), answer);
    expect(parseTranscript(serializeTranscript(done))).toEqual(done);
  });
});
