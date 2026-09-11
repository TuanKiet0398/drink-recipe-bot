import { useEffect, useRef, useState } from "react";
import { apiFetch, readableError } from "../api/client";
import { useAuth } from "../auth/AuthContext";
import { BrandIcon } from "../components/BrandIcon";
import * as s from "../layout/styles";

interface ChatMessage {
  role: "user" | "assistant";
  content: string;
  model?: string;
}

interface ChatReply {
  reply: string;
  model: string;
}

interface HistoryItem {
  role: "user" | "assistant";
  content: string;
  created_at: string;
}

interface LLMSettings {
  provider: string;
  chat_model: string;
}

const PROVIDER_LABELS: Record<string, string> = { openai: "OpenAI", ollama: "Ollama" };

function BotAvatar() {
  return (
    <span
      aria-hidden="true"
      className="flex h-[26px] w-[26px] shrink-0 items-center justify-center rounded-full bg-admin-primary-light text-admin-primary-dark"
    >
      <BrandIcon className="h-3.5 w-3.5" />
    </span>
  );
}

export function ChatPage() {
  const { username } = useAuth();
  const [settings, setSettings] = useState<LLMSettings | null>(null);
  const [messages, setMessages] = useState<ChatMessage[]>([]);
  const [draft, setDraft] = useState("");
  const [sending, setSending] = useState(false);
  const [resetting, setResetting] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const panelRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    apiFetch<LLMSettings>("/admin/llm-settings")
      .then(setSettings)
      .catch(() => setSettings(null));
    apiFetch<HistoryItem[]>("/admin/chat/history")
      .then((items) => {
        const loaded = items.map(({ role, content }) => ({ role, content }));
        // Prepend: a message sent before the history arrived must not be lost.
        setMessages((current) => [...loaded, ...current]);
      })
      .catch(() => setError("Failed to load the conversation"));
  }, []);

  useEffect(() => {
    const panel = panelRef.current;
    if (panel) panel.scrollTop = panel.scrollHeight;
  }, [messages, sending]);

  async function send(e: React.FormEvent): Promise<void> {
    e.preventDefault();
    const text = draft.trim();
    if (!text || sending) return;
    setMessages((current) => [...current, { role: "user", content: text }]);
    setDraft("");
    setSending(true);
    setError(null);
    try {
      const data = await apiFetch<ChatReply>("/admin/chat", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ message: text }),
      });
      setMessages((current) => [...current, { role: "assistant", content: data.reply, model: data.model }]);
    } catch (err) {
      setError(readableError(err, "Failed to get a reply"));
    } finally {
      setSending(false);
    }
  }

  async function reset(): Promise<void> {
    setResetting(true);
    try {
      await apiFetch("/admin/chat/history", { method: "DELETE" });
      setMessages([]);
      setError(null);
    } catch {
      setError("Failed to reset the conversation");
    } finally {
      setResetting(false);
    }
  }

  return (
    <div className="flex h-[calc(100vh-120px)] flex-col gap-4">
      <div>
        <h1 className={s.pageTitle}>Chat</h1>
        <p className={s.pageDescription}>
          Chat with the bot. It remembers your preferences between conversations.
        </p>
      </div>

      <div className="flex flex-wrap items-center justify-between gap-2 rounded-[10px] border border-admin-border bg-white px-3.5 py-2.5">
        <div className="flex items-center gap-2 text-[12.5px] text-admin-muted">
          {settings && (
            <>
              <span className="inline-flex items-center gap-1.5 rounded-full bg-admin-primary-light px-2.5 py-0.5 font-semibold text-admin-primary-dark">
                <span aria-hidden="true" className="h-1.5 w-1.5 rounded-full bg-admin-primary" />
                {settings.chat_model}
              </span>
              <span>via {PROVIDER_LABELS[settings.provider] ?? settings.provider}</span>
            </>
          )}
        </div>
        <div className="flex items-center gap-2.5">
          <span className="text-xs text-admin-muted">Clears the chat history. Remembered preferences stay.</span>
          <button
            onClick={reset}
            disabled={sending || resetting}
            className={`${s.btnSecondary} px-3 py-1.5 text-[12.5px]`}
          >
            Reset conversation
          </button>
        </div>
      </div>

      {error && (
        <p role="alert" className={s.alertError}>
          {error}
        </p>
      )}

      <div ref={panelRef} className={`${s.card} flex flex-1 flex-col gap-3 overflow-y-auto overflow-x-hidden p-[18px]`}>
        {messages.length === 0 && !sending && (
          <p className="m-auto text-[13.5px] text-admin-muted">Send a message to start chatting with the bot.</p>
        )}
        {messages.map((message, index) => {
          const isUser = message.role === "user";
          return (
            <div key={index} className={`flex items-start gap-2 ${isUser ? "justify-end" : "justify-start"}`}>
              {!isUser && <BotAvatar />}
              <div className="flex max-w-[70%] flex-col">
                <div
                  className={
                    isUser
                      ? "whitespace-pre-wrap rounded-[14px_14px_4px_14px] bg-admin-primary px-3.5 py-2.5 text-[13.5px] leading-snug text-white"
                      : "whitespace-pre-wrap rounded-[14px_14px_14px_4px] border border-admin-border bg-admin-bg px-3.5 py-2.5 text-[13.5px] leading-snug text-admin-fg"
                  }
                >
                  {message.content}
                </div>
                <span className={`mt-0.5 text-[10.5px] text-admin-label ${isUser ? "text-right" : "text-left"}`}>
                  {isUser ? username : message.model ? `Bot · ${message.model}` : "Bot"}
                </span>
              </div>
              {isUser && (
                <span
                  aria-hidden="true"
                  className="flex h-[26px] w-[26px] shrink-0 items-center justify-center rounded-full bg-admin-primary text-[11px] font-bold text-white"
                >
                  {(username ?? "?").charAt(0).toUpperCase()}
                </span>
              )}
            </div>
          );
        })}
        {sending && (
          <div className="flex items-start justify-start gap-2">
            <BotAvatar />
            <div className="max-w-[70%] rounded-[14px_14px_14px_4px] border border-admin-border bg-admin-bg px-3.5 py-2.5 text-[13.5px] text-admin-muted">
              Đang trả lời…
            </div>
          </div>
        )}
      </div>

      <form onSubmit={send} className="flex gap-2">
        <input
          aria-label="Message"
          value={draft}
          onChange={(e) => setDraft(e.target.value)}
          placeholder="Nhắn bot, ví dụ: cách pha matcha đá?"
          className={`${s.input} flex-1`}
        />
        <button
          type="submit"
          disabled={sending}
          className="rounded-[9px] bg-admin-primary px-5 text-[13.5px] font-semibold text-white hover:bg-admin-primary-dark disabled:cursor-not-allowed disabled:bg-[#9FB396]"
        >
          Send
        </button>
      </form>
    </div>
  );
}
