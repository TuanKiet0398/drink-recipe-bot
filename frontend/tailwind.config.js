export default {
  content: ["./index.html", "./src/**/*.{ts,tsx}"],
  theme: {
    extend: {
      fontFamily: {
        sans: ["Inter", "system-ui", "sans-serif"],
      },
      colors: {
        primary: {
          DEFAULT: "#3F6B4A",
          dark: "#2F5238",
          light: "#E8F0E6",
        },
        gold: "#E3B23C",
        surface: "#F7F5EF",
        card: "#FFFFFF",
        border: "#E3DFD3",
        muted: "#F1EFE7",
        "muted-foreground": "#6B7566",
        foreground: "#22291F",
        // Admin panel palette (references/Matcha Admin Redesign.dc.html).
        // Kept separate so the landing and login pages don't change.
        admin: {
          primary: "#3E6B37",
          "primary-dark": "#2C4F27",
          "primary-light": "#E4EEDD",
          bg: "#F5F7F1",
          border: "#DCE3D4",
          divider: "#ECEFE6",
          fg: "#1C2A1F",
          "fg-2": "#33422F",
          muted: "#55604D",
          label: "#7C8874",
          danger: "#B91C1C",
          "danger-light": "#FEF2F2",
          "danger-border": "#F3C6C6",
        },
      },
      boxShadow: {
        card: "0 1px 2px 0 rgb(0 0 0 / 0.04), 0 1px 3px 0 rgb(0 0 0 / 0.06)",
        "admin-card": "0 1px 2px rgba(28, 42, 31, 0.06)",
      },
      keyframes: {
        "float-a": {
          "0%, 100%": { transform: "translate(0, 0) scale(1)" },
          "50%": { transform: "translate(45px, -55px) scale(1.25)" },
        },
        "float-b": {
          "0%, 100%": { transform: "translate(0, 0) scale(1)" },
          "50%": { transform: "translate(-50px, 45px) scale(1.2)" },
        },
        "steam": {
          "0%": { transform: "translateY(0) scaleX(1)", opacity: "0.7" },
          "50%": { transform: "translateY(-14px) scaleX(1.8)", opacity: "1" },
          "100%": { transform: "translateY(-26px) scaleX(1)", opacity: "0" },
        },
        "rise-in": {
          "0%": { transform: "translateY(12px)", opacity: "0" },
          "100%": { transform: "translateY(0)", opacity: "1" },
        },
        "fade-up": {
          "0%": { transform: "translateY(10px)", opacity: "0" },
          "100%": { transform: "translateY(0)", opacity: "1" },
        },
        "gradient-pan": {
          "0%, 100%": { backgroundPosition: "0% 50%" },
          "50%": { backgroundPosition: "100% 50%" },
        },
        "pulse-soft": {
          "0%, 100%": { transform: "scale(1) rotate(0deg)" },
          "50%": { transform: "scale(1.15) rotate(-4deg)" },
        },
        "steam-path": {
          "0%": { transform: "translateY(0)", opacity: "0" },
          "20%": { opacity: "0.9" },
          "100%": { transform: "translateY(-18px)", opacity: "0" },
        },
        "sway": {
          "0%, 100%": { transform: "rotate(-6deg) translateY(0)" },
          "50%": { transform: "rotate(6deg) translateY(-6px)" },
        },
      },
      animation: {
        "float-a": "float-a 6s ease-in-out infinite",
        "float-b": "float-b 7s ease-in-out infinite",
        steam: "steam 2s ease-in-out infinite",
        "rise-in": "rise-in 400ms ease-out both",
        "fade-up": "fade-up 500ms ease-out both",
        "gradient-pan": "gradient-pan 5s ease-in-out infinite",
        "pulse-soft": "pulse-soft 1.8s ease-in-out infinite",
        "steam-path": "steam-path 2.2s ease-in-out infinite",
        sway: "sway 4s ease-in-out infinite",
      },
    },
  },
  plugins: [],
};
