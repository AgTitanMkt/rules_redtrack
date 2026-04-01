import threading
from datetime import datetime
from typing import Callable, Optional


class RuleScheduler:
    def __init__(self):
        self._thread: Optional[threading.Thread] = None
        self._stop = threading.Event()
        self._interval = 300
        self._callback: Optional[Callable] = None
        self._last_run: Optional[datetime] = None
        self._running = False
        self._count = 0

    @property
    def is_running(self):
        return self._running and self._thread and self._thread.is_alive()

    @property
    def status(self):
        return {
            "running": self.is_running,
            "interval_minutes": self._interval // 60,
            "last_run": self._last_run.isoformat() if self._last_run else None,
            "run_count": self._count,
        }

    def start(self, callback: Callable, interval_minutes: int = 5):
        if self.is_running:
            self.stop()
        self._callback = callback
        self._interval = max(60, interval_minutes * 60)
        self._stop.clear()
        self._running = True
        self._thread = threading.Thread(target=self._loop, daemon=True)
        self._thread.start()

    def stop(self):
        self._running = False
        self._stop.set()
        if self._thread:
            self._thread.join(timeout=5)
            self._thread = None

    def _loop(self):
        while not self._stop.is_set():
            try:
                self._last_run = datetime.now()
                self._count += 1
                if self._callback:
                    self._callback()
            except Exception as e:
                print(f"[SCHEDULER] Error: {e}")
            self._stop.wait(timeout=self._interval)
        self._running = False


scheduler = RuleScheduler()
