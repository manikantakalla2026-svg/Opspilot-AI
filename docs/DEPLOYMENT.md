# Interview demo deployment checklist (prepared, NOT deployed)

Update 8 November 2026: the operator reports successful local real Gemini
investigation using the saved `gemini-3.5-flash-lite` configuration. Earlier
configuration/test observations below are historical. This inspection made no
Gemini requests. The Blueprint and production example now use that model.
`AI_EXTERNAL_ENABLED=false` remains the initial Blueprint safety default; for
real investigation, deliberately set it to `true` and configure `GEMINI_API_KEY`
in Render secrets during the backend configuration step. Never commit the key.

Deploy in separate steps: reviewed local commit, GitHub setup/push after approval,
Neon target/migration review, Render configuration/deploy after approval, then
Pages configuration/deploy after approval and HTTPS verification. The final
Render/Pages URLs do not exist in this checkout yet; use actual assigned URLs
when configuring the API origin and CORS, rather than guessing them.

Current verification and release gates are in [FINALIZATION.md](FINALIZATION.md)
(7 November 2026). Its test counts and runtime observations supersede older notes
below. No features beyond the existing interview MVP are required for closeout.

Architecture: Cloudflare Pages serves the React/Vite static build over HTTPS.
The browser calls the Render FastAPI HTTPS origin directly, without `/api`.
Render connects to the existing Neon PostgreSQL pooled endpoint with TLS.
Codex is a development tool only; visitors need no ChatGPT or Codex account.
The shared workspace token remains required. This is one synthetic-data demo
workspace, not a multi-client production service.

## 1. Before publishing

- Rotate the Gemini key exposed in chat. Do not reuse it or paste replacements in
  chat. Set a replacement only in local backend/.env or Render's secret settings.
- Use synthetic QuickCart data and a dedicated Neon demo branch/database. Never
  attach confidential production logs to a public interview demonstration.
- Generate a fresh WORKSPACE_TOKEN. Share it privately only with intended demo
  participants; token holders can manage all services and records in this workspace.
- Inspect `git status` and staged diffs before committing. `.env`, `.env.local`,
  test URLs, production env files, private keys and cloud credential directories are
  ignored. Only placeholder `.env*.example` files should be committed.
- No files were committed or pushed by this change. Commit the application and
  reviewed config, then push to your Git provider yourself.
- Keep a separate Neon test endpoint for RUN_NEON_TESTS=1. Tests refuse the same
  normalized Neon endpoint, including pooled/direct aliases. Test files create
  synthetic records and reset AI quota/cache tables ONLY on that test endpoint.

## 2. Neon database and migrations (manual)

Keep your existing project, ORM and Alembic history. No new schema migration is
required by this increment. The expected revision remains `b75_ai_analysis`.

For a fresh DEMO branch, copy its pooled URL into Render as DATABASE_URL with
`sslmode=require` (or certificate-verifying SSL mode). Keep its direct URL locally
for migrations as DATABASE_URL_UNPOOLED. Check that both belong to the SAME intended
demo branch, not the verification branch or a confidential production branch.

From `backend`, with that demo branch's direct URL configured locally:

```powershell
.venv/Scripts/python.exe -m alembic current
.venv/Scripts/python.exe -m alembic upgrade head
.venv/Scripts/python.exe -m alembic check
```

Run migrations once as a deliberate operator step before opening the demo. They
are deliberately absent from Render's build/start command; a build never changes
the database. The running API does not need DATABASE_URL_UNPOOLED.
On Render Free, shell access, one-off jobs and pre-deploy commands are unavailable.
Run the reviewed migration commands from this local checkout using the intended
Neon demo branch's direct URL, only after explicit database-change approval.
Do not upgrade the Render plan to obtain migration access. See
[free limitations](https://render.com/docs/free) and
[pre-deploy availability](https://render.com/docs/deploys#pre-deploy-command).

## 3. Render FastAPI backend (manual; do not click deploy until ready)

Use the repository-root `render.yaml` Blueprint, or create a Python Web Service:

| Setting | Value |
| --- | --- |
| Plan | Free |
| Root directory | `backend` |
| Python version | `3.13.9` |
| Build command | `pip install -r requirements.txt` |
| Start command | `uvicorn app.main:app --host 0.0.0.0 --port $PORT --proxy-headers` |
| Health check | `/health` |
| Automatic deploy | Off |

Render terminates HTTPS; the application binds its assigned PORT. Keep the public
Render URL as `https://YOUR-SERVICE.onrender.com`. `/health` checks process health;
check `/health/db` separately to confirm the actual database connection.

Copy variables from `backend/.env.production.example` into Render's environment
settings, replacing all placeholders. Minimum required:

- DATABASE_URL: pooled Neon DEMO URL with TLS.
- WORKSPACE_TOKEN: a strong random secret.
- FRONTEND_ORIGINS: JSON array of exact Pages HTTPS origins, e.g.
  `["https://YOUR-PROJECT.pages.dev"]`. No trailing slash or `/api` path.
- AI_EXTERNAL_ENABLED=false for the reliable simulated interview path.
- GEMINI_MODEL=gemini-3.5-flash-lite and the documented AI daily limits.

No wildcard CORS is accepted. When adding a custom Pages domain, list that exact
origin too. Preview origins are not automatically trusted: explicitly add only
ones you intend to use, or use the production Pages URL for the interview.
CORS controls browser access; the workspace token still authenticates every
management request. Do not remove authentication to solve a CORS problem.

## 4. Cloudflare Pages frontend (manual)

Create a Pages project connected to your repository, using:

| Setting | Value |
| --- | --- |
| Root directory | `frontend` |
| Framework | React / Vite |
| Build command | `npm run build` |
| Output directory | `dist` |
| Build variable | `VITE_API_BASE_URL=https://YOUR-SERVICE.onrender.com` |
| Node build variable | `NODE_VERSION=22` |

Use the frontend lockfile (`frontend/package-lock.json`) when installing packages.
VITE_API_BASE_URL is public and embedded at BUILD time. Changing it requires a
new frontend build. It must use HTTPS, have no credentials/query/fragment and no
`/api` suffix for this backend. Both health checks and authenticated API requests
use it. Leaving it unset uses the LOCAL `/api` Vite proxy, which does not exist on
Pages and will not connect to Render. Never put a token, API key or database URL
in a VITE_ variable or Cloudflare frontend build environment.

`frontend/public/_headers` is copied into dist for Pages response headers. Pages
provides the SPA fallback when no top-level 404.html is present; no API rewrite
or Pages Function is needed. The Render API serves `/incidents`, `/logs`, etc.,
not `/api/incidents`. Browser requests go directly to Render over HTTPS.

If the final Pages project URL differs from the planned origin, update Render's
FRONTEND_ORIGINS accordingly, save the environment changes and deploy Render with
the new configuration. A restart alone can reuse the previous deployed environment.
Do not use `*`.

## 5. Gemini versus simulation

At verification: no GEMINI_API_KEY configured, AI_EXTERNAL_ENABLED=false,
model `gemini-2.5-flash-lite`. No real Gemini API request was made. The key supplied
in chat was not saved or used. Rotate it before configuring a replacement.

For the interview, **Run simulated analysis** is deterministic, clearly labeled
as not generated by Gemini, and works without an external key or consent checkbox.
It still consumes the application's global analysis request budget. If rehearsals
exhaust that budget, wait for the documented UTC reset or deliberately configure
an appropriate limit before the interview; do not assume every error is an AI issue.

To enable real Gemini later, configure a rotated GEMINI_API_KEY backend-only and
AI_EXTERNAL_ENABLED=true, restart the backend, then explicitly approve ONE live
smoke test. Supplying a key alone is not approval for that test. Real requests also
require the UI consent checkbox. Free-tier API availability/quotas are controlled
by Google; confirm your project has no billing and the selected model is still
eligible. No paid fallback, provider switch or automatic retry is implemented.
Only categories, severities and log evidence IDs leave the backend, not stored
messages/metadata. Consequently AI can suggest hypotheses, not prove root causes.

## 6. Browser acceptance checklist (manual, still pending)

Browser automation stopped because the Windows browser URL could not be reliably
identified. API/build tests do not substitute for visually completing this list.

- Start both existing development servers in separate terminals, or use the
  deployed Pages URL after deployment is deliberately authorized.
- Open the app. Confirm API/database health. Enter the workspace token.
- Register a synthetic service named QuickCart Interview and retain its ingestion
  key privately if you will demonstrate external ingestion.
- Open QuickCart simulator, select that service and run Payment gateway timeout.
- Confirm five stored error logs, one incident, dashboard counts and unhealthy
  service status. Simulator uses the same internal ingestion/detection pipeline.
- Open the incident, choose Run simulated analysis and confirm its source label.
- Click a supporting log UUID. Confirm the stored message, severity, timestamp,
  service and sanitized metadata appear. Close the log, then close the incident.
- Refresh the page and confirm persisted logs/incidents remain; reconnect with
  the token if needed. Show the status change to Investigating/Resolved.
- Test a narrow/mobile browser width and keyboard navigation through evidence.
- Check browser Network/Console for mixed content, CORS and failed requests.
- Confirm no Gemini key/database URL is visible in browser assets or requests.

For SAFE local verification on a test DB only, the provided scripts use ports
8010/5174 and a non-production test token. Keep the ignored backend/.env.test.local
pointing to an independent Neon endpoint:

```powershell
# Terminal 1, project root
backend/.venv/Scripts/python.exe backend/scripts/demo_test_server.py
# Terminal 2, project root
$env:DEV_API_TARGET='http://127.0.0.1:8010'
npm --prefix frontend run dev -- --port 5174
# Terminal 3, project root: HTTP and independent database assertions
backend/.venv/Scripts/python.exe backend/scripts/verify_interview.py
# After restarting ONLY the isolated test API:
backend/.venv/Scripts/python.exe backend/scripts/verify_interview.py --resume
```

Open http://127.0.0.1:5174 and use `opspilot-browser-test` ONLY for that isolated
server. The helper disables Gemini regardless of ordinary local settings.
Do not use that test token on the public Render service.

## 7. Free-tier interview limitations

Render Free services sleep after 15 minutes without inbound traffic; startup can
be delayed. Open the app and wait for both health checks before the interview.
If the first call times out, retry after the service wakes. Do not promise always-on
availability. Neon and Google have independent resource/quota limits. Dashboard
polling every five seconds keeps making requests while the visible app is open;
close unused tabs to avoid unnecessary database/hosting usage. No paid plan,
service, deployment or keep-alive scheduler was enabled by this change.

Closeout requires browser/device acceptance and deployed HTTPS verification.
Real Gemini verification requires separate explicit approval. Keep the scope at
one shared synthetic-data interview workspace.

Official deployment references checked for this preparation:
- https://render.com/docs/deploy-fastapi
- https://render.com/docs/blueprint-spec
- https://render.com/docs/free
- https://developers.cloudflare.com/pages/configuration/build-configuration/
- https://developers.cloudflare.com/pages/configuration/serving-pages/
- https://ai.google.dev/gemini-api/docs/pricing
