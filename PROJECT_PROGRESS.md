# OpsPilot AI progress

## Milestone 1 — foundation complete
- [x] Windows runtime and workspace checks; Git initialized
- [x] React + TypeScript + Vite and Python + FastAPI setup
- [x] Approved dependencies installed and locked
- [x] Neon production connection configured; TLS and pooled runtime URL
- [x] Existing frontend proxy, health endpoints, ports, and root env setup preserved

## Milestone 2 — operational MVP implemented
- [x] Inspect actual production database (initially no user tables)
- [x] SQLAlchemy Service, Log, Incident models with UUID keys and foreign keys
- [x] Versioned Alembic migration a64bccfa6f4d; direct URL required for migrations
- [x] Test migration on an isolated Neon branch; apply to production; check schema drift
- [x] Service create/list/read/update/deactivate APIs and frontend forms
- [x] Per-service ingestion credentials, SHA-256 hashes, rotation/revocation
- [x] Workspace-token protection for management APIs
- [x] Structured ingestion, validation, bounded metadata and secret redaction
- [x] Log filtering/search/time ranges and limit/offset pagination
- [x] Automatic incidents: five similar ERROR/CRITICAL events in 120 seconds
- [x] Per-service row locks plus partial unique index prevent duplicate active incidents
- [x] Active event counts and critical escalation; status changes and retained history
- [x] React sidebar, live metric cards, service health list, hourly error chart
- [x] Live logs and incident lists from real APIs; five-second polling, no operational mock data
- [x] Loading, empty, error, retry, and validation states
- [x] Bounded QuickCart simulator: normal, payment timeout, database timeout, exception
- [x] Persisted 30-second simulator cooldown and 120 logs/service/minute ingestion bound
- [x] Verify independent Neon reads and persistence after API restart
- [x] Document setup, APIs, migration workflow, simulator, and tests in docs/MILESTONE_2.md

## Milestone 2 verification evidence (historical)

- Isolated branch: milestone2-verification (br-wandering-feather-a1i5tv6j).
  Auto-expires 2026-11-05 at 18:00 UTC; root production link/env were not switched.
- Actual production tables: alembic_version, services, incidents, logs.
- Alembic current: a64bccfa6f4d (head).
- Alembic check on verification branch: No new upgrade operations detected.
- Complete PostgreSQL suite: 13 passed over pooled Neon connections.
- npm run build: 18 modules transformed; built in 250ms; exit 0.
- npm run lint: exit 0, no warnings.
- Live frontend proxy workflow: authenticated service creation, ingestion,
  simulator, logs, incidents, and dashboard passed.
- QuickCart production demo: six logs, five errors, one detected incident.
- Independent database connection verified all six logs.
- After restarting API: all six logs and the incident remained accessible via
  the frontend proxy; API/database health returned status ok.

## Resolved issues and limits

- Fixed Neon pooled connection rejection of startup statement_timeout option.
  Tests now use pooled URLs for runtime and direct URLs for Alembic.
- Fixed Windows test temp ownership conflict using a fresh workspace temp directory.
- One upstream Starlette/httpx test-client deprecation warning remains; tests pass.
- Browser automation host is unavailable. Build/API/persistence checks passed;
  visual browser interaction was not automatically verified.
- Management authentication is a shared token for a single local demo workspace,
  not user accounts or a multi-tenant permission system.
- DELETE safely deactivates services; it does not erase incident/log history.
- Pattern-based redaction cannot detect every possible secret: producers must
  send sanitized data. No raw production secrets should be ingested.
- Simulator shares the ingestion validation/storage/detection pipeline server-side;
  it does not make loopback HTTP calls or run an unlimited background generator.

## Next milestones — not started

3. Incident summary/details implemented; assignment, investigation notes, timeline and optional real-time transport remain planned.
4. Gemini investigation and explicit deterministic demo implemented below; additional providers and reports remain planned.
5. Cloudflare Pages / Render deployment configuration prepared below; deployment and browser acceptance remain manual.


## AI investigation increment - implemented 2026-11-05

- [x] Inspected and preserved operational MVP; no rebuild or database replacement.
- [x] Official google-genai Python SDK (2.34.0), backend-only GEMINI_API_KEY,
  configurable gemini-2.5-flash-lite model with documented free-tier eligibility.
- [x] Modular provider protocol and Gemini adapter; Codex is development-only.
  Clients need no Codex or ChatGPT accounts. No paid/provider fallback.
- [x] Authenticated POST /incidents/{id}/analysis and GET /ai/quota.
- [x] PostgreSQL evidence bounded to 20 matching incident logs; send only allowlisted
  categories, severity and log UUIDs. No raw text, personal data or metadata sent.
- [x] Bounded Pydantic output, validated evidence references, no model tools,
  safe timeout/rate-limit/provider/invalid-response handling, retries disabled.
- [x] Explicit operator enablement plus request consent; external calls off by default.
- [x] Durable workspace daily investigation/global analysis request quotas, shared
  cooldown, atomic reservations and evidence/model-version cache; no restart bypass.
- [x] Deterministic explicitly labeled simulated analysis, available without API key.
- [x] Incident details UI: Analyze with AI, consent, loading, hypotheses, evidence,
  checks, uncertainty, quota feedback and separate simulated button.
- [x] Single demo workspace restriction retained; no multi-tenant claims.
- [x] Analysis request body bounded to 1024 bytes, no arbitrary prompt inputs.
- [x] Additive migration b75_ai_analysis verified on isolated Neon branch, then
  applied to application database; Alembic check reports no schema drift.
- [x] Application read-only smoke checks: database health, dashboard, incidents and
  AI quota all returned 200 after migration. No operational rows rewritten.
- [x] Frontend production build and lint pass.
- [x] Offline provider tests cover valid/invalid output, timeouts, missing/auth inputs,
  provider 429/503, bounded input, deterministic demo and sensitive-text projection.
- [x] PostgreSQL endpoint tests mock Gemini and cover missing key/consent, caching,
  changed evidence, concurrent quota enforcement, UTC rollover, invalid evidence,
  provider rate limits and dashboard operation after limits/errors.
- [ ] One live Gemini API smoke test: intentionally NOT run. User must configure
  key and explicitly approve the request first.
- [ ] Free-host deployment, multi-tenant identity/isolation, production privacy/audit
  controls, additional adapters, cache cleanup and browser visual verification.

Configuration, quota semantics, API contract, free-tier/privacy limitations and
implemented/planned scope: [AI investigation guide](docs/AI_INVESTIGATION.md).
The shared token grants access to every service in this demo workspace. Do not
onboard independent clients or confidential production data yet. Free-tier API
availability is provider-controlled; app limits cannot verify a key's billing tier.


### Final AI increment verification

- Complete backend suite: **29 passed**, including PostgreSQL integration tests on
  the isolated branch and mocked Gemini responses; no real provider calls.
- One existing upstream Starlette/httpx test-client deprecation warning remains.
- `npm run build`: passed (19 modules); `npm run lint`: passed.
- Isolated and application database Alembic checks: no schema drift.
- Live browser layout verification has not been performed.


## Interview demonstration preparation - 2026-11-05

### Implemented

- [x] Re-inspected actual code and progress; extended the existing app, no rebuild.
- [x] Fixed payment/database timeout classification for messages saying "timed out"
  without an error_type. Added regression cases and bumped evidence projection
  cache version so prior classifications are not reused.
- [x] Clickable hypothesis evidence UUIDs open authenticated stored-log details.
  Endpoint checks service, signature, severity and incident interval; logs from
  another incident/service return 404. Loading/error/close and focus states added.
- [x] Existing QuickCart simulator still shares ingestion and threshold detection.
- [x] Added simulator -> stored logs -> incident -> independent PostgreSQL session
  -> dashboard -> simulated analysis -> evidence endpoint integration coverage.
- [x] Strengthened test isolation: reject the same application Neon endpoint even
  when URLs differ by pooling, credentials or database name. All test mutations
  targeted the separate ignored verification endpoint; no production data changed.
- [x] Added safe localhost-only test server and reproducible HTTP verification script.
  API port 8010, Vite port 5174, Gemini forcibly disabled in that test server.
- [x] HTTP workflow through the actual Vite proxy passed: five errors persisted,
  one incident, payment_timeout category, explicit simulated label and stored log.
- [x] Restarted that test API process; HTTP reads and a fresh independent database
  session still found the same five logs and incident. Dashboard remained available.
- [x] Production public HTTPS API URL through VITE_API_BASE_URL, used by both
  health and authenticated requests; original local /api proxy retained.
- [x] Exact-origin HTTPS CORS validation; production preflight accepted configured
  Pages origin and rejected an unrelated origin. Local HTTP development preserved.
- [x] Prepared root render.yaml, backend/frontend production env examples,
  Cloudflare static headers and docs/DEPLOYMENT.md with manual checklist.
  No Render/Cloudflare resources created; nothing deployed, committed or pushed.
- [x] Secret env/credential directories excluded from Git; placeholder examples
  remain includable. Candidate Git files scanned against configured credential
  values with no matches. Temporary verification record IDs are ignored.

### Verification and limitations

- Complete isolated-Neon backend regression: 37 tests passed in the final run (81.18 seconds).
- Frontend build and lint passed. Additional production-URL build confirmed the
  HTTPS Render URL was embedded and Cloudflare headers copied; local build restored.
- No database migrations needed or run for this increment. Current code migration
  head remains b75_ai_analysis; earlier milestone schema claims above are historical.
- Gemini configuration check: key absent, external analysis disabled, configured
  model gemini-2.5-flash-lite. Simulated path verified; no real Gemini request made.
- The key supplied in chat was not saved or used. Operator must revoke it and
  configure a replacement privately before any approved real-provider test.
- Browser verification NOT completed: browser inventory reported the access host
  unavailable; native Chrome interaction then stopped because it could not reliably
  identify the current browser URL. No alternate automation bypass attempted.
  Manual browser/keyboard/mobile acceptance checklist is in docs/DEPLOYMENT.md.
- One existing upstream Starlette/httpx TestClient deprecation warning remains.
- Public URL is still protected by a shared token for ONE synthetic-data workspace.
  All token holders can manage its records; no multi-tenant or read-only public role.
- Render cold starts, provider quotas and free hosting/database resource ceilings
  remain external limits. Cache/log retention cleanup, notes/assignment and
  individual accounts/tenant isolation remain planned.

Full operator checklist and deployment steps: [Deployment guide](docs/DEPLOYMENT.md).

- Temporary isolated verification servers were stopped after checks; ordinary
  development servers were not changed. No deployment or real Gemini call occurred.

## Phase 1 Python monitoring SDK - implemented 2026-11-06

- [x] Separate installable `opspilot-sdk` package with `opspilot_sdk` imports;
  API origin/service UUID/ingestion key configuration and explicit env loading.
- [x] Structured ERROR/CRITICAL events and privacy-preserving exception reports.
- [x] Optional pure ASGI FastAPI middleware: route templates, same exception
  re-raised, no request body/headers/query collection or raw exception messages.
- [x] Pre-queue redaction, bounded metadata, short transport timeouts, finite
  daemon queue, bounded connect-only retries, delivery counters and bounded close.
- [x] HTTPS for remote origins, verified TLS, no redirects or implicit proxies.
- [x] Independent external FastAPI example, install guide and five-error walkthrough
  in `opspilot-sdk/README.md`.
- [x] 24 SDK tests passed: contract, privacy, overload, outages, retry bounds,
  exception preservation, handled exceptions and example lifespan behavior.
- [x] Local wheel built and installed to ignored `.sdk-artifacts/installed`.
- [x] SDK -> existing ingestion route -> isolated PostgreSQL verified: no incident
  for the first four matching errors; event five creates one Open incident with
  five committed logs, verified through an independent database session.
- [x] Actual localhost HTTP test using the INSTALLED wheel: five external FastAPI
  500 responses -> SDK -> API -> five stored logs and one Open incident. Both
  temporary servers stopped. Reproduce with `backend/scripts/verify_sdk.py`.
- [x] Existing backend regression: 37 tests passed initially; the remaining
  configuration test had a Windows temporary-directory permission setup error
  and passed when rerun with a fresh workspace basetemp (38 tests passed overall).
  Existing upstream TestClient deprecation warning remains.
- [x] No existing backend/frontend runtime code, migrations or production records
  changed. No real Gemini calls, deployment, SDK publication or automatic fixes.

The expired verification branch was replaced with schema-only
`sdk-phase1-verification` (`br-curly-pond-a18gat0s`), containing synthetic test
records only, expiring 2026-11-07 18:00 UTC. Only ignored `backend/.env.test.local`
was updated; application env files and branch selection were preserved.
The SDK remains best-effort: full queues/outages/process exit can lose events,
and pattern redaction cannot recognize every sensitive value. No tenant isolation,
automatic fixes, remote execution or unrestricted log collection was introduced.


## Finalization review ? 7 November 2026

Scope frozen at the existing interview MVP. All 62 backend/SDK tests passed,
including isolated Neon tests. Frontend build/lint, application database health,
Alembic revision/drift, actual external SDK HTTP ingestion and restart persistence
passed. Browser automation was blocked by URL identification; manual acceptance
remains open. No live Gemini, deployment, Git commit/push or paid service.
See [current final report and exact release steps](docs/FINALIZATION.md).
