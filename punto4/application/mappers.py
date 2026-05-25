"""
Application Layer - Mappers.

Responsabilidad única: traducir entre entidades de dominio y DTOs.

JUSTIFICACIÓN TÉCNICA:
- Centraliza la lógica de transformación (no dispersa en endpoints ni entidades)
- Si el formato de la API cambia, solo cambia el mapper
- Facilita testing independiente de la transformación
"""
import math
from domain.entities import Job, TextResult, AggregatedReport
from application.dtos import (
    JobStatusDTO,
    TextResultDTO,
    PaginatedResultsDTO,
    ReportDTO,
)


class JobMapper:
    """Mapea entidades Job a DTOs."""

    @staticmethod
    def to_status_dto(job: Job) -> JobStatusDTO:
        return JobStatusDTO(
            job_id=job.id,
            status=job.status.value,
            total_texts=job.total_texts,
            processed_texts=job.processed_texts,
            progress_percentage=job.progress_percentage,
            created_at=job.created_at.isoformat(),
            updated_at=job.updated_at.isoformat(),
            error_message=job.error_message,
        )


class TextResultMapper:
    """Mapea entidades TextResult a DTOs."""

    @staticmethod
    def to_dto(result: TextResult) -> TextResultDTO:
        return TextResultDTO(
            id=result.id,
            original_text=result.original_text,
            sentiment=result.sentiment.value,
            score=round(result.score, 4),
            processed_at=result.processed_at.isoformat(),
        )

    @staticmethod
    def to_paginated_dto(
        job_id: str,
        results: list[TextResult],
        total: int,
        page: int,
        per_page: int,
    ) -> PaginatedResultsDTO:
        total_pages = math.ceil(total / per_page) if per_page > 0 else 0
        return PaginatedResultsDTO(
            job_id=job_id,
            items=[TextResultMapper.to_dto(r) for r in results],
            page=page,
            per_page=per_page,
            total_items=total,
            total_pages=total_pages,
            has_next=page < total_pages,
            has_prev=page > 1,
        )


class ReportMapper:
    """Mapea AggregatedReport (Value Object de dominio) a ReportDTO."""

    @staticmethod
    def to_dto(report: AggregatedReport, cached: bool = False) -> ReportDTO:
        return ReportDTO(
            job_id=report.job_id,
            positive_count=report.positive_count,
            negative_count=report.negative_count,
            neutral_count=report.neutral_count,
            total_analyzed=report.total_analyzed,
            average_score=round(report.average_score, 4),
            positive_percentage=report.positive_percentage,
            negative_percentage=report.negative_percentage,
            neutral_percentage=report.neutral_percentage,
            cached=cached,
        )
