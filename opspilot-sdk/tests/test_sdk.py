import json
import threading
import time
from uuid import uuid4

import httpx
import pytest
from fastapi import FastAPI, HTTPException
from fastapi.testclient import TestClient

from opspilot_sdk import OpsPilot
from opspilot_sdk.fastapi import OpsPilotMiddleware


def sdk(handler, **kwargs):
    return OpsPilot("https://monitor.example", str(uuid4()), "private-ingestion-key",
                    transport=httpx.MockTransport(handler), **kwargs)


def test_wire_contract_and_redaction():
    requests = []
    def handler(request):
        requests.append(request)
        return httpx.Response(201, json={"log_id": str(uuid4()), "incident_id": None})
    client = sdk(handler)
    assert client.report_error('password="very private" Bearer abc123 user@example.com https://u:p@host/path?token=x',
        error_type="Timeout", endpoint="/checkout?token=hidden",
        metadata={"nested": {"api_key": "hidden-key", "phone": "12345"}, "cookie": "private-cookie",
                  "safe": "secret=hidden-secret", "object": object()})
    assert client.flush()
    assert client.close()
    request = requests[0]
    assert request.method == "POST" and "/ingest/" in str(request.url)
    assert request.headers["X-Ingestion-Key"] == "private-ingestion-key"
    body = json.loads(request.content)
    assert body["endpoint"] == "/checkout"
    for secret in ("very private", "abc123", "user@example.com", "u:p", "hidden-key", "private-cookie", "hidden-secret"):
        assert secret not in request.content.decode()
    assert body["metadata"]["object"] == "[OMITTED]"
    assert client.stats == {"accepted": 1, "delivered": 1, "failed": 0, "dropped": 0}


def test_exception_does_not_collect_message_or_locals():
    bodies = []
    client = sdk(lambda r: (bodies.append(json.loads(r.content)) or httpx.Response(201)))
    client.report_exception(ValueError("confidential customer data"))
    assert client.flush() and client.close()
    assert bodies[0]["message"] == "Unhandled ValueError"
    assert "confidential" not in json.dumps(bodies)


def test_configured_ingestion_key_is_redacted_even_without_a_label():
    bodies = []
    client = sdk(lambda r: (bodies.append(r.content.decode()) or httpx.Response(201)))
    client.report_error("private-ingestion-key", metadata={"value": "private-ingestion-key"})
    assert client.flush() and client.close()
    assert "private-ingestion-key" not in bodies[0]


def test_example_uses_lifespan_client_and_captures_five_failures(monkeypatch):
    import importlib.util
    from pathlib import Path
    path = Path(__file__).resolve().parents[2] / "examples" / "external-fastapi" / "app.py"
    bodies = []
    client = sdk(lambda r: (bodies.append(json.loads(r.content)) or httpx.Response(201)))
    monkeypatch.setattr(OpsPilot, "from_env", classmethod(lambda cls: client))
    spec = importlib.util.spec_from_file_location("external_demo", path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    with TestClient(module.app, raise_server_exceptions=False) as browser:
        assert browser.get("/health").status_code == 200
        for _ in range(5):
            assert browser.get("/demo/unhandled").status_code == 500
        assert client.flush()
        assert browser.get("/demo/stats").json()["delivered"] == 5
        assert len(bodies) == 5
        assert all(b["endpoint"] == "/demo/unhandled" for b in bodies)
    assert not client.report_error("after shutdown")


@pytest.mark.parametrize("failure,retries,expected", [
    (httpx.ConnectError, 1, 2), (httpx.ConnectTimeout, 2, 3),
    (httpx.ReadTimeout, 2, 1), (httpx.WriteError, 2, 1),
])
def test_only_pre_delivery_failures_retry(failure, retries, expected):
    attempts = []
    def handler(request):
        attempts.append(1)
        assert request.extensions["timeout"]["connect"] == 0.1
        raise failure("private transport detail", request=request)
    client = sdk(handler, max_retries=retries, timeout=0.1)
    assert client.report_error("Test")
    assert client.flush(3)
    client.close()
    assert len(attempts) == expected
    assert client.stats["failed"] == 1


@pytest.mark.parametrize("status", [301, 401, 409, 422, 429, 500, 503])
def test_http_failures_are_not_retried_or_redirected(status):
    calls = []
    client = sdk(lambda r: (calls.append(r) or httpx.Response(status, headers={"Location": "https://evil.example"})))
    client.report_error("Test")
    assert client.flush()
    client.close()
    assert len(calls) == 1 and client.stats["failed"] == 1


def test_queue_is_bounded_and_reporting_and_close_do_not_wait_for_network():
    started, release = threading.Event(), threading.Event()
    def blocked(request):
        started.set()
        release.wait(3)
        return httpx.Response(201)
    client = sdk(blocked, queue_size=1)
    client.report_error("First")
    assert started.wait(1)
    before = time.monotonic()
    assert client.report_error("Second")
    assert not client.report_error("Third")
    assert not client.flush(0.01)
    assert not client.close(0.01)
    assert time.monotonic() - before < 0.5
    assert not client.report_error("After close")
    release.set()
    assert client.close(2)


def test_metadata_and_invalid_events_are_bounded():
    bodies = []
    client = sdk(lambda r: (bodies.append(json.loads(r.content)) or httpx.Response(201)))
    assert not client.report_error(123)
    assert not client.report_error("x", severity="INFO")
    assert not client.report_error("x", endpoint=None)
    cyclic = {}; cyclic["cycle"] = cyclic
    assert client.report_error("x" * 5000, metadata=cyclic)
    assert client.report_error("x", metadata={str(i): "x" * 500 for i in range(20)})
    assert client.flush() and client.close()
    assert len(bodies[0]["message"]) == 4000
    assert all(len(json.dumps(b["metadata"])) <= 4000 for b in bodies)


@pytest.mark.parametrize("url", ["http://remote.example", "https://user:pass@host", "https://host/api", "https://host?key=x", "file:///tmp"])
def test_insecure_configuration_rejected(url):
    with pytest.raises(ValueError):
        OpsPilot(url, str(uuid4()), "key")


def test_fastapi_captures_once_preserves_failure_and_ignores_handled_errors():
    bodies = []
    client = sdk(lambda r: (bodies.append(json.loads(r.content)) or httpx.Response(201)))
    app = FastAPI()
    app.add_middleware(OpsPilotMiddleware, client=client)
    original = RuntimeError("secret customer details")
    @app.get("/orders/{order_id}")
    def fail(order_id: str):
        raise original
    @app.get("/handled")
    def handled():
        raise HTTPException(404, "not found")
    with TestClient(app, raise_server_exceptions=False) as browser:
        assert browser.get("/orders/private-user?token=private").status_code == 500
        assert browser.get("/handled").status_code == 404
    assert client.flush()
    assert len(bodies) == 1
    assert bodies[0]["endpoint"] == "/orders/{order_id}"
    assert "private" not in json.dumps(bodies) and "customer" not in json.dumps(bodies)
    with TestClient(app) as browser:
        with pytest.raises(RuntimeError) as caught:
            browser.get("/orders/1")
        assert caught.value is original
    client.close()


def test_fastapi_outage_still_returns_original_500():
    client = sdk(lambda r: (_ for _ in ()).throw(httpx.ConnectError("offline")), max_retries=0)
    app = FastAPI()
    app.add_middleware(OpsPilotMiddleware, client=client)
    @app.get("/failure")
    def fail():
        raise RuntimeError("test")
    with TestClient(app, raise_server_exceptions=False) as browser:
        assert browser.get("/failure").status_code == 500
    assert client.flush() and client.close()
    assert client.stats["failed"] == 1
