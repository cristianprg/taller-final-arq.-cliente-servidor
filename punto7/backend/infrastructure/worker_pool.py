import queue
import random
import threading
import time

from domain.metrics import MetricsCollector
from domain.models import Task


class WorkerPool:
    def __init__(
        self,
        num_workers: int = 3,
        max_queue: int = 100,
        producer_interval: float = 0.3,
        min_process_time: float = 1.0,
        max_process_time: float = 2.0,
    ) -> None:
        self.num_workers = num_workers
        self.queue: queue.Queue[Task] = queue.Queue(maxsize=max_queue)
        self.metrics = MetricsCollector()
        self._stop_event = threading.Event()
        self._worker_threads: list[threading.Thread] = []
        self._producer_thread: threading.Thread | None = None
        self._config_lock = threading.Lock()
        self._desired_workers = num_workers
        self._producer_interval = producer_interval
        self._min_process_time = min_process_time
        self._max_process_time = max_process_time
        self._task_id = 0
        self._task_id_lock = threading.Lock()

    def start(self) -> None:
        for _ in range(self.num_workers):
            self._spawn_worker()

        self._producer_thread = threading.Thread(
            target=self._produce_tasks,
            name="task-producer",
            daemon=True,
        )
        self._producer_thread.start()

    def stop(self) -> None:
        self._stop_event.set()

    def update_config(
        self,
        desired_workers: int | None = None,
        producer_interval: float | None = None,
        min_process_time: float | None = None,
        max_process_time: float | None = None,
    ) -> None:
        with self._config_lock:
            if desired_workers is not None:
                self._desired_workers = max(1, desired_workers)
            if producer_interval is not None:
                self._producer_interval = max(0.1, producer_interval)
            if min_process_time is not None:
                self._min_process_time = max(0.1, min_process_time)
            if max_process_time is not None:
                self._max_process_time = max(self._min_process_time, max_process_time)

        self._ensure_worker_count()

    def get_config(self) -> dict:
        with self._config_lock:
            return {
                "desired_workers": self._desired_workers,
                "producer_interval": self._producer_interval,
                "min_process_time": self._min_process_time,
                "max_process_time": self._max_process_time,
            }

    def _next_task_id(self) -> int:
        with self._task_id_lock:
            self._task_id += 1
            return self._task_id

    def _spawn_worker(self) -> None:
        worker_id = len(self._worker_threads) + 1
        thread = threading.Thread(
            target=self._worker_loop,
            args=(worker_id,),
            name=f"worker-{worker_id}",
            daemon=True,
        )
        thread.start()
        self._worker_threads.append(thread)

    def _ensure_worker_count(self) -> None:
        with self._config_lock:
            desired = self._desired_workers

        alive_threads = [t for t in self._worker_threads if t.is_alive()]
        self._worker_threads = alive_threads
        current = len(self._worker_threads)
        if desired > current:
            for _ in range(desired - current):
                self._spawn_worker()

    def _produce_tasks(self) -> None:
        while not self._stop_event.is_set():
            task = Task(
                id=self._next_task_id(),
                text="dummy text",
                created_at=time.time(),
            )
            try:
                self.queue.put(task, timeout=1)
            except queue.Full:
                pass
            self.metrics.update_queue_size(self.queue.qsize())
            with self._config_lock:
                interval = self._producer_interval
            time.sleep(interval)

    def _worker_loop(self, worker_id: int) -> None:
        while not self._stop_event.is_set():
            with self._config_lock:
                desired = self._desired_workers
            if worker_id > desired:
                break
            try:
                task = self.queue.get(timeout=1)
            except queue.Empty:
                self.metrics.update_queue_size(self.queue.qsize())
                continue

            self.metrics.update_queue_size(self.queue.qsize())
            start = time.time()

            # Observer inverso: el worker notifica cambios al MetricsCollector.
            self.metrics.worker_started()
            with self._config_lock:
                min_time = self._min_process_time
                max_time = self._max_process_time
            time.sleep(random.uniform(min_time, max_time))
            processing_time = time.time() - start
            self.metrics.worker_finished(processing_time)

            self.queue.task_done()
            self.metrics.update_queue_size(self.queue.qsize())
            _ = task
