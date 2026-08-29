import { defineConfig, loadEnv } from "vite";
import react from "@vitejs/plugin-react";

export default defineConfig(({ mode }) => {
  const environment = loadEnv(mode, ".", "");
  const shellEnvironment = (
    globalThis as typeof globalThis & {
      process?: { env?: Record<string, string | undefined> };
    }
  ).process?.env;
  return {
    plugins: [react()],
    server: {
      port: 5173,
      proxy: {
        "/api":
          shellEnvironment?.AISHIELD_API_PROXY ??
          environment.AISHIELD_API_PROXY ??
          "http://localhost:8000",
      },
    },
  };
});
