import threading
import time
from collections import deque


class MetricsCollector:
    """
    Singleton: garantiza una sola instancia para que todas las capas
    reporten y lean las mismas metricas en memoria.
    """

    _instance = None
    _instance_lock = threading.Lock()

    def __new__(cls):
        # Thread-safe singleton creation.
        with cls._instance_lock:
            if cls._instance is None:
                cls._instance = super().__new__(cls)
                cls._instance._initialized = False
        return cls._instance

    def __init__(self) -> None:
        if self._initialized:
            return
        # Lock protege el estado compartido ante accesos concurrentes.
        self._lock = threading.Lock()
        self.queue_size = 0
        self.active_workers = 0
        self.total_processing_time = 0.0
        self.completed_jobs = 0
        self.completed_timestamps = deque()
        self._initialized = True

    def update_queue_size(self, size: int) -> None:
        with self._lock:
            self.queue_size = size

    def worker_started(self) -> None:
        with self._lock:
            self.active_workers += 1

    def worker_finished(self, processing_time: float) -> None:
        now = time.time()
        with self._lock:
            self.active_workers = max(0, self.active_workers - 1)
            self.completed_jobs += 1
            self.total_processing_time += processing_time
            self.completed_timestamps.append(now)
            self._prune_old(now)

    def _prune_old(self, now: float) -> None:
        cutoff = now - 60
        while self.completed_timestamps and self.completed_timestamps[0] < cutoff:
            self.completed_timestamps.popleft()

    def snapshot(self) -> dict:
        # Snapshot: se toma una copia consistente con el lock tomado.
        now = time.time()
        with self._lock:
            self._prune_old(now)
            jobs_per_minute = len(self.completed_timestamps)
            avg_time = (
                self.total_processing_time / self.completed_jobs
                if self.completed_jobs > 0
                else 0.0
            )
            return {
                "queue_size": self.queue_size,
                "active_workers": self.active_workers,
                "jobs_per_minute": jobs_per_minute,
                "average_processing_time": round(avg_time, 2),
            }
