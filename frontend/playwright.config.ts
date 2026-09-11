import { defineConfig, devices } from '@playwright/test'
import { existsSync } from 'node:fs'
import path from 'node:path'
import { fileURLToPath } from 'node:url'

const __dirname = path.dirname(fileURLToPath(import.meta.url))
const repoRoot = path.join(__dirname, '..')
const venvPython =
  process.platform === 'win32'
    ? path.join(repoRoot, '.venv', 'Scripts', 'python.exe')
    : path.join(repoRoot, '.venv', 'bin', 'python')
const python = existsSync(venvPython) ? venvPython : 'python'

const apiPort = 8010
const uiPort = 5174
const learnApi = `http://127.0.0.1:${apiPort}`
const uiOrigin = `http://127.0.0.1:${uiPort}`
const viteCommand =
  process.platform === 'win32'
    ? `set LEARN_API_URL=${learnApi}&& npm run dev -- --host 127.0.0.1 --port ${uiPort} --strictPort`
    : `LEARN_API_URL=${learnApi} npm run dev -- --host 127.0.0.1 --port ${uiPort} --strictPort`

export default defineConfig({
  testDir: './e2e',
  fullyParallel: false,
  timeout: 60_000,
  use: {
    baseURL: uiOrigin,
    trace: 'on-first-retry',
  },
  projects: [
    {
      name: 'chromium',
      use: {
        ...devices['Desktop Chrome'],
        channel: process.env.PLAYWRIGHT_CHANNEL || 'msedge',
      },
    },
  ],
  webServer: [
    {
      command: `${python} -m uvicorn app.main:app --host 127.0.0.1 --port ${apiPort}`,
      cwd: repoRoot,
      url: `${learnApi}/api/learn/catalog`,
      reuseExistingServer: !process.env.CI,
      timeout: 30_000,
    },
    {
      command: viteCommand,
      url: uiOrigin,
      reuseExistingServer: !process.env.CI,
      timeout: 30_000,
    },
  ],
})
