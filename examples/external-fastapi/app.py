"""A separate monitored application. No OpsPilot backend imports."""
import asyncio
from contextlib import asynccontextmanager

from fastapi import FastAPI
from opspilot_sdk import OpsPilot
from opspilot_sdk.fastapi import OpsPilotMiddleware


@asynccontextmanager
async def lifespan(app):
    # Create after process startup; use one client per worker, never before fork.
    client = OpsPilot.from_env()
    app.state.opspilot = client
    try:
        yield
    finally:
        await asyncio.to_thread(client.close, 2.0)


app = FastAPI(title="External OpsPilot SDK example", lifespan=lifespan)


app.add_middleware(OpsPilotMiddleware)


@app.get("/health")
def health():
    return {"status": "ok"}


@app.get("/demo/unhandled")
def unhandled():
    raise RuntimeError("Synthetic checkout failure")


@app.post("/demo/handled")
def handled():
    accepted = app.state.opspilot.report_error(
        "Synthetic payment gateway timed out", error_type="PaymentGatewayTimeout",
        endpoint="/demo/handled", metadata={"environment": "demo"})
    return {"event_queued": accepted}


@app.get("/demo/stats")
def stats():
    return app.state.opspilot.stats
