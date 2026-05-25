"""
Presentation Layer - FastAPI Routers para Historia #4.

Endpoints:
  GET /jobs/{job_id}                → estado y progreso
  GET /jobs/{job_id}/results        → resultados paginados
  GET /jobs/{job_id}/report         → reporte agregado

JUSTIFICACIÓN:
- Solo lectura → se atienden en el hilo del servidor sin workers adicionales
- FastAPI multihilo → thread-safe via scoped_session en la infraestructura
- Pydantic schemas → validación + documentación OpenAPI automática
"""
from typing import Optional
from dataclasses import asdict

from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel, Field

from application.dtos import ResultsQuery
from application.services.job_query_service import (
    JobQueryService,
    JobNotFoundError,
    JobStillProcessingError,
)

router = APIRouter(prefix="/jobs", tags=["Jobs - Consultas"])


# ─── Pydantic Response Schemas ────────────────────────────────────────────────

class JobStatusResponse(BaseModel):
    job_id: str
    status: str
    total_texts: int
    processed_texts: int
    progress_percentage: float = Field(..., description="Porcentaje completado [0-100]")
    created_at: str
    updated_at: str
    error_message: Optional[str] = None

    model_config = {"json_schema_extra": {"example": {
        "job_id": "abc-123",
        "status": "processing",
        "total_texts": 500,
        "processed_texts": 213,
        "progress_percentage": 42.6,
        "created_at": "2025-06-01T10:00:00",
        "updated_at": "2025-06-01T10:02:15",
        "error_message": None,
    }}}


class TextResultItem(BaseModel):
    id: str
    original_text: str
    sentiment: str = Field(..., description="positive | negative | neutral")
    score: float = Field(..., description="Score de sentimiento [-1.0, 1.0]")
    processed_at: str


class PaginatedResultsResponse(BaseModel):
    job_id: str
    items: list[TextResultItem]
    page: int
    per_page: int
    total_items: int
    total_pages: int
    has_next: bool
    has_prev: bool


class ReportResponse(BaseModel):
    job_id: str
    positive_count: int
    negative_count: int
    neutral_count: int
    total_analyzed: int
    average_score: float
    positive_percentage: float
    negative_percentage: float
    neutral_percentage: float
    cached: bool = Field(..., description="True si vino de caché")


class ErrorResponse(BaseModel):
    detail: str


# ─── Dependency stubs (se conectan al contenedor DI real) ─────────────────────

def get_query_service() -> JobQueryService:
    from dependencies import get_job_query_service
    return get_job_query_service()


def get_current_user_id() -> str:
    from dependencies import get_current_user
    return get_current_user()


# ─── Endpoints ────────────────────────────────────────────────────────────────

@router.get(
    "/{job_id}",
    response_model=JobStatusResponse,
    summary="Estado y progreso de un job",
    responses={404: {"model": ErrorResponse}},
)
def get_job_status(
    job_id: str,
    service: JobQueryService = Depends(get_query_service),
    user_id: str = Depends(get_current_user_id),
):
    """
    Retorna el estado actual del job.
    Cuando está en **processing** incluye `processed_texts` y `progress_percentage`.
    """
    try:
        dto = service.get_job_status(job_id, user_id)
        return JobStatusResponse(**dto.__dict__)
    except JobNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc))


@router.get(
    "/{job_id}/results",
    response_model=PaginatedResultsResponse,
    summary="Resultados paginados del job",
    responses={404: {"model": ErrorResponse}},
)
def get_job_results(
    job_id: str,
    page: int = Query(default=1, ge=1, description="Número de página"),
    per_page: int = Query(default=20, ge=1, le=100, description="Items por página [1-100]"),
    sentiment: Optional[str] = Query(
        default=None,
        pattern="^(positive|negative|neutral)$",
        description="Filtrar por sentimiento",
    ),
    service: JobQueryService = Depends(get_query_service),
    user_id: str = Depends(get_current_user_id),
):
    """Lista paginada de textos con sentimiento y score. Filtrable por sentimiento."""
    try:
        query = ResultsQuery(page=page, per_page=per_page, sentiment_filter=sentiment)
        dto = service.get_paginated_results(job_id, user_id, query)
        return PaginatedResultsResponse(
            job_id=dto.job_id,
            items=[TextResultItem(**item.__dict__) for item in dto.items],
            page=dto.page,
            per_page=dto.per_page,
            total_items=dto.total_items,
            total_pages=dto.total_pages,
            has_next=dto.has_next,
            has_prev=dto.has_prev,
        )
    except JobNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc))
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc))


@router.get(
    "/{job_id}/report",
    response_model=ReportResponse,
    summary="Reporte agregado de sentimientos",
    responses={
        404: {"model": ErrorResponse},
        409: {"model": ErrorResponse, "description": "Job aún en procesamiento"},
    },
)
def get_job_report(
    job_id: str,
    service: JobQueryService = Depends(get_query_service),
    user_id: str = Depends(get_current_user_id),
):
    """
    Retorna conteos por sentimiento, porcentajes y score promedio.
    Solo disponible cuando el job está **completed**.
    Los reportes son inmutables y se sirven desde caché en consultas sucesivas.
    """
    try:
        dto = service.get_aggregated_report(job_id, user_id)
        return ReportResponse(**dto.__dict__)
    except JobNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc))
    except JobStillProcessingError as exc:
        raise HTTPException(status_code=409, detail=str(exc))
