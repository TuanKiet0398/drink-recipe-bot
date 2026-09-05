import { Link } from "react-router-dom";
import { MatchaIllustration } from "../components/MatchaIllustration";

const FEATURES = [
  {
    title: "Documents & Recipes",
    description: "Upload the tea and matcha knowledge the bot answers from.",
  },
  {
    title: "Users",
    description: "See every Telegram user who has chatted with the bot, block or unblock.",
  },
  {
    title: "Access Log",
    description: "Read the full conversation history between users and the bot.",
  },
  {
    title: "Audit Log",
    description: "Track every admin action taken in this panel, with IP and timestamp.",
  },
];

export function WelcomePage() {
  return (
    <div className="min-h-screen bg-surface">
      <section className="relative overflow-hidden bg-gradient-to-br from-[#7BAE72] via-primary to-primary-dark bg-[length:200%_200%] animate-gradient-pan">
        <div
          aria-hidden="true"
          className="absolute inset-0 opacity-[0.08] [background-image:radial-gradient(circle,white_1.5px,transparent_1.5px)] [background-size:22px_22px]"
        />

        <div className="relative mx-auto grid max-w-5xl grid-cols-1 items-center gap-10 px-6 py-20 md:grid-cols-2 md:py-28">
          <div className="text-center md:text-left">
            <span className="animate-fade-up inline-block text-sm font-semibold uppercase tracking-widest text-white [animation-delay:0ms]">
              Matcha Bot
            </span>

            <h1 className="animate-fade-up mt-4 text-4xl font-semibold leading-tight text-white sm:text-5xl [animation-delay:100ms]">
              Steep the knowledge.
              <br />
              Serve the answers.
            </h1>

            <p className="animate-fade-up mx-auto mt-4 max-w-md text-base text-white/85 md:mx-0 [animation-delay:200ms]">
              The admin panel behind your matcha &amp; tea Telegram assistant — manage recipes,
              users and conversation history in one place.
            </p>

            <Link
              to="/login"
              className="animate-fade-up mt-8 inline-block rounded-md bg-white px-6 py-3 text-sm font-semibold text-primary-dark shadow-lg transition-transform hover:scale-105 [animation-delay:300ms]"
            >
              Enter Admin Panel
            </Link>
          </div>

          <div className="animate-fade-up mx-auto w-full max-w-sm [animation-delay:200ms]">
            <MatchaIllustration className="w-full drop-shadow-xl" />
          </div>
        </div>
      </section>

      <section className="mx-auto max-w-5xl px-6 py-16">
        <h2 className="text-center text-sm font-semibold uppercase tracking-widest text-muted-foreground">
          Everything in one panel
        </h2>
        <div className="mt-8 grid grid-cols-1 gap-4 sm:grid-cols-2 lg:grid-cols-4">
          {FEATURES.map((feature) => (
            <div
              key={feature.title}
              className="rounded-xl border border-border bg-card p-5 shadow-card transition-transform hover:-translate-y-1"
            >
              <h3 className="text-sm font-semibold text-foreground">{feature.title}</h3>
              <p className="mt-1 text-xs text-muted-foreground">{feature.description}</p>
            </div>
          ))}
        </div>
      </section>
    </div>
  );
}
