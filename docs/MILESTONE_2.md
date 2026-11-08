# Milestone 2: services, ingestion, detection, and dashboard

## Run locally

Keep the existing root Neon `.env.local` file. No database URL changes are needed.

```powershell
npm run dev:backend
# Separate terminal:
npm run dev
```

Open http://127.0.0.1:5173. Copy the `WORKSPACE_TOKEN` value from local
`backend/.env` into the workspace access form. Do not include surrounding quotes.
This shared token protects the single demo workspace; it is not multi-user auth.
The browser keeps it in session storage until Sign out or the tab session ends.
Do not expose this development server publicly.

## Demonstrate the flow

1. Services: register a service (for example QuickCart Payments).
2. Save the ingestion key shown once after creation. Only its SHA-256 hash is stored.
3. QuickCart simulator: choose the active service and a failure scenario; Run simulation.
4. Live logs: inspect the actual stored logs and sanitized metadata.
5. Incidents: inspect the automatically created incident and event count.
6. Overview: inspect metrics and hourly errors computed from PostgreSQL.
7. Resolve the incident. Five new matching errors can create a new incident.

The verification run creates a clearly labeled QuickCart Payments demo service
and genuine persisted demo events. These are generated operational records, not
hardcoded dashboard responses. The dashboard polls every five seconds; hidden
tabs pause polling. No WebSocket dependency is required for this milestone.

## API

Management calls require `X-Workspace-Token`.

| Method | Path | Purpose |
| --- | --- | --- |
| POST / GET | /services | Register / paginated list |
| GET / PUT | /services/{id} | Read / update |
| DELETE | /services/{id} | Deactivate; preserve historical logs and incidents |
| POST | /services/{id}/rotate-key | Revoke old ingestion key and return a new one once |
| POST | /ingest/{service_id} | Store log; requires X-Ingestion-Key instead of workspace token |
| GET | /logs | Filter by service_id, severity, q, since, until; limit/offset |
| GET | /incidents | Filter by service_id/status; limit/offset |
| PATCH | /incidents/{id} | Change Open / Investigating / Resolved status |
| GET | /dashboard | Database aggregates and hourly error trend |
| POST | /simulator | Bounded QuickCart events through the shared ingestion pipeline |

Example ingestion (Python, replace ID and read key from your environment):

```python
import os
import httpx

response = httpx.post(
    'http://127.0.0.1:8000/ingest/YOUR_SERVICE_ID',
    headers={'X-Ingestion-Key': os.environ['INGESTION_KEY']},
    json={
        'severity': 'ERROR',
        'message': 'Payment gateway timed out after 30 seconds',
        'error_type': 'PaymentGatewayTimeout',
        'endpoint': '/payments/checkout',
        'metadata': {'component': 'payments'},
    },
)
response.raise_for_status()
print(response.json())
```

## Data and detection

- SQLAlchemy entities: services, logs, incidents. UUID primary keys and foreign keys.
- Alembic migration: a64bccfa6f4d; no runtime create_all or implicit schema updates.
- Migrations require `DATABASE_URL_UNPOOLED`. Runtime uses pooled `DATABASE_URL`.
- Five ERROR/CRITICAL logs of one normalized signature in 120 seconds create an incident.
- Signatures use error type, endpoint, and sanitized message with numeric/UUID values normalized.
- The detection clock is server received_at; client timestamps cannot spoof the detection window.
- A per-service PostgreSQL row lock serializes ingestion, lifecycle updates, cooldowns,
  and detection across workers. A partial unique index also protects active incident signatures.
- Further matching errors update the active incident count; CRITICAL escalates severity.
- Resolved incidents remain historical; only events received after resolution count toward a new one.
- Services are soft-deleted. PUT with active=true reactivates a service.

## Bounds and sanitization

Maximum 120 logs per service per minute, 4000 message characters, 4000 metadata
characters, 100 results per API page. Metadata is recursively bounded. Common
credential fields, bearer strings, passwords, email addresses, connection-string
credentials, and card-like values are redacted; endpoint query strings are discarded.
Pattern-based sanitization is a defense, not permission to send raw secrets: producers
must sanitize their own logs too.

Simulations are synchronous and automatically stop after five failure events or
three normal events, with a persisted 30-second per-service cooldown. They use the
same LogInput validation, sanitization, storage, limit, and detection function as
the external ingestion endpoint. There is no unbounded background loop or inert
Stop button. Scenarios: payment timeout, DB timeout, exception, normal.

## Verify

```powershell
npm run build
npm run lint
cd backend
.venv\Scripts\python.exe -m alembic current
.venv\Scripts\python.exe -m alembic check
.venv\Scripts\python.exe -m pytest -q
```

Database integration tests are intentionally opt-in. They read only
`backend/.env.test.local` and refuse the application's configured database URL.
The isolated milestone2-verification branch expires 2026-11-05 at 18:00 UTC.
The default unit-test command skips those integration tests.

```powershell
# From backend; requires a separate migrated Neon verification branch:
$env:RUN_NEON_TESTS='1'
.venv\Scripts\python.exe -m pytest -q -p no:cacheprovider --basetemp .pytest-tmp-YOUR_UNIQUE_RUN
```

The real-db suite tests concurrent ingestion, one-incident deduplication, rolling
windows, persisted event counts, resolution/new incidents, credential isolation
and rotation, CRUD/deactivation, redaction, pagination, simulator cooldown,
normal scenario, rate limits, and critical escalation.

`backend/scripts/verify_live_demo.py` exercises the running frontend proxy/API
and writes real QuickCart demo data. It deliberately does not delete history.
Rerunning it is subject to the same cooldown.
