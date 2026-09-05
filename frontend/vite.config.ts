import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";

export default defineConfig({
  plugins: [react()],
  server: {
    proxy: {
      "/admin": "http://127.0.0.1:8000",
    },
    // /mnt/d/... is a Windows drive mounted into WSL2 — inotify events
    // from edits made on the Windows/host side don't propagate reliably,
    // so HMR silently serves stale content without polling.
    watch: {
      usePolling: true,
    },
  },
  test: {
    environment: "jsdom",
    setupFiles: ["./tests/setup.ts"],
    globals: true,
  },
});
