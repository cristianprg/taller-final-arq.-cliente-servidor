from fastapi import APIRouter, Header, HTTPException

from application.services import WorkerService
from domain.metrics import MetricsCollector
from presentation.schemas import ConfigResponse, ConfigUpdateRequest, MetricsResponse

ADMIN_TOKEN = "admin123"

router = APIRouter()
_worker_service: WorkerService | None = None


def set_worker_service(service: WorkerService) -> None:
    global _worker_service
    _worker_service = service


def _check_admin(authorization: str | None) -> None:
    if authorization is None or not authorization.startswith("Bearer "):
        raise HTTPException(status_code=401, detail="Missing token")
    token = authorization.split(" ", 1)[1]
    if token != ADMIN_TOKEN:
        raise HTTPException(status_code=403, detail="Invalid token")


@router.get("/admin/metrics", response_model=MetricsResponse)
def get_metrics(authorization: str | None = Header(default=None, alias="Authorization")):
    _check_admin(authorization)
    return MetricsCollector().snapshot()


@router.get("/admin/config", response_model=ConfigResponse)
def get_config(authorization: str | None = Header(default=None, alias="Authorization")):
    _check_admin(authorization)
    if _worker_service is None:
        raise HTTPException(status_code=500, detail="Worker service not ready")
    return _worker_service.get_config()


@router.post("/admin/config", response_model=ConfigResponse)
def update_config(
    payload: ConfigUpdateRequest,
    authorization: str | None = Header(default=None, alias="Authorization"),
):
    _check_admin(authorization)
    if _worker_service is None:
        raise HTTPException(status_code=500, detail="Worker service not ready")
    _worker_service.update_config(
        desired_workers=payload.desired_workers,
        producer_interval=payload.producer_interval,
        min_process_time=payload.min_process_time,
        max_process_time=payload.max_process_time,
    )
    return _worker_service.get_config()
