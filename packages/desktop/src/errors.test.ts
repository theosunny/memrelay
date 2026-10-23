import { describe, expect, it } from "vitest";
import { COPY } from "./errors";

describe("COPY", () => {
  it("hides hosts and quarantine instructions", () => {
    const blob = Object.values(COPY).join("\n");
    expect(blob).not.toContain("127.0.0.1");
    expect(blob).not.toContain("8787");
    expect(blob).not.toContain("xattr");
    expect(blob).not.toContain("右键");
    expect(COPY.sidecarDown).toBe("分身暂时没连上");
    expect(COPY.modelRejected).toBe("这次没有答上来。");
  });
});
