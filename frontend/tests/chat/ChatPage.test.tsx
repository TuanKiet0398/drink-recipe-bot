import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { http, HttpResponse } from "msw";
import { describe, expect, it, beforeEach } from "vitest";
import { server } from "../mocks/server";
import { API_BASE } from "../mocks/handlers";
import { storeCredentials } from "../../src/api/client";
import { AuthProvider } from "../../src/auth/AuthContext";
import { ChatPage } from "../../src/chat/ChatPage";

const settings = {
  provider: "openai",
  base_url: null,
  chat_model: "gpt-4o-mini",
  has_api_key: true,
  is_default: false,
  daily_token_limit: null,
  updated_at: null,
  updated_by: null,
};

beforeEach(() => {
  sessionStorage.clear();
  import.meta.env.VITE_API_BASE_URL = API_BASE;
  storeCredentials("admin", "admin");
  server.use(http.get(`${API_BASE}/admin/llm-settings`, () => HttpResponse.json(settings)));
});

function renderPage() {
  render(
    <AuthProvider>
      <ChatPage />
    </AuthProvider>
  );
}

async function sendMessage(text: string) {
  await userEvent.type(screen.getByLabelText("Message"), text);
  await userEvent.click(screen.getByRole("button", { name: "Send" }));
}

describe("ChatPage", () => {
  it("shows the configured model and provider", async () => {
    renderPage();
    expect(await screen.findByText("gpt-4o-mini")).toBeInTheDocument();
    expect(screen.getByText("via OpenAI")).toBeInTheDocument();
  });

  it("sends the message with the prior conversation as history", async () => {
    const bodies: unknown[] = [];
    server.use(
      http.post(`${API_BASE}/admin/chat`, async ({ request }) => {
        bodies.push(await request.json());
        return HttpResponse.json({ reply: `reply-${bodies.length}`, model: "gpt-4o-mini" });
      })
    );
    renderPage();

    await sendMessage("first question");
    expect(screen.getByText("first question")).toBeInTheDocument();
    expect(await screen.findByText("reply-1")).toBeInTheDocument();
    expect(screen.getByText("Bot · gpt-4o-mini")).toBeInTheDocument();

    await sendMessage("second question");
    expect(await screen.findByText("reply-2")).toBeInTheDocument();

    expect(bodies).toEqual([
      { message: "first question", history: [] },
      {
        message: "second question",
        history: [
          { role: "user", content: "first question" },
          { role: "assistant", content: "reply-1" },
        ],
      },
    ]);
  });

  it("disables Send and shows a typing bubble while waiting", async () => {
    let release!: () => void;
    const gate = new Promise<void>((resolve) => {
      release = resolve;
    });
    server.use(
      http.post(`${API_BASE}/admin/chat`, async () => {
        await gate;
        return HttpResponse.json({ reply: "done", model: "gpt-4o-mini" });
      })
    );
    renderPage();

    await sendMessage("hello");
    expect(screen.getByRole("button", { name: "Send" })).toBeDisabled();
    expect(screen.getByText("Đang trả lời…")).toBeInTheDocument();

    release();
    expect(await screen.findByText("done")).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Send" })).toBeEnabled();
  });

  it("does not send a blank message", async () => {
    let calls = 0;
    server.use(
      http.post(`${API_BASE}/admin/chat`, () => {
        calls += 1;
        return HttpResponse.json({ reply: "x", model: "m" });
      })
    );
    renderPage();

    await sendMessage("   ");
    expect(calls).toBe(0);
  });

  it("shows the server error when the bot fails", async () => {
    server.use(
      http.post(`${API_BASE}/admin/chat`, () =>
        HttpResponse.json({ detail: "Incorrect API key provided" }, { status: 502 })
      )
    );
    renderPage();

    await sendMessage("hello");
    expect(await screen.findByRole("alert")).toHaveTextContent("Incorrect API key provided");
    expect(screen.getByText("hello")).toBeInTheDocument();
  });

  it("clears the conversation on reset", async () => {
    server.use(
      http.post(`${API_BASE}/admin/chat`, () => HttpResponse.json({ reply: "the reply", model: "gpt-4o-mini" }))
    );
    renderPage();

    await sendMessage("hello");
    expect(await screen.findByText("the reply")).toBeInTheDocument();

    await userEvent.click(screen.getByRole("button", { name: "Reset conversation" }));
    await waitFor(() => expect(screen.queryByText("the reply")).not.toBeInTheDocument());
    expect(screen.queryByText("hello")).not.toBeInTheDocument();
  });
});
