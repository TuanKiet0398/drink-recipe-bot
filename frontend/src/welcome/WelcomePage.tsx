import { Link } from "react-router-dom";
import { MatchaIllustration } from "../components/MatchaIllustration";

const CAPABILITIES = [
  { label: "Channels" },
  { label: "Knowledge Base" },
  { label: "Usage & Cost" },
  { label: "Audit Trail" },
];

const STEPS = [
  {
    title: "Connect a channel",
    description: "Add a Telegram bot token — more platforms are on the way.",
  },
  {
    title: "Feed it recipes",
    description: "Upload drink recipes and shop knowledge as plain text or markdown.",
  },
  {
    title: "It chats with personality",
    description: "A warm, expert host tone (SOUL.md) — never invents what isn't in your knowledge.",
  },
  {
    title: "Watch everything",
    description: "Conversations, token cost, and every admin action stay visible and searchable.",
  },
];

const FEATURES = [
  {
    title: "Channels",
    description: "Connect multiple bots at once — encrypted credentials, live start/stop, no restarts.",
    icon: (
      <path
        strokeLinecap="round"
        strokeLinejoin="round"
        d="M13 10V3L4 14h7v7l9-11h-7z"
      />
    ),
  },
  {
    title: "Documents & Recipes",
    description: "Upload the drink knowledge the bot answers from — bilingual chunking built in.",
    icon: (
      <path
        strokeLinecap="round"
        strokeLinejoin="round"
        d="M9 12h6m-6 4h6m2 5H7a2 2 0 01-2-2V5a2 2 0 012-2h5.586a1 1 0 01.707.293l5.414 5.414a1 1 0 01.293.707V19a2 2 0 01-2 2z"
      />
    ),
  },
  {
    title: "Users",
    description: "See every customer who has chatted with the bot, per channel. Block or unblock.",
    icon: (
      <path
        strokeLinecap="round"
        strokeLinejoin="round"
        d="M17 20h5v-2a4 4 0 00-3-3.87M9 20H4v-2a4 4 0 013-3.87m5-4.13a4 4 0 100-8 4 4 0 000 8zm6 4c0 1.657-3.134 3-7 3s-7-1.343-7-3 3.134-3 7-3 7 1.343 7 3z"
      />
    ),
  },
  {
    title: "Usage & Cost",
    description: "Token usage and estimated cost by model, charted — filter, drill in, clean up.",
    icon: (
      <path
        strokeLinecap="round"
        strokeLinejoin="round"
        d="M9 19v-6a2 2 0 00-2-2H5a2 2 0 00-2 2v6a2 2 0 002 2h2a2 2 0 002-2zm0 0V9a2 2 0 012-2h2a2 2 0 012 2v10m0 0V5a2 2 0 012-2h2a2 2 0 012 2v14"
      />
    ),
  },
  {
    title: "Access Log",
    description: "Read the full conversation history between customers and the bot.",
    icon: (
      <path
        strokeLinecap="round"
        strokeLinejoin="round"
        d="M8 12h.01M12 12h.01M16 12h.01M21 12c0 4.418-4.03 8-9 8a9.86 9.86 0 01-4.255-.949L3 20l1.395-3.72C3.512 15.042 3 13.574 3 12c0-4.418 4.03-8 9-8s9 3.582 9 8z"
      />
    ),
  },
  {
    title: "Audit Log",
    description: "Every admin action — including failed logins — with IP, target and timestamp.",
    icon: (
      <path
        strokeLinecap="round"
        strokeLinejoin="round"
        d="M9 12l2 2 4-4m6 2a9 9 0 11-18 0 9 9 0 0118 0z"
      />
    ),
  },
];

function FeatureIcon({ children }: { children: React.ReactNode }) {
  return (
    <span className="inline-flex h-10 w-10 items-center justify-center rounded-lg bg-primary-light text-primary-dark">
      <svg viewBox="0 0 24 24" className="h-5 w-5" fill="none" stroke="currentColor" strokeWidth={1.8} aria-hidden="true">
        {children}
      </svg>
    </span>
  );
}

export function WelcomePage() {
  return (
    <div className="min-h-screen bg-surface">
      <header className="mx-auto flex max-w-5xl items-center justify-between px-6 py-5">
        <span className="flex items-center gap-2 text-sm font-semibold text-primary-dark">
          <span aria-hidden="true">🍵</span>
          Shop Assistant Admin
        </span>
        <Link
          to="/login"
          className="rounded-md px-3 py-1.5 text-sm font-medium text-primary-dark transition-colors hover:bg-primary-light"
        >
          Log in
        </Link>
      </header>

      <section className="relative overflow-hidden bg-gradient-to-br from-[#7BAE72] via-primary to-primary-dark bg-[length:200%_200%] animate-gradient-pan">
        <div
          aria-hidden="true"
          className="absolute inset-0 opacity-[0.08] [background-image:radial-gradient(circle,white_1.5px,transparent_1.5px)] [background-size:22px_22px]"
        />

        <div className="relative mx-auto grid max-w-5xl grid-cols-1 items-center gap-10 px-6 py-16 md:grid-cols-2 md:py-24">
          <div className="text-center md:text-left">
            <span className="animate-fade-up inline-block text-sm font-semibold uppercase tracking-widest text-white [animation-delay:0ms]">
              Multi-channel bot admin
            </span>

            <h1 className="animate-fade-up mt-4 text-4xl font-semibold leading-tight text-white sm:text-5xl [animation-delay:100ms]">
              Steep the knowledge.
              <br />
              Serve every channel.
            </h1>

            <p className="animate-fade-up mx-auto mt-4 max-w-md text-base text-white/85 md:mx-0 [animation-delay:200ms]">
              The admin panel behind your drinks assistant bot — connect channels, teach it
              recipes, and watch every conversation, cost and action in one place.
            </p>

            <div className="animate-fade-up mt-8 flex flex-wrap items-center justify-center gap-3 md:justify-start [animation-delay:300ms]">
              <Link
                to="/login"
                className="inline-block rounded-md bg-white px-6 py-3 text-sm font-semibold text-primary-dark shadow-lg transition-transform hover:scale-105"
              >
                Enter Admin Panel
              </Link>
            </div>

            <div className="animate-fade-up mt-8 flex flex-wrap items-center justify-center gap-x-5 gap-y-2 md:justify-start [animation-delay:400ms]">
              {CAPABILITIES.map((c) => (
                <span key={c.label} className="flex items-center gap-1.5 text-xs font-medium text-white/75">
                  <span className="h-1.5 w-1.5 rounded-full bg-gold" aria-hidden="true" />
                  {c.label}
                </span>
              ))}
            </div>
          </div>

          <div className="animate-fade-up mx-auto w-full max-w-sm [animation-delay:200ms]">
            <MatchaIllustration className="w-full drop-shadow-xl" />
          </div>
        </div>
      </section>

      <section className="mx-auto max-w-5xl px-6 py-16">
        <h2 className="text-center text-sm font-semibold uppercase tracking-widest text-muted-foreground">
          How it works
        </h2>
        <div className="mt-8 grid grid-cols-1 gap-6 sm:grid-cols-2 lg:grid-cols-4">
          {STEPS.map((step, i) => (
            <div key={step.title} className="animate-rise-in relative pl-10" style={{ animationDelay: `${i * 80}ms` }}>
              <span className="absolute left-0 top-0 flex h-7 w-7 items-center justify-center rounded-full bg-primary text-xs font-semibold text-white">
                {i + 1}
              </span>
              <h3 className="text-sm font-semibold text-foreground">{step.title}</h3>
              <p className="mt-1 text-xs text-muted-foreground">{step.description}</p>
            </div>
          ))}
        </div>
      </section>

      <section className="mx-auto max-w-5xl px-6 py-16">
        <h2 className="text-center text-sm font-semibold uppercase tracking-widest text-muted-foreground">
          Everything in one panel
        </h2>
        <div className="mt-8 grid grid-cols-1 gap-4 sm:grid-cols-2 lg:grid-cols-3">
          {FEATURES.map((feature) => (
            <div
              key={feature.title}
              className="flex flex-col gap-3 rounded-xl border border-border bg-card p-5 shadow-card transition-transform hover:-translate-y-1"
            >
              <FeatureIcon>{feature.icon}</FeatureIcon>
              <div>
                <h3 className="text-sm font-semibold text-foreground">{feature.title}</h3>
                <p className="mt-1 text-xs text-muted-foreground">{feature.description}</p>
              </div>
            </div>
          ))}
        </div>
      </section>

      <section className="border-t border-border bg-card">
        <div className="mx-auto flex max-w-5xl flex-col items-center gap-4 px-6 py-14 text-center">
          <h2 className="text-2xl font-semibold text-foreground">Ready to see it running?</h2>
          <p className="max-w-md text-sm text-muted-foreground">
            Log in to connect a channel, upload your first recipes, and watch the bot go live.
          </p>
          <Link
            to="/login"
            className="mt-2 inline-block rounded-md bg-primary px-6 py-3 text-sm font-semibold text-white shadow-lg transition-transform hover:scale-105 hover:bg-primary-dark"
          >
            Enter Admin Panel
          </Link>
        </div>
      </section>
    </div>
  );
}
