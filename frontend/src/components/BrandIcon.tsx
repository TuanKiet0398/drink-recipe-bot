export function BrandIcon({ className = "h-5 w-5" }: { className?: string }) {
  return (
    <svg
      viewBox="0 0 24 24"
      className={className}
      fill="none"
      stroke="currentColor"
      strokeWidth={1.8}
      strokeLinecap="round"
      strokeLinejoin="round"
      aria-hidden="true"
    >
      {/* steam */}
      <path d="M9 2.5c-1 1.2 1 1.8 0 3" opacity={0.7} />
      <path d="M13 2.5c-1 1.2 1 1.8 0 3" opacity={0.7} />
      {/* cup */}
      <path d="M4 9h13v6a4 4 0 01-4 4H8a4 4 0 01-4-4V9z" />
      <path d="M17 10h1.5a2.5 2.5 0 010 5H17" />
      <path d="M4 9h13" />
    </svg>
  );
}
