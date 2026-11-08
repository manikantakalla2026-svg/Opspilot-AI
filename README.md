# OpsPilot AI

**Finalization status (7 November 2026):** build/lint and all 62 backend/SDK
tests passed, including isolated Neon integration. No deployment, Git push or
real Gemini call was performed. Browser acceptance remains manual. See the
[final report, deployment steps and external-app checklist](docs/FINALIZATION.md)
for current results; older milestone counts below are historical.

Connect an external Python application using the separate local-only
[opspilot-sdk package and setup guide](opspilot-sdk/README.md). It includes
structured errors, exception reporting, optional FastAPI middleware, redaction,
and a bounded background sender. The independent example is in
`examples/external-fastapi`. Nothing is published or deployed.

A local full-stack incident-management MVP built with React, TypeScript, Vite,
FastAPI, SQLAlchemy, Alembic, and Neon PostgreSQL.

Milestone 2 includes service registration/management, authenticated structured
log ingestion, automatic incident detection, database-backed dashboard and live
log/incident views, and a bounded QuickCart payment-service simulator.

## Start on Windows

From this project root, open two VS Code PowerShell terminals:

```powershell
npm run dev:backend
```

```powershell
npm run dev
```

Open http://127.0.0.1:5173. Enter WORKSPACE_TOKEN from local backend/.env, without
surrounding quotes. The shared token protects this single demo workspace.
Use Sign out to clear it from this tab's session storage.

- API docs: http://127.0.0.1:8000/docs
- API liveness: http://127.0.0.1:8000/health
- Database health: http://127.0.0.1:8000/health/db

Both servers bind only to localhost. Ctrl+C stops each server. Do not start a
second copy when its port is occupied. Use python instead of py on this machine.

## Configuration

Root .env.local contains Neon-generated DATABASE_URL, DATABASE_URL_UNPOOLED,
and NEON_BRANCH. These values remain backend-only. FastAPI loads root .env,
root .env.local, then backend/.env; process environment has highest precedence.

The database/schema is already configured. For a fresh clone, install dependencies:

```powershell
npm ci
npm --prefix frontend ci
python -m venv backend/.venv
backend/.venv/Scripts/python.exe -m pip install -r backend/requirements.txt
neon login
neon deploy
```

Copy backend/.env.example to backend/.env and set WORKSPACE_TOKEN to a long random
secret. For example generate one with python -c "import secrets; print(secrets.token_urlsafe(32))".
Never commit .env files, put database keys in VITE_ variables, or paste them in chat.

Apply migrations using the direct URL (never the pooler):

```powershell
cd backend
.venv/Scripts/python.exe -m alembic upgrade head
```

No Docker or local PostgreSQL is needed. Neon deployment provisions database
infrastructure; the React frontend and FastAPI backend still run locally.

## Demo and verification

The database contains a labeled QuickCart Payments demo service with six real
logs and one automatically detected payment timeout incident from verification.
Register another service or use the simulator to generate additional events.
Five matching failures in two minutes open an incident; resolve it from Incidents.
Simulations stop automatically and have a per-service 30-second cooldown.

```powershell
npm run build
npm run lint
cd backend
.venv/Scripts/python.exe -m pytest -q
```

The default test run skips opt-in real-database tests. All 13 tests were also run
against a separate Neon verification branch, including concurrent ingestion and
persistence checks. One upstream test-client deprecation warning remains.

See [Milestone 2 guide](docs/MILESTONE_2.md) for APIs, ingestion examples,
security bounds, and integration-test instructions. See
[project progress](PROJECT_PROGRESS.md) for completed work and remaining milestones.


## Gemini incident investigation

Incident details now include **Analyze with AI** and **Run simulated analysis**.
The deployed AI runtime uses the official Google GenAI Python SDK. Clients do not
need Codex or ChatGPT accounts. The MVP remains one shared demo workspace.

Configure backend-only `GEMINI_API_KEY` and set `AI_EXTERNAL_ENABLED=true` after
reviewing the privacy requirements. External calls also require incident-level
consent. Leave it disabled for deterministic simulations without API access.
Default daily limits are 10 real investigations and 50 total analysis requests;
monitoring continues when AI is unavailable. Never enable provider billing if you
require strictly free API use; the app cannot detect the key's billing tier.

See [AI investigation setup and limitations](docs/AI_INVESTIGATION.md) for settings,
additive migrations, security, free-tier references, tests and planned work.
No live Gemini smoke test is run until the operator configures a key and approves it.


## Interview demo and deployment preparation

See [Cloudflare Pages + Render + Neon checklist](docs/DEPLOYMENT.md). Configuration
is prepared; no deployment has been performed. Backend settings are illustrated in
`backend/.env.production.example`, frontend settings in
`frontend/.env.production.example`; all example credentials are placeholders.

AI hypothesis evidence IDs now open the corresponding stored incident log. Timeout
messages such as "Payment gateway timed out" are classified correctly even without
an error_type. No new migration is required by these changes.

The safe localhost HTTP verification scripts target only the independent Neon
verification database. Browser acceptance and a rotated-key, explicitly approved
real Gemini smoke test remain manual pending steps.
