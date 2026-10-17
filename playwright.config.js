import { defineConfig } from "@playwright/test";

export default defineConfig({
  testDir: "./tests/browser",
  timeout: 30000,
  fullyParallel: false,
  workers: 1,
  use: {baseURL: process.env.IQALARM_TEST_URL || "http://127.0.0.1:18123", browserName: "chromium", trace: "retain-on-failure"},
  reporter: "list",
});
