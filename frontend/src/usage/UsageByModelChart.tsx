import { useState } from "react";

interface ModelBreakdown {
  model: string;
  calls: number;
  total_tokens: number;
  estimated_cost_usd: number;
}

// Validated categorical palette (dataviz skill reference), fixed order —
// never cycled or reassigned when the model list changes.
const CATEGORICAL_COLORS = [
  "#2a78d6", // blue
  "#eb6834", // orange
  "#1baf7a", // aqua
  "#eda100", // yellow
  "#e87ba4", // magenta
  "#008300", // green
  "#4a3aa7", // violet
  "#e34948", // red
];

const RADIUS = 70;
const STROKE_WIDTH = 30;
const CIRCUMFERENCE = 2 * Math.PI * RADIUS;
const GAP_DEG = 2; // visual separation between adjacent segments

function formatTokens(n: number): string {
  if (n >= 1_000_000) return `${(n / 1_000_000).toFixed(1)}M`;
  if (n >= 1_000) return `${(n / 1_000).toFixed(1)}K`;
  return String(n);
}

export function UsageByModelChart({ byModel }: { byModel: ModelBreakdown[] }) {
  const [hovered, setHovered] = useState<string | null>(null);

  const total = byModel.reduce((sum, m) => sum + m.total_tokens, 0);
  const sorted = [...byModel].sort((a, b) => b.total_tokens - a.total_tokens);

  let cumulativeDeg = 0;
  const segments = sorted.map((m, i) => {
    const shareDeg = total > 0 ? (m.total_tokens / total) * 360 : 0;
    const startDeg = cumulativeDeg;
    cumulativeDeg += shareDeg;
    const arcDeg = Math.max(shareDeg - (sorted.length > 1 ? GAP_DEG : 0), 0);
    const arcLength = (arcDeg / 360) * CIRCUMFERENCE;
    return {
      model: m.model,
      calls: m.calls,
      total_tokens: m.total_tokens,
      estimated_cost_usd: m.estimated_cost_usd,
      color: CATEGORICAL_COLORS[i % CATEGORICAL_COLORS.length],
      startDeg,
      arcLength,
      pct: total > 0 ? (m.total_tokens / total) * 100 : 0,
    };
  });

  return (
    <div className="rounded-xl border border-border bg-card p-5 shadow-card">
      <h2 className="text-xs font-semibold uppercase tracking-wide text-muted-foreground">Tokens by Model</h2>
      {byModel.length === 0 ? (
        <p className="mt-4 text-sm text-muted-foreground">No usage recorded yet.</p>
      ) : (
        <div className="mt-4 flex flex-col items-center gap-6 sm:flex-row sm:items-center">
          <div className="relative shrink-0" style={{ width: 200, height: 200 }}>
            <svg width={200} height={200} viewBox="0 0 200 200">
              <g transform="translate(100 100) rotate(-90)">
                <circle r={RADIUS} fill="none" stroke="#F1EFE7" strokeWidth={STROKE_WIDTH} />
                {segments.map((seg) => (
                  <circle
                    key={seg.model}
                    r={RADIUS}
                    fill="none"
                    stroke={seg.color}
                    strokeWidth={STROKE_WIDTH}
                    strokeDasharray={`${seg.arcLength} ${CIRCUMFERENCE - seg.arcLength}`}
                    strokeDashoffset={-((seg.startDeg / 360) * CIRCUMFERENCE)}
                    strokeLinecap="butt"
                    opacity={hovered === null || hovered === seg.model ? 1 : 0.35}
                    className="transition-opacity duration-150"
                    onMouseEnter={() => setHovered(seg.model)}
                    onMouseLeave={() => setHovered(null)}
                    onFocus={() => setHovered(seg.model)}
                    onBlur={() => setHovered(null)}
                    tabIndex={0}
                    role="img"
                    aria-label={`${seg.model}: ${formatTokens(seg.total_tokens)} tokens`}
                  />
                ))}
              </g>
            </svg>
            <div className="pointer-events-none absolute inset-0 flex flex-col items-center justify-center">
              <span className="text-lg font-semibold text-foreground">{formatTokens(total)}</span>
              <span className="text-xs text-muted-foreground">tokens</span>
            </div>
            {hovered !== null &&
              (() => {
                const seg = segments.find((s) => s.model === hovered);
                if (!seg) return null;
                return (
                  <div
                    role="tooltip"
                    className="absolute left-1/2 top-full z-10 mt-2 -translate-x-1/2 whitespace-nowrap rounded-md bg-foreground px-2.5 py-1.5 text-xs text-white shadow-card"
                  >
                    <div className="font-semibold">
                      {seg.model} — {formatTokens(seg.total_tokens)} tokens ({seg.pct.toFixed(0)}%)
                    </div>
                    <div className="text-white/80">
                      {seg.calls} calls · ${seg.estimated_cost_usd.toFixed(4)}
                    </div>
                  </div>
                );
              })()}
          </div>

          <ul className="flex flex-1 flex-col gap-2">
            {segments.map((seg) => (
              <li
                key={seg.model}
                className="flex items-center gap-2 text-sm"
                onMouseEnter={() => setHovered(seg.model)}
                onMouseLeave={() => setHovered(null)}
              >
                <span
                  className="h-2.5 w-2.5 shrink-0 rounded-full"
                  style={{ backgroundColor: seg.color }}
                  aria-hidden="true"
                />
                <span className="truncate font-medium text-foreground" title={seg.model}>
                  {seg.model}
                </span>
                <span className="ml-auto shrink-0 tabular-nums text-muted-foreground">
                  {formatTokens(seg.total_tokens)} · {seg.pct.toFixed(0)}%
                </span>
              </li>
            ))}
          </ul>
        </div>
      )}
    </div>
  );
}
