import { useState, type FormEvent } from "react";
import { Link, useNavigate } from "react-router-dom";
import { MatchaIllustration } from "../components/MatchaIllustration";
import { useAuth } from "./AuthContext";

export function LoginPage() {
  const { login } = useAuth();
  const navigate = useNavigate();
  const [username, setUsername] = useState("");
  const [password, setPassword] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [submitting, setSubmitting] = useState(false);

  async function handleSubmit(event: FormEvent): Promise<void> {
    event.preventDefault();
    setError(null);
    setSubmitting(true);
    try {
      await login(username, password);
      navigate("/panel/docs");
    } catch {
      setError("Invalid username or password");
    } finally {
      setSubmitting(false);
    }
  }

  return (
    <div className="flex min-h-screen items-center justify-center bg-surface px-4 py-10">
      <div className="grid w-full max-w-5xl overflow-hidden rounded-2xl border border-border bg-card shadow-xl md:min-h-[560px] md:grid-cols-5">
        <div className="relative col-span-3 hidden flex-col justify-center overflow-hidden bg-gradient-to-br from-[#7BAE72] via-primary to-primary-dark bg-[length:200%_200%] p-12 animate-gradient-pan md:flex">
          <div
            aria-hidden="true"
            className="absolute inset-0 opacity-[0.08] [background-image:radial-gradient(circle,white_1.5px,transparent_1.5px)] [background-size:22px_22px]"
          />
          <div
            aria-hidden="true"
            className="animate-float-a pointer-events-none absolute -left-16 top-16 h-56 w-56 rounded-full bg-gold/20 blur-3xl"
          />
          <div
            aria-hidden="true"
            className="animate-float-b pointer-events-none absolute -bottom-10 right-0 h-64 w-64 rounded-full bg-primary-light/30 blur-3xl"
          />

          <span className="animate-fade-up absolute left-12 top-12 text-sm font-semibold uppercase tracking-widest text-white [animation-delay:0ms]">
            Matcha Bot
          </span>

          <MatchaIllustration className="animate-fade-up pointer-events-none absolute -bottom-6 -right-6 h-56 w-56 opacity-90 [animation-delay:150ms]" />

          <div className="relative flex flex-col items-start gap-6">
            <h2 className="animate-fade-up text-4xl font-semibold leading-tight text-white [animation-delay:200ms]">
              Steep the knowledge.
              <br />
              Serve the answers.
            </h2>
            <p className="animate-fade-up max-w-sm text-sm text-white/85 [animation-delay:300ms]">
              Manage recipes, users and conversation logs for your matcha &amp; tea Telegram bot.
            </p>
            <div className="animate-fade-up flex flex-wrap gap-2 [animation-delay:400ms]">
              {["Recipes", "Users", "Access Log", "Audit Log"].map((tag) => (
                <span
                  key={tag}
                  className="rounded-full border border-white/25 bg-white/10 px-3 py-1 text-xs font-medium text-white transition-colors hover:bg-white/20"
                >
                  {tag}
                </span>
              ))}
            </div>
          </div>

          <span className="absolute bottom-12 left-12 text-xs text-white/60">Admin panel</span>
        </div>

        <div className="col-span-2 flex flex-col justify-center gap-5 p-8 sm:p-12">
          <div className="flex flex-col gap-2 md:hidden">
            <span className="text-3xl" aria-hidden="true">
              🍵
            </span>
          </div>
          <form onSubmit={handleSubmit} className="animate-rise-in flex flex-col gap-5">
            <div>
              <Link
                to="/"
                className="mb-2 inline-flex items-center gap-1 text-sm text-muted-foreground transition-colors hover:text-primary"
              >
                ← Back
              </Link>
              <h1 className="text-2xl font-semibold text-foreground">Admin Login</h1>
              <p className="text-sm text-muted-foreground">Sign in to manage the Matcha Bot</p>
            </div>
            <label className="flex flex-col gap-1 text-sm font-medium text-foreground">
              Username
              <input
                value={username}
                onChange={(e) => setUsername(e.target.value)}
                className="rounded-md border border-border bg-surface px-3 py-2 text-sm text-foreground transition-colors focus-visible:border-primary"
              />
            </label>
            <label className="flex flex-col gap-1 text-sm font-medium text-foreground">
              Password
              <input
                type="password"
                value={password}
                onChange={(e) => setPassword(e.target.value)}
                className="rounded-md border border-border bg-surface px-3 py-2 text-sm text-foreground transition-colors focus-visible:border-primary"
              />
            </label>
            {error && (
              <p role="alert" className="rounded-md bg-red-50 px-3 py-2 text-sm text-red-700">
                {error}
              </p>
            )}
            <button
              type="submit"
              disabled={submitting}
              className="rounded-md bg-primary px-3 py-2.5 text-sm font-semibold text-white transition-all hover:bg-primary-dark hover:shadow-md active:scale-[0.98] disabled:cursor-not-allowed disabled:opacity-60"
            >
              {submitting ? "Logging in…" : "Log in"}
            </button>
          </form>
        </div>
      </div>
    </div>
  );
}
