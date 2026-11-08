# OpsPilot Python SDK — Phase 1

Reusable local Python package `opspilot-sdk`, imported as `opspilot_sdk`.
Python 3.10+ required. Not published to PyPI or deployed. Sends only explicit
events and optional unhandled FastAPI exceptions to the existing ingestion API.

## 1. Install in the monitored application's environment

From the OpsPilot repository root (Windows PowerShell):

```powershell
python -m venv .sdk-demo-venv
.sdk-demo-venv/Scripts/python.exe -m pip install "./opspilot-sdk[fastapi]" uvicorn python-dotenv
```

For an existing Python application, use its virtual environment's Python:

```powershell
python -m pip install "C:/Users/manik/Downloads/OPSPILOT AI/opspilot-sdk[fastapi]"
```

Core dependency: HTTPX. Omit `[fastapi]` when not using FastAPI. Share the package
directory privately, or build and share a local wheel (no publishing needed):

```powershell
python -m pip wheel --no-deps --wheel-dir .sdk-artifacts ./opspilot-sdk
python -m pip install .sdk-artifacts/opspilot_sdk-0.1.0-py3-none-any.whl
```

The SDK has no dependency on OpsPilot backend source, database credentials,
workspace token, Gemini, or the backend's virtual environment.

## 2. Register a service and configure the external backend

Start OpsPilot with `npm run dev:backend` and `npm run dev` in separate terminals.
Verify `http://127.0.0.1:8000/health/db` returns `{"status":"ok"}`.
Open `http://127.0.0.1:5173`, enter `WORKSPACE_TOKEN` from `backend/.env`, and
register a NEW service such as `External Python Demo`. Save the returned service
UUID and one-time ingestion key privately. Rotating the key revokes the old one.

Set these in the monitored backend's terminal or hosting environment:

```powershell
$env:OPSPILOT_API_URL='http://127.0.0.1:8000'
$env:OPSPILOT_SERVICE_ID='YOUR-SERVICE-UUID'
$env:OPSPILOT_INGESTION_KEY='YOUR-INGESTION-KEY'
```

The API URL is an origin, without `/api` or `/ingest`. Remote URLs require HTTPS
with certificate verification; HTTP is allowed only on localhost/127.0.0.1/::1.
Redirects and implicit environment proxies are disabled. A hosted application
cannot reach your laptop through its own localhost; it needs a reachable HTTPS
OpsPilot backend. Keep ingestion keys server-side and out of source control.

## 3. Report structured errors or exceptions

```python
from opspilot_sdk import OpsPilot

monitor = OpsPilot.from_env()  # one per process, created after worker startup
# Or: OpsPilot(api_url="https://your-api.example", service_id="...", ingestion_key="...")

queued = monitor.report_error(
    "Payment gateway timed out",
    error_type="PaymentGatewayTimeout",
    endpoint="/checkout",
    metadata={"component": "payments", "environment": "staging"},
)

try:
    raise RuntimeError("Sensitive exception text is omitted")
except RuntimeError as exc:
    monitor.report_exception(exc, endpoint="/checkout")
    # Continue your application's existing error handling.

# Scripts/shutdown only; do not wait inside request handlers:
monitor.flush(timeout=2)
print(monitor.stats)  # accepted, delivered, failed, dropped; no payloads/secrets
monitor.close(timeout=2)
```

Report methods return queue acceptance, NOT delivery. False means dropped
(invalid input, full queue or closed client). `flush()` means pending work
finished, not that it succeeded; inspect `stats["failed"]` too.
Supported severities are `ERROR` (default) and `CRITICAL`.
`from_env()` reads only the three named variables; it does not load dotenv files.
Missing/invalid startup configuration fails early; subsequent delivery failures
are isolated from monitored application requests.

## 4. Optional FastAPI integration

Merge the startup/shutdown logic into your existing lifespan:

```python
import asyncio
from contextlib import asynccontextmanager
from fastapi import FastAPI
from opspilot_sdk import OpsPilot
from opspilot_sdk.fastapi import OpsPilotMiddleware

@asynccontextmanager
async def lifespan(app):
    app.state.opspilot = OpsPilot.from_env()
    try:
        yield
    finally:
        await asyncio.to_thread(app.state.opspilot.close, 2.0)

app = FastAPI(lifespan=lifespan)
app.add_middleware(OpsPilotMiddleware)

@app.get("/checkout")
def checkout():
    raise RuntimeError("Synthetic failure")
```

Alternatively pass `client=monitor` to the middleware and manage that client's
lifecycle yourself. Create one client per worker after startup, never before
process forking. Do not replace your application's existing startup tasks.

The integration queues an event then re-raises the SAME exception, preserving
normal HTTP 500 behavior. Handled HTTPException responses, arbitrary 500 responses,
exceptions swallowed by custom handlers, WebSockets, and detached background-task
errors are not automatically captured. Report these explicitly if appropriate.
Avoid explicitly reporting and then re-raising through the middleware, which
would send duplicate events. Route templates are used, e.g. `/orders/{order_id}`.
No raw request URL, query string, body, headers, cookies, stack, locals, or
exception message is collected.

## 5. Run the independent external FastAPI example

From the repository root with the three variables set:

```powershell
.sdk-demo-venv/Scripts/python.exe -m uvicorn app:app --app-dir examples/external-fastapi --host 127.0.0.1 --port 9000
```

Optional: copy `examples/external-fastapi/.env.example` to an ignored `.env`, fill
it privately, and add `--env-file examples/external-fastapi/.env` to uvicorn.
The intentionally failing example routes are for controlled local testing only.

In another PowerShell terminal, trigger five matching errors within two minutes:

```powershell
1..5 | ForEach-Object { curl.exe -s -o NUL -w "%{http_code}\n" http://127.0.0.1:9000/demo/unhandled }
```

Five HTTP 500 responses are expected: monitoring preserves application behavior.
Wait briefly, then open `http://127.0.0.1:9000/demo/stats`; expect accepted=5,
delivered=5, failed=0. In OpsPilot, filter to this service and confirm five stored
`Unhandled RuntimeError` logs and one Open incident with event count 5. The
dashboard refreshes about every five seconds. For a structured handled error:

```powershell
curl.exe -X POST http://127.0.0.1:9000/demo/handled
```

That route has a different signature and does not combine with unhandled errors.
The existing detector groups by error type, endpoint and normalized message;
five matching ERROR/CRITICAL events received within 120 seconds open an incident.
Further events update an active incident. Existing authentication, rate limits
(120 events/service/minute), simulator, dashboard and AI APIs are unchanged.

## Reliability and privacy

- One daemon sender and a bounded in-memory queue (default 100, configurable
  1–1000). Reporting performs redaction and queues without caller-thread network
  I/O. Full queues drop new events. There is no disk spool or log scraping.
- Default HTTPX timeout is one second per connect/read/write/pool operation,
  configurable 0.05–5 seconds. It is not a total wall-clock deadline; DNS and OS
  scheduling may take longer. All network activity remains in the daemon. See
  [HTTPX timeout semantics](https://www.python-httpx.org/advanced/timeouts/).
- Default one retry, maximum two, only for connection-establishment failures;
  interruptible backoff is 0.1/0.2 seconds. Never retries HTTP responses, redirects
  or ambiguous read/write failures: ingestion has no idempotency key, so a retry
  after delivery could inflate incident counts. Delivery is best-effort, not
  exactly-once. Outages and process termination may lose events.
- `close(timeout=2)` stops acceptance and waits at most two seconds. The daemon
  may finish later. Call `flush`/`close` outside requests and off the event loop.
- Before queueing, redact common credential fields, bearer/basic credentials,
  URLs, emails, phone/card-like long numbers, known token formats and this
  client's configured ingestion key. Nested metadata depth/count/size is bounded;
  oversized metadata is omitted. Unknown objects are not stringified.
- Pattern matching cannot recognize every secret or personal identifier. Send
  only reviewed minimal messages and metadata. Exception text is always omitted;
  this can group different failures of the same exception class on one route.
  Use a stable reviewed structured event when finer grouping is needed.
- No automatic fixes, commands, remote execution, environment dumping,
  unrestricted collection or automatic production changes. OpsPilot remains
  one shared demo workspace; this SDK does not add tenant isolation.

## Tests

From the repository root:

```powershell
backend/.venv/Scripts/python.exe -m pytest -c opspilot-sdk/pyproject.toml opspilot-sdk/tests -q
```

Alternatively install `[test]` and run `python -m pytest` inside `opspilot-sdk`.
Unit/ASGI tests use in-memory transports without network requests.
For real PostgreSQL verification, set `backend/.env.test.local` to a separate
schema-only/migrated Neon endpoint, never the application endpoint. From backend:

```powershell
$env:RUN_NEON_TESTS='1'
.venv/Scripts/python.exe -m pytest tests/test_sdk_postgres.py -q
```

The existing isolation guard rejects the application endpoint, including pooled
and direct aliases. This test drives the SDK into the real ingestion HTTP route
via TestClient, verifies no incident after 1–4 events, then reads the fifth-event
incident and five committed logs through an independent PostgreSQL session.
It creates synthetic test rows and never calls Gemini. The example walkthrough
above exercises actual network ports between two applications.

For a repeatable actual-HTTP check using an installed SDK, run from the repository
root with ports 8010 and 9000 free:

```powershell
backend/.venv/Scripts/python.exe backend/scripts/verify_sdk.py
```

Install the local wheel in that environment first, or set `PYTHONPATH` to its
isolated install directory. The script uses only the isolated test database,
starts and stops its own localhost servers, creates a synthetic service, and
checks five external HTTP failures produce five logs and one Open incident.

Troubleshooting: 401 = wrong/rotated ingestion key; 409 = inactive service;
422 = invalid event; 429 = rate limit; 503 = API database unavailable.
Stats intentionally contain counts only; use API health checks and docs to
diagnose configuration without printing keys or payloads.
