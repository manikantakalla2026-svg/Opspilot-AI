"""One daemon worker, finite queue, no application-thread network I/O."""
import os
import queue
import threading
import time
from urllib.parse import urlsplit
from uuid import UUID

import httpx

from .redaction import clean_text, metadata_projection


class OpsPilot:
    def __init__(self, api_url: str, service_id: str, ingestion_key: str, *,
                 timeout: float = 1.0, max_retries: int = 1, queue_size: int = 100,
                 transport: httpx.BaseTransport | None = None):
        url = urlsplit(api_url)
        if (url.scheme not in {"http", "https"} or not url.hostname or url.username
                or url.password or url.query or url.fragment or url.path not in {"", "/"}
                or (url.scheme == "http" and url.hostname not in {"localhost", "127.0.0.1", "::1"})):
            raise ValueError("Use an HTTPS API origin; HTTP is allowed only on loopback")
        service_id = str(UUID(service_id))
        if not isinstance(ingestion_key, str) or not ingestion_key.strip() or any(ord(c) < 33 or ord(c) > 126 for c in ingestion_key):
            raise ValueError("A nonempty printable ingestion key is required")
        if not 0.05 <= timeout <= 5 or type(max_retries) is not int or not 0 <= max_retries <= 2:
            raise ValueError("Timeout must be 0.05–5 seconds; retries must be 0–2")
        if type(queue_size) is not int or not 1 <= queue_size <= 1000:
            raise ValueError("Queue size must be 1–1000")
        self._url = f"{api_url.rstrip('/')}/ingest/{service_id}"
        self._key = ingestion_key
        self._timeout = timeout
        self._retries = max_retries
        self._transport = transport
        self._queue = queue.Queue(maxsize=queue_size)
        self._lock = threading.Lock()
        self._closed = threading.Event()
        self._counts = {"accepted": 0, "delivered": 0, "failed": 0, "dropped": 0}
        self._worker = threading.Thread(target=self._run, name="opspilot-sender", daemon=True)
        self._worker.start()

    @classmethod
    def from_env(cls, **kwargs):
        """Read only these three explicit backend environment variables."""
        return cls(os.environ["OPSPILOT_API_URL"], os.environ["OPSPILOT_SERVICE_ID"],
                   os.environ["OPSPILOT_INGESTION_KEY"], **kwargs)

    @property
    def stats(self):
        with self._lock:
            return dict(self._counts)

    def report_error(self, message: str, *, error_type: str = "ApplicationError",
                     endpoint: str = "", metadata: dict | None = None,
                     severity: str = "ERROR") -> bool:
        """Return queue acceptance, NOT delivery. Invalid events are dropped safely."""
        try:
            if severity not in {"ERROR", "CRITICAL"} or not isinstance(message, str) or not message.strip():
                raise ValueError("Invalid error event")
            secrets = (self._key,)
            event = {"message": clean_text(message, secrets)[:4000],
                     "error_type": clean_text(error_type, secrets)[:100], "severity": severity,
                     "endpoint": clean_text(endpoint.split("?", 1)[0].split("#", 1)[0], secrets)[:200],
                     "metadata": metadata_projection(metadata, secrets)}
            with self._lock:
                if self._closed.is_set():
                    self._counts["dropped"] += 1
                    return False
                try:
                    self._queue.put_nowait(event)
                except queue.Full:
                    self._counts["dropped"] += 1
                    return False
                self._counts["accepted"] += 1
            return True
        except Exception:
            with self._lock:
                self._counts["dropped"] += 1
            return False

    def report_exception(self, exception: Exception, *, endpoint: str = "",
                         metadata: dict | None = None) -> bool:
        # No exception str(), stack, locals, request data or arbitrary repr().
        name = type(exception).__name__
        return self.report_error(f"Unhandled {name}", error_type=name,
                                 endpoint=endpoint, metadata=metadata)

    def _send(self, client, event):
        for attempt in range(self._retries + 1):
            try:
                # Stream and ignore response bodies: never buffer an unbounded reply.
                with client.stream("POST", self._url, headers={"X-Ingestion-Key": self._key}, json=event) as response:
                    return response.status_code == 201
            except (httpx.ConnectTimeout, httpx.ConnectError):
                # Connection failures happen before delivery. Never retry ambiguous
                # read/write failures or HTTP responses: ingestion has no idempotency.
                if attempt == self._retries or self._closed.wait(0.1 * (attempt + 1)):
                    return False
            except Exception:
                return False
        return False

    def _run(self):
        try:
            with httpx.Client(timeout=self._timeout, transport=self._transport,
                              follow_redirects=False, trust_env=False) as client:
                while not self._closed.is_set() or not self._queue.empty():
                    try:
                        event = self._queue.get(timeout=0.05)
                    except queue.Empty:
                        continue
                    try:
                        delivered = self._send(client, event)
                        with self._lock:
                            self._counts["delivered" if delivered else "failed"] += 1
                    finally:
                        self._queue.task_done()
        except Exception:
            # Even transport initialization failures must not escape into the app.
            with self._lock:
                self._closed.set()
            while True:
                try:
                    self._queue.get_nowait()
                except queue.Empty:
                    break
                self._queue.task_done()
                with self._lock:
                    self._counts["failed"] += 1

    def flush(self, timeout: float = 2.0) -> bool:
        """Wait at most timeout seconds for queued work; not for request handlers."""
        deadline = time.monotonic() + max(0, timeout)
        with self._queue.all_tasks_done:
            while self._queue.unfinished_tasks:
                remaining = deadline - time.monotonic()
                if remaining <= 0:
                    return False
                self._queue.all_tasks_done.wait(remaining)
        return True

    def close(self, timeout: float = 2.0) -> bool:
        """Stop acceptance and allow a bounded wait. A daemon may finish later."""
        with self._lock:
            self._closed.set()
        self._worker.join(max(0, timeout))
        return not self._worker.is_alive()
