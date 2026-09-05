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
        surface: "#F7F5EF",
        card: "#FFFFFF",
        border: "#E3DFD3",
        muted: "#F1EFE7",
        "muted-foreground": "#6B7566",
        foreground: "#22291F",
      },
      boxShadow: {
        card: "0 1px 2px 0 rgb(0 0 0 / 0.04), 0 1px 3px 0 rgb(0 0 0 / 0.06)",
      },
    },
  },
  plugins: [],
};
