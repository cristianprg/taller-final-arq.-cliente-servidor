import threading

from infrastructure.worker_pool import WorkerPool


class WorkerService:
    def __init__(self, num_workers: int = 3) -> None:
        self.pool = WorkerPool(num_workers=num_workers)
        self._started = False
        self._lock = threading.Lock()

    def start(self) -> None:
        with self._lock:
            if self._started:
                return
            self.pool.start()
            self._started = True

    def stop(self) -> None:
        self.pool.stop()

    def update_config(
        self,
        desired_workers: int | None = None,
        producer_interval: float | None = None,
        min_process_time: float | None = None,
        max_process_time: float | None = None,
    ) -> None:
        self.pool.update_config(
            desired_workers=desired_workers,
            producer_interval=producer_interval,
            min_process_time=min_process_time,
            max_process_time=max_process_time,
        )

    def get_config(self) -> dict:
        return self.pool.get_config()
