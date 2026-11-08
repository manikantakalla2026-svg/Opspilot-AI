# Incident AI investigation

OpsPilot uses Codex for development only. The deployed runtime is FastAPI with
Google's official `google-genai` SDK. Clients need only the demo workspace token;
they need no Codex, ChatGPT, or Google account. The operator supplies the Gemini key.

## Setup

1. Install `backend/requirements.txt` in the existing backend virtual environment.
2. Apply the additive migration with the existing direct migration connection:
   from `backend`, run `.venv/Scripts/python.exe -m alembic upgrade head`.
   Revision `b75_ai_analysis` adds only `ai_usage` and `ai_analyses`.
   It has been tested on the existing isolated Neon verification branch.
3. Set backend environment variables (or ignored `backend/.env`):

```dotenv
GEMINI_API_KEY=your-google-ai-studio-key
GEMINI_MODEL=gemini-2.5-flash-lite
AI_EXTERNAL_ENABLED=false
AI_DAILY_INVESTIGATION_LIMIT=10
AI_GLOBAL_DAILY_REQUEST_LIMIT=50
AI_REQUEST_COOLDOWN_SECONDS=5
AI_TIMEOUT_SECONDS=12
```

Restart the backend after changes. Never put the key in frontend files, a `VITE_`
variable, source control, or a browser request. Keep external analysis disabled
until the operator has reviewed Google's current terms, free eligibility and
privacy policy. Set `AI_EXTERNAL_ENABLED=true` to enable it. Each real analysis
also requires explicit consent in incident details. There is no startup API call.

Open an incident's Details / Analyze with AI button. Simulated analysis works
without a key or external enablement, is deterministic and labeled as simulated.
Gemini errors never trigger automatic simulation or another provider.

## Privacy and authorization

This MVP is ONE demo workspace with a shared administrative token. Every token
holder can see all its services. Do not onboard independent clients or confidential
production workloads until individual authentication, tenant ownership filters,
authorization, audit and privacy controls are implemented. Deploy behind HTTPS.

The outbound projection intentionally excludes all raw log messages, metadata,
service names, titles, timestamps, paths, credentials, user identifiers and network
addresses. Local classification produces only a fixed error category, severity and
opaque log UUID. At most 20 ERROR/CRITICAL logs matching the incident's service,
signature and observed interval are sent. This is conservative data minimization;
it reduces context and therefore the precision of possible root causes. Evidence
IDs in results refer to stored logs; categories are symptoms, not proof of causes.
Never ingest confidential data expecting pattern redaction to remove everything.
Free-tier Google content may be used to improve Google's products. Use synthetic
demo logs; categorical projection and consent do not replace a production privacy
assessment. No raw logs or free-form prompt text can be submitted to this endpoint.

Provider output is Pydantic-validated with bounded strings/lists and references
checked against this incident. Log content is untrusted and never included verbatim
in prompts. The model has no tools or ability to execute recommended checks.
Responses render as escaped text in React. Analysis bodies are limited to 1024 bytes.

## Usage and free-tier limits

- PostgreSQL UPSERT and row locks serialize shared workspace reservations.
- Global daily limit counts analysis POST requests including cache hits, demo,
  consent/key failures and provider failures. Cooldown/global rejections do not
  increase the count. Unknown incident IDs do not consume AI quota.
- Investigation allowance counts real provider attempts on cache misses, including
  failures. The reservation commits before any provider call and survives restarts.
- A shared persisted cooldown prevents parallel requests bypassing limits.
- Identical incident evidence, model and projection version reuse successful results.
  Simulation and real cache entries are separate. Evidence changes invalidate cache.
- In-flight/failed fingerprints block repeats for 60 seconds. Afterward retries
  consume another investigation; crashes never refund the reserved quota.
- Limits reset at 00:00 UTC, independently of Google's quota reset schedule.
- Monitoring, ingestion and dashboard endpoints do not use the AI budget.
- No automatic retries, tools, grounding, paid fallback, or provider/model switching.

The selected model has free input/output pricing at verification time (2026-11-05).
Google quotas depend on project, region and account and can change. Check AI Studio
for the actual RPM/TPM/RPD allowance; app limits do not guarantee provider capacity.
Use a free-tier Google project without billing enabled to avoid charges. The app
cannot verify a key's billing tier; enabling billing can make requests billable.
Google also controls model retirement/routing, so review deprecation notices before
continued use; the application does not select a replacement automatically.
Free hosting and database resources also have independent limits. Hosting is not
deployed by this change; retain the existing local setup until deployment work.

Official references:
- https://ai.google.dev/gemini-api/docs/pricing
- https://ai.google.dev/gemini-api/docs/rate-limits
- https://ai.google.dev/gemini-api/terms
- https://googleapis.github.io/python-genai/
- https://ai.google.dev/gemini-api/docs/structured-output

## APIs and tests

`GET /ai/quota` and `POST /incidents/{UUID}/analysis` require
`X-Workspace-Token`. POST body: `{"simulated":false,"consent":true}`.
Responses include source/model, simulated/cached flags, bounded hypotheses,
evidence references, recommended checks, confidence, uncertainty and quota.

Run `backend/.venv/Scripts/python.exe -m pytest backend/tests -q` for offline tests.
Set `RUN_NEON_TESTS=1` only with the existing isolated `backend/.env.test.local`
configured and migrated to run all PostgreSQL tests. Never point it at production.
Run `npm run build` and `npm run lint` for frontend validation.

No real Gemini request has been made. Configure the key and give explicit approval
before one live smoke test. Do not run that test automatically in CI.

Implemented: modular Gemini adapter and provider contract, validated investigation
endpoint, conservative projection, durable quotas/cache, explicit deterministic demo,
incident details UI, error/loading/quota states and automated tests.
Planned: multi-tenant accounts, production privacy review/audit controls, notes and
assignment, additional provider adapters, cache retention cleanup, free-host deployment
and browser visual QA. The provider protocol is ready for other adapters; no OpenAI
adapter, Codex runtime or paid fallback is installed.
