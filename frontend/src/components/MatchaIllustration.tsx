export function MatchaIllustration({ className = "" }: { className?: string }) {
  return (
    <svg
      viewBox="0 0 320 320"
      className={className}
      fill="none"
      xmlns="http://www.w3.org/2000/svg"
      aria-hidden="true"
    >
      {/* steam */}
      <g className="animate-steam-path" style={{ animationDelay: "0ms" }}>
        <path
          d="M140 90c-8 14 12 18 4 32"
          stroke="white"
          strokeOpacity="0.75"
          strokeWidth="4"
          strokeLinecap="round"
        />
      </g>
      <g className="animate-steam-path" style={{ animationDelay: "500ms" }}>
        <path
          d="M165 78c-8 14 12 18 4 32"
          stroke="white"
          strokeOpacity="0.85"
          strokeWidth="5"
          strokeLinecap="round"
        />
      </g>
      <g className="animate-steam-path" style={{ animationDelay: "1000ms" }}>
        <path
          d="M190 90c-8 14 12 18 4 32"
          stroke="white"
          strokeOpacity="0.75"
          strokeWidth="4"
          strokeLinecap="round"
        />
      </g>

      {/* bowl (chawan) */}
      <path
        d="M95 165h140l-14 55c-3 22-27 38-56 38s-53-16-56-38l-14-55z"
        fill="#FBF9F3"
      />
      <path
        d="M95 165h140l-14 55c-3 22-27 38-56 38s-53-16-56-38l-14-55z"
        stroke="#2F5238"
        strokeOpacity="0.15"
        strokeWidth="2"
      />
      {/* matcha surface */}
      <ellipse cx="165" cy="167" rx="72" ry="16" fill="#5C8A52" />
      <ellipse cx="165" cy="165" rx="72" ry="15" fill="#79A968" />
      <path
        d="M110 163c14-8 30 8 44 0s32-8 44 2"
        stroke="#EFF6EA"
        strokeOpacity="0.6"
        strokeWidth="3"
        strokeLinecap="round"
      />

      {/* whisk (chasen) resting on the rim */}
      <g transform="translate(226 132) rotate(28)">
        <rect x="-6" y="-38" width="12" height="34" rx="6" fill="#C9A227" />
        {[-10, -5, 0, 5, 10].map((dx) => (
          <path
            key={dx}
            d={`M${dx} -6 L${dx * 1.8} 26`}
            stroke="#D9B94A"
            strokeWidth="2.5"
            strokeLinecap="round"
          />
        ))}
      </g>

      {/* floating leaves */}
      <g className="animate-sway" style={{ transformOrigin: "60px 90px" }}>
        <path
          d="M60 70c16 4 24 20 16 34-16-4-24-20-16-34z"
          fill="#C9A227"
          fillOpacity="0.55"
        />
        <path d="M60 78c6 6 8 14 8 20" stroke="#7A5E12" strokeOpacity="0.3" strokeWidth="1.5" />
      </g>
      <g className="animate-sway" style={{ animationDelay: "800ms", transformOrigin: "252px 74px" }}>
        <path
          d="M252 58c14 5 20 20 12 32-14-5-20-20-12-32z"
          fill="#E8F0E6"
          fillOpacity="0.7"
        />
        <path d="M252 65c5 5 7 12 6 18" stroke="#2F5238" strokeOpacity="0.25" strokeWidth="1.5" />
      </g>
      <g className="animate-sway" style={{ animationDelay: "1400ms", transformOrigin: "80px 220px" }}>
        <path
          d="M80 206c14 4 20 18 13 30-14-4-20-18-13-30z"
          fill="#7BAE72"
          fillOpacity="0.5"
        />
      </g>
    </svg>
  );
}
