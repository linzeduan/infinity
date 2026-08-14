import { defineConfig } from "@playwright/test";

export default defineConfig({
  testDir: "./e2e",
  timeout: 30_000,
  use: {
    baseURL: "http://127.0.0.1:8765",
    channel: "msedge",
    trace: "retain-on-failure",
  },
  webServer: {
    command: ".\\.venv\\Scripts\\python.exe -m uvicorn backend.main:app --host 127.0.0.1 --port 8765",
    cwd: "..",
    url: "http://127.0.0.1:8765/api/health",
    reuseExistingServer: true,
    timeout: 180_000,
  },
});
