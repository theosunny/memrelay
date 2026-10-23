import { useEffect, useRef, type KeyboardEvent } from "react";
import { SAMPLE_ASK, type ChatMessage } from "./chat";
import { COPY } from "./errors";

export function ChatThread({
  messages,
  draft,
  onDraft,
  onSend,
  disabled,
  onOpenModel,
}: {
  messages: ChatMessage[];
  draft: string;
  onDraft: (value: string) => void;
  onSend: (text: string) => void;
  disabled: boolean;
  onOpenModel?: () => void;
}) {
  const last = useRef<HTMLElement | null>(null);

  useEffect(() => {
    last.current?.scrollIntoView?.({ block: "nearest" });
  }, [messages]);

  function onKeyDown(event: KeyboardEvent<HTMLTextAreaElement>) {
    if (event.key !== "Enter" || event.shiftKey || event.nativeEvent.isComposing || disabled) return;
    event.preventDefault();
    onSend(draft);
  }

  return (
    <div>
      <div className="thread">
        {messages.length === 0 ? (
          <button className="chip" type="button" onClick={() => onSend(SAMPLE_ASK)}>
            {SAMPLE_ASK}
          </button>
        ) : null}
        {messages.map((message, index) => (
          <article
            key={message.id}
            ref={index === messages.length - 1 ? last : undefined}
            className={message.role === "user" ? "bubble user" : "bubble twin"}
          >
            <p>{message.pending ? "正在回答…" : message.text}</p>
            {!message.pending && message.error === "model" ? (
              <button type="button" onClick={() => onOpenModel?.()}>{COPY.openModel}</button>
            ) : null}
            {!message.pending && message.citations?.length ? (
              <ol>
                {message.citations.map((item) => (
                  <li key={`${item.n}-${item.id}`}>[{item.n}] {item.title} {item.snippet}</li>
                ))}
              </ol>
            ) : null}
            {!message.pending && message.disclosure ? <p className="disclosure">{message.disclosure}</p> : null}
          </article>
        ))}
      </div>
      <form
        className="composer"
        onSubmit={(event) => {
          event.preventDefault();
          if (!disabled) onSend(draft);
        }}
      >
        <textarea id="composer" value={draft} disabled={disabled} onChange={(event) => onDraft(event.target.value)} onKeyDown={onKeyDown} />
        <button className="primary" type="submit" disabled={disabled || !draft.trim()}>发送</button>
      </form>
    </div>
  );
}
