"""Actual localhost SDK -> API -> isolated Neon test; never production.

Run from the repository root with backend/.venv/Scripts/python.exe.
Creates synthetic service/log/incident records; never invokes Gemini.
"""
import os
from pathlib import Path
import socket
import subprocess
import sys
import time

import httpx

ROOT = Path(__file__).resolve().parents[2]


def wait_for(client, url, process, timeout=30):
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        if process.poll() is not None:
            raise RuntimeError("Verification server exited; inspect test configuration")
        try:
            if client.get(url).status_code == 200:
                return
        except httpx.HTTPError:
            pass
        time.sleep(0.1)
    raise RuntimeError("Verification server did not become ready")


def main():
    for port in (8010, 9000):
        with socket.socket() as probe:
            probe.bind(("127.0.0.1", port))  # fail rather than use someone else's server
    processes = []
    try:
        # Uvicorn closes connections after unhandled application exceptions.
        # Each deliberate 500 uses a fresh connection; never retry a failure
        # that may already have queued an SDK event.
        with httpx.Client(timeout=5, trust_env=False, headers={"Connection": "close"}) as http:
            api = subprocess.Popen([sys.executable, str(ROOT / "backend/scripts/demo_test_server.py")],
                                   cwd=ROOT, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
            processes.append(api)
            wait_for(http, "http://127.0.0.1:8010/health", api)
            assert http.get("http://127.0.0.1:8010/health/db").status_code == 200
            headers = {"X-Workspace-Token": "opspilot-browser-test"}
            from uuid import uuid4
            result = http.post("http://127.0.0.1:8010/services", headers=headers,
                               json={"name": f"sdk-http-{uuid4().hex[:10]}"})
            assert result.status_code == 201
            service = result.json()
            env = dict(os.environ, OPSPILOT_API_URL="http://127.0.0.1:8010",
                       OPSPILOT_SERVICE_ID=service["id"],
                       OPSPILOT_INGESTION_KEY=service["ingestion_key"])
            # Use installed package when available; caller can set PYTHONPATH for source tests.
            external = subprocess.Popen([sys.executable, "-m", "uvicorn", "app:app", "--app-dir",
                                         str(ROOT / "examples/external-fastapi"), "--host", "127.0.0.1",
                                         "--port", "9000"], cwd=ROOT, env=env,
                                        stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
            processes.append(external)
            wait_for(http, "http://127.0.0.1:9000/health", external)
            for _ in range(5):
                assert http.get("http://127.0.0.1:9000/demo/unhandled").status_code == 500
            deadline = time.monotonic() + 20
            while time.monotonic() < deadline:
                stats = http.get("http://127.0.0.1:9000/demo/stats").json()
                if stats["delivered"] == 5:
                    break
                time.sleep(0.1)
            assert stats == {"accepted": 5, "delivered": 5, "failed": 0, "dropped": 0}
            logs = http.get("http://127.0.0.1:8010/logs", headers=headers,
                            params={"service_id": service["id"]}).json()
            incidents = http.get("http://127.0.0.1:8010/incidents", headers=headers,
                                 params={"service_id": service["id"]}).json()
            assert logs["total"] == 5 and incidents["total"] == 1
            assert incidents["items"][0]["event_count"] == 5
            assert incidents["items"][0]["status"] == "Open"
            assert all(log["message"] == "Unhandled RuntimeError" for log in logs["items"])
            print("PASS: five real external FastAPI HTTP failures -> installed SDK -> five logs -> one Open incident")
    finally:
        for process in reversed(processes):
            process.terminate()
            try:
                process.wait(5)
            except subprocess.TimeoutExpired:
                process.kill()
                process.wait(5)


if __name__ == "__main__":
    main()
