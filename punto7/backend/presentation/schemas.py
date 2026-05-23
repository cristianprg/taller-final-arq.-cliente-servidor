from pydantic import BaseModel


class MetricsResponse(BaseModel):
    queue_size: int
    active_workers: int
    jobs_per_minute: int
    average_processing_time: float


class ConfigResponse(BaseModel):
    desired_workers: int
    producer_interval: float
    min_process_time: float
    max_process_time: float


class ConfigUpdateRequest(BaseModel):
    desired_workers: int | None = None
    producer_interval: float | None = None
    min_process_time: float | None = None
    max_process_time: float | None = None
