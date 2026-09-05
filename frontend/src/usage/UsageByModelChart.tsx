import { useState } from "react";

interface ModelBreakdown {
  model: string;
  calls: number;
  total_tokens: number;
  estimated_cost_usd: number;
}

// Single-series chart (one metric — tokens — across models), so one fixed
// accent color throughout; no categorical palette or legend needed.
const BAR_COLOR = "#3F6B4A";

function formatTokens(n: number): string {
  if (n >= 1_000_000) return `${(n / 1_000_000).toFixed(1)}M`;
  if (n >= 1_000) return `${(n / 1_000).toFixed(1)}K`;
  return String(n);
}

export function UsageByModelChart({ byModel }: { byModel: ModelBreakdown[] }) {
  const [hovered, setHovered] = useState<string | null>(null);

  return (
    <div className="rounded-xl border border-border bg-card p-5 shadow-card">
      <h2 className="text-xs font-semibold uppercase tracking-wide text-muted-foreground">Tokens by Model</h2>
      {byModel.length === 0 ? (
        <p className="mt-4 text-sm text-muted-foreground">No usage recorded yet.</p>
      ) : (
        <div className="mt-4 flex flex-col gap-3">
          {[...byModel]
            .sort((a, b) => b.total_tokens - a.total_tokens)
            .map((m) => {
              const max = Math.max(...byModel.map((row) => row.total_tokens), 1);
              const pct = (m.total_tokens / max) * 100;
              return (
                <div
                  key={m.model}
                  className="relative flex items-center gap-3"
                  onMouseEnter={() => setHovered(m.model)}
                  onMouseLeave={() => setHovered(null)}
                  onFocus={() => setHovered(m.model)}
                  onBlur={() => setHovered(null)}
                  tabIndex={0}
                >
                  <span className="w-40 shrink-0 truncate text-sm font-medium text-foreground" title={m.model}>
                    {m.model}
                  </span>
                  <div className="h-4 flex-1 rounded-r-[4px] bg-muted">
                    <div
                      className="h-4 rounded-r-[4px] transition-[width] duration-300 ease-out"
                      style={{
                        width: `${pct}%`,
                        backgroundColor: BAR_COLOR,
                        minWidth: pct > 0 ? "4px" : 0,
                      }}
                    />
                  </div>
                  <span className="w-16 shrink-0 text-right text-sm tabular-nums text-foreground">
                    {formatTokens(m.total_tokens)}
                  </span>
                  {hovered === m.model && (
                    <div
                      role="tooltip"
                      className="absolute -top-11 left-40 z-10 rounded-md bg-foreground px-2.5 py-1.5 text-xs text-white shadow-card"
                    >
                      <div className="font-semibold">{formatTokens(m.total_tokens)} tokens</div>
                      <div className="text-white/80">
                        {m.calls} calls · ${m.estimated_cost_usd.toFixed(4)}
                      </div>
                    </div>
                  )}
                </div>
              );
            })}
        </div>
      )}
    </div>
  );
}
