// src/ChatBox.jsx
import React, { useEffect, useRef, useState } from "react";

export default function ChatBox({ title = "Chat", onSend }) {
  const [messages, setMessages] = useState([
    { role: "assistant", text: "Hi! Ask me anything here." },
  ]);
  const [draft, setDraft] = useState("");
  const listRef = useRef(null);

  // auto-scroll to bottom when messages change
  useEffect(() => {
    if (listRef.current) {
      listRef.current.scrollTop = listRef.current.scrollHeight;
    }
  }, [messages]);

  const send = async () => {
    const text = draft.trim();
    if (!text) return;
    setDraft("");

    // push user message
    setMessages((m) => [...m, { role: "user", text }]);

    // optional: call backend via onSend
    if (onSend) {
      try {
        const reply = await onSend(text);
        setMessages((m) => [...m, { role: "assistant", text: reply ?? "(no reply)" }]);
        return;
      } catch (e) {
        setMessages((m) => [...m, { role: "assistant", text: "Error: " + (e?.message || "failed") }]);
        return;
      }
    }

    // mock assistant reply (remove once wired to backend)
    setTimeout(() => {
      setMessages((m) => [
        ...m,
        { role: "assistant", text: "You said: " + text },
      ]);
    }, 500);
  };

  const onKeyDown = (e) => {
    if (e.key === "Enter" && !e.shiftKey) {
      e.preventDefault();
      send();
    }
  };

  return (
    <section className="card chat">
      <div className="chat-head">
        <h2>{title}</h2>
      </div>

      <div className="chat-list" ref={listRef} aria-live="polite">
        {messages.map((m, i) => (
          <Message key={i} role={m.role} text={m.text} />
        ))}
      </div>

      <div className="chat-input">
        <textarea
          placeholder="Type your message... (Enter to send, Shift+Enter for a new line)"
          value={draft}
          onChange={(e) => setDraft(e.target.value)}
          onKeyDown={onKeyDown}
          rows={2}
        />
        <button className="btn primary" onClick={send} aria-label="Send message">
          Send
        </button>
      </div>
    </section>
  );
}

function Message({ role, text }) {
  const isUser = role === "user";
  return (
    <div className={`chat-bubble ${isUser ? "me" : "bot"}`}>
      <div className="chat-meta">{isUser ? "You" : "Assistant"}</div>
      <div className="chat-text">{text}</div>
    </div>
  );
}
