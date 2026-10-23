import type { Answer, Citation } from "./api";

export const SAMPLE_ASK = "我偏好什么？";

export type ChatMessage = {
  id: string;
  role: "user" | "twin";
  text: string;
  pending?: boolean;
  disclosure?: string;
  citations?: Citation[];
  error?: "model";
};

export function pushUser(messages: ChatMessage[], text: string): ChatMessage[] {
  return [...messages, { id: crypto.randomUUID(), role: "user", text }];
}

export function markPending(messages: ChatMessage[]): ChatMessage[] {
  return [...messages, { id: crypto.randomUUID(), role: "twin", text: "", pending: true }];
}

export function finishTwin(messages: ChatMessage[], answer: Answer): ChatMessage[] {
  const next = messages.slice();
  const last = next[next.length - 1];
  if (!last || last.role !== "twin" || !last.pending) return messages;
  next[next.length - 1] = {
    ...last,
    pending: false,
    text: answer.answer,
    disclosure: answer.disclosure,
    citations: answer.citations,
  };
  return next;
}

export function failTwin(messages: ChatMessage[]): ChatMessage[] {
  const next = messages.slice();
  const last = next[next.length - 1];
  if (!last || last.role !== "twin" || !last.pending) return messages;
  next[next.length - 1] = { ...last, pending: false, error: "model" };
  return next;
}

export function parseTranscript(raw: string): ChatMessage[] {
  if (!raw.trim()) return [];
  try {
    const data: unknown = JSON.parse(raw);
    return Array.isArray(data) ? (data as ChatMessage[]) : [];
  } catch {
    return [];
  }
}

export function serializeTranscript(messages: ChatMessage[]): string {
  return JSON.stringify(messages);
}
