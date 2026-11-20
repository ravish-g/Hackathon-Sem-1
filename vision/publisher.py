import json
import threading
import time
from collections import deque

try:
    import requests
except ImportError:
    requests = None

from .metrics import TelemetrySample


class TelemetryPublisher:
    def __init__(self, url: str | None, worker_token: str | None = None, max_pending: int = 100):
        self.url = url
        self.worker_token = worker_token
        self._pending: deque[dict] = deque(maxlen=max_pending)
        self._lock = threading.Lock()
        self._stop = threading.Event()
        self._thread: threading.Thread | None = None

    def start(self) -> None:
        if not self.url:
            return
        self._thread = threading.Thread(target=self._run, name="telemetry-publisher", daemon=True)
        self._thread.start()

    def stop(self) -> None:
        self._stop.set()
        if self._thread:
            self._thread.join(timeout=3.0)

    def publish(self, sample: TelemetrySample) -> bool:
        payload = sample.to_dict()
        if not self.url:
            return True
        with self._lock:
            self._pending.append(payload)
        return True

    def _run(self) -> None:
        while not self._stop.is_set():
            payload = None
            with self._lock:
                if self._pending:
                    payload = self._pending.popleft()
            if payload is None:
                time.sleep(0.05)
                continue
            if self._post(payload):
                continue
            delay = 1.0
            for _ in range(3):
                time.sleep(delay)
                if self._post(payload):
                    break
                delay = min(delay * 2.0, 8.0)

    def _post(self, payload: dict) -> bool:
        if requests is None:
            return False
        headers = {"Content-Type": "application/json"}
        if self.worker_token:
            headers["Authorization"] = f"Bearer {self.worker_token}"
        try:
            response = requests.post(self.url, json=payload, headers=headers, timeout=2.0)
            return 200 <= response.status_code < 300
        except requests.RequestException:
            return False
