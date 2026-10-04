import { defineConfig } from "@playwright/test";
export default defineConfig({
  testDir: "tests",
  fullyParallel: false,
  workers: 1,
  retries: 0,
  use: {
    baseURL: "http://127.0.0.1:5194",
    channel: "msedge",
    reducedMotion: "reduce",
    viewport: { width: 1440, height: 1000 },
  },
  reporter: "list",
});
