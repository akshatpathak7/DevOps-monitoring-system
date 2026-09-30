import { defineConfig } from "@playwright/test";
export default defineConfig({
  testDir: "./tests",
  timeout: 240000,
  workers: 1,
  use: {
    channel: process.env.BROWSER_CHANNEL,
    baseURL: process.env.BASE_URL || "http://localhost:8080",
    trace: "retain-on-failure",
    screenshot: "only-on-failure",
  },
  reporter: "list",
});
