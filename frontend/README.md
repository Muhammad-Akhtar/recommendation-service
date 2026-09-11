# Learning UI

Vite + React app that reads the ML plan from FastAPI (`/api/learn/*`).

```text
npm install
npm run dev          # http://localhost:5173/learn  (proxies /api to :8000)
npm run test:e2e     # Playwright in e2e/ — does not run pytest
```

API must be up for `npm run dev` (or Playwright starts it). Isolated Docker:

```text
docker compose -f docker-compose.learn.yml up --build
```

Then open http://localhost:3000/learn
