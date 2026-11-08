# OpsPilot AI finalization — 7 November 2026

Status update, 8 November 2026: the operator reports local real Gemini
investigation is working. The saved model is `gemini-3.5-flash-lite`; the deployment
templates now match. Earlier absent-key/disabled-AI notes, test counts and release
gates in this report describe their dated verification runs, not a new live test.
Follow [DEPLOYMENT.md](DEPLOYMENT.md) for the current publishing sequence.
This preparation did not push, deploy, provision resources or change a database.

Code is ready for the final manual acceptance pass and operator deployment.
The project is NOT yet publicly deployed or fully signed off. No new modules,
paid services, Git commits/pushes, or live Gemini requests were made.
This report supersedes historical test counts in README and PROJECT_PROGRESS.

## UI review and fixes

Reviewed every React source component: App (workspace access, Overview, Services,
Live logs, Incidents, QuickCart), IncidentAnalysis (details, AI and evidence),
shared API client, global styles and responsive styles. Preserved the existing
dark layout, spacing, tables, badges, forms and mobile breakpoints.

Final changes:
- Ignore stale dashboard/list responses after filter/session changes and sign-out.
- Show connection attention and refresh failure instead of a healthy indicator
  when refresh fails; keep the last successful update timestamp visible.
- Explain API/network timeouts, including the hosting cold-start case.
- Add keyboard skip navigation to workspace content and respect reduced motion
  when opening investigation/evidence panels.
- Reject deployed API URLs with path suffixes such as `/api`; use the HTTPS origin.
- Repair the SDK HTTP verification harness: intentional unhandled 500 responses
  close Uvicorn connections, so use fresh connections without retrying events.

Visual appearance, keyboard flow and mobile acceptance remain MANUAL, not passed.
Windows Computer Use stopped because it could not reliably identify the browser
URL. No alternative browser-control bypass was attempted.

## Verification results

| Check | Result |
| --- | --- |
| Frontend TypeScript/Vite build | Passed |
| Frontend oxlint | Passed, no diagnostics in final run |
| Offline backend + SDK regression | 46 passed, 16 opt-in DB tests skipped |
| Complete isolated-Neon regression | 62 passed, zero skipped/failed |
| Application `/health` and `/health/db` | Both 200; database check is read-only |
| Registration, auth, key rotation, deactivation | Passed integration tests |
| SDK events 1–4 / event 5 | No incident / one persisted incident |
| Concurrent detection, status updates, filters, redaction | Passed |
| Simulator, simulated label, evidence HTTP retrieval via Vite | Passed |
| Same logs/incident after test API restart | Passed; independently read from PostgreSQL |
| Installed SDK + separate external FastAPI over actual HTTP | Passed: five 500s, five delivered logs, one Open incident |
| Gemini provider contracts/errors/quotas/cache | Passed using mocks only |
| Live Gemini / public deployed HTTPS end-to-end | Skipped, not authorized / not deployed |
| Alembic current + schema drift check | `b75_ai_analysis (head)`; no new upgrade operations |
| HTTPS API build + Pages `_headers` output | Passed with placeholder HTTPS origin, no deployment |
| Git exclusions and configured-secret scan | Env files ignored; no configured-secret matches in 81 candidate files |

Initial DB test attempt failed under restricted network access (16 failures,
46 passes). The network-enabled isolated run passed all 62. Initial SDK HTTP
smoke failed with WinError 10054; the harness fix above passed on rerun.
Warnings: upstream Starlette/httpx TestClient deprecation; Windows denied pytest
cache writing in the network-enabled run. Neither failed assertions.

Only synthetic integration data was added to the separate test endpoint.
AI integration tests reset that test endpoint's AI cache/quota tables; application
data was not deleted. No migrations were applied in this review.

## Gemini configuration and readiness

Observed locally: key absent, external AI disabled, model `gemini-2.5-flash-lite`.
Integration is implemented, but actual key/model access and live output remain
UNVERIFIED. Confirm current model access and free eligibility in your Google
project before selecting a model; configuration alone does not prove readiness.
No authenticated model-list or generate request was made.

Set these backend-only in `backend/.env` or Render secret settings:

```dotenv
GEMINI_API_KEY=your-private-replacement-key
GEMINI_MODEL=gemini-2.5-flash-lite
AI_EXTERNAL_ENABLED=false
AI_DAILY_INVESTIGATION_LIMIT=10
AI_GLOBAL_DAILY_REQUEST_LIMIT=50
AI_REQUEST_COOLDOWN_SECONDS=5
AI_TIMEOUT_SECONDS=12
```

The key and explicit enablement are required for real calls; model and numeric
settings have the defaults shown. Keep enablement false until you explicitly
approve one live test, then enable, restart, open one synthetic incident, check
consent and click Analyze with Gemini once. Inspect the result and usage before
any further call. App limits cannot guarantee that a provider project is free.

Simulation calls the local deterministic provider. Responses set
`source="Simulated analysis"`, `simulated=true`, `model=null`; the UI also says
"not generated by Gemini". Gemini has a distinct cache fingerprint and source.
Provider failures return errors; they do not silently return simulated output.
Only categorical evidence, severities and evidence UUIDs go to Google.

## Remaining release gates

1. Complete the manual browser checklist below; browser acceptance is unverified.
2. Rotate the isolated test database credential: the first failing pytest run
   printed a driver traceback containing connection arguments. Do not reuse that
   credential for the public demo. Keep replacements out of chat and Git.
3. Existing deployment notes record an earlier exposed Gemini key; revoke it
   before configuring a replacement. No Gemini key is currently configured here.
4. Choose final Render/Pages URLs, configure private production settings and a
   strong workspace token, then deploy manually when ready. No public HTTPS
   cross-origin/SDK smoke test can be certified before deployment exists.
5. If real Gemini is part of the interview promise, complete the separately
   approved single live test. Simulation is ready without this optional gate.

The current application is largely untracked in Git; no tracked files were
reported by `git ls-files`. Review/add/commit the intended source before a future
Git-connected deployment. Nothing was staged, committed or pushed in this review.
Do not use the temporary verification endpoint for hosting: project history
records it as expiring on 7 November 2026 at 23:30 India time
(18:00 UTC); confirm the expiry in the provider console.

## Exact manual deployment sequence

1. After reviewing source and secret exclusions, commit and push yourself when
   ready. Do not include populated env files or `.sdk-artifacts`.
2. Use the intended persistent Neon synthetic-demo branch, with pooled TLS
   `DATABASE_URL`. Privately configure that same branch's direct
   `DATABASE_URL_UNPOOLED` for local migrations. Do not use the test endpoint.
3. From `backend`, run:

   ```powershell
   .venv/Scripts/python.exe -m alembic current
   .venv/Scripts/python.exe -m alembic upgrade head
   .venv/Scripts/python.exe -m alembic check
   ```

4. Render: create a Free Python Web Service, root `backend`, Python `3.13.9`,
   build `pip install -r requirements.txt`, start
   `uvicorn app.main:app --host 0.0.0.0 --port $PORT --proxy-headers`, health
   `/health`, automatic deployment off. Root `render.yaml` contains this setup.
5. Set Render `DATABASE_URL`, a fresh `WORKSPACE_TOKEN`, and
   `FRONTEND_ORIGINS=["https://YOUR-PROJECT.pages.dev"]`. Copy AI settings above
   with external AI disabled and no key for the simulated interview path.
   The running backend does not need the direct migration URL.
6. Deploy Render deliberately. Check HTTPS `/health` and `/health/db` both return
   `{"status":"ok"}` (liveness includes an additional service field).
7. Cloudflare Pages: repository root setting `frontend`, build `npm run build`,
   output `dist`, `NODE_VERSION=22`, and build environment
   `VITE_API_BASE_URL=https://YOUR-SERVICE.onrender.com` (no `/api`). Deploy.
8. Update Render CORS to the exact final Pages HTTPS origin if it differs. Add
   an exact custom-domain origin only if used. Do not use wildcards or disable
   workspace authentication. Rebuild Pages whenever its API variable changes.
9. Open Pages, wait for API/DB wake-up, then complete the checklist below.
   Confirm no mixed-content/CORS errors. Share the workspace token privately.

Render's free service can sleep after 15 minutes idle; allow startup time before
an interview. All data lives in Neon, not Render's ephemeral filesystem.
Settings follow [Render FastAPI](https://render.com/docs/deploy-fastapi),
[Render free-service limits](https://render.com/docs/free),
[Cloudflare build configuration](https://developers.cloudflare.com/pages/configuration/build-configuration/)
and [Neon pooling guidance](https://neon.com/docs/connect/connection-pooling).

## Manual browser acceptance (exact expected results)

For local isolated checks, use the three-terminal commands in
[DEPLOYMENT.md section 6](DEPLOYMENT.md#6-browser-acceptance-checklist-manual-still-pending).
Use `opspilot-browser-test` only on that localhost test server. For public checks,
use the deployed Pages URL and private production workspace token.

- Submit a wrong token: readable error, then correct it: workspace opens.
- Overview: counts/trend render; switch through all five navigation views.
- Services: register `Final Review <unique suffix>`, save UUID/key privately,
  edit description, verify success state and retained description on refresh.
- QuickCart: select that service, run Payment gateway timeout; expect five logs
  and one incident. Immediate repeat should show a cooldown error.
- Live logs: filter that service/severity and search `timed out`; inspect metadata.
- Incidents: open details, run simulated analysis; verify the explicit simulated
  badge/disclaimer. Gemini button must remain disabled when unconfigured.
- Click an evidence UUID: corresponding stored message, severity, time and service
  appear. Close evidence, close incident; test keyboard focus indicators.
- Change incident to Investigating, then Resolved. Refresh; status/logs persist.
- Use browser Network offline mode: next refresh shows connection attention/error
  and last success time. Restore connectivity; Retry recovers.
- Sign out: dashboard/key disappear; reload does not restore workspace access.
- At 390px and desktop widths: no overlapping controls; tables scroll inside their
  panel. Tab through forms/buttons, including Skip to workspace content.
- Console/Network: no CORS/mixed-content errors; no DB/Gemini secrets in frontend
  assets. Workspace token is expected in authenticated request headers.

## Connect one external Python application

- [ ] Register one dedicated service; retain its UUID and ingestion key privately.
- [ ] In that application's environment, install `./opspilot-sdk` (absolute path
  if elsewhere), or the locally built wheel. Add `[fastapi]` only if required.
- [ ] Set only `OPSPILOT_API_URL=https://YOUR-SERVICE.onrender.com`,
  `OPSPILOT_SERVICE_ID=<UUID>`, `OPSPILOT_INGESTION_KEY=<key>` server-side.
- [ ] Create `OpsPilot.from_env()` once per worker after startup; use explicit
  reporting or the existing optional FastAPI middleware/lifespan example.
- [ ] Send five identical synthetic errors on the same endpoint within 120 seconds.
- [ ] Flush outside request handlers; confirm delivered=5, failed=0, dropped=0.
- [ ] In OpsPilot confirm exactly five logs and one Open incident with count 5.
- [ ] Run simulated analysis and open evidence; resolve the incident and refresh.
- [ ] Close the SDK during shutdown. Never send the workspace token, DB URL or
  Gemini key to the monitored app; it needs only its own ingestion key.

Full runnable integration examples: [SDK README](../opspilot-sdk/README.md).
