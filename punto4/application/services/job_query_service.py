"""
Application Layer - JobQueryService.

Orquesta los casos de uso de consulta definidos en la Historia #4:
  1. Obtener estado y progreso de un trabajo
  2. Obtener resultados paginados (texto + sentimiento)
  3. Obtener reporte agregado con caché

DECISIONES DE DISEÑO:
- Thread-safe: usa threading.Lock para proteger el caché en memoria
- Cache bajo demanda: solo para jobs completados (sus reportes son inmutables)
- El servicio no conoce HTTP ni SQLAlchemy; depende de abstracciones (interfaces)
"""
import logging
import threading
from typing import Optional

from domain.entities import JobStatus
from domain.interfaces import JobRepository, TextResultRepository
from application.dtos import (
    JobStatusDTO,
    PaginatedResultsDTO,
    ReportDTO,
    ResultsQuery,
)
from application.mappers import JobMapper, TextResultMapper, ReportMapper

logger = logging.getLogger(__name__)


class JobNotFoundError(Exception):
    """El job no existe o no pertenece al usuario autenticado."""


class JobStillProcessingError(Exception):
    """Se solicita reporte de un job que aún no completó."""


class JobQueryService:
    """
    Servicio de aplicación para consultas de jobs y sus resultados.
    
    Patrón: Facade sobre los repositorios de dominio.
    Concurrencia: thread-safe mediante lock para caché en memoria.
    """

    def __init__(
        self,
        job_repo: JobRepository,
        result_repo: TextResultRepository,
        cache_max_size: int = 256,
    ):
        self._job_repo = job_repo
        self._result_repo = result_repo
        # Caché en memoria para reportes de jobs completados (inmutables)
        self._report_cache: dict[str, ReportDTO] = {}
        self._cache_lock = threading.Lock()
        self._cache_max_size = cache_max_size

    # ── Caso de uso 1: Estado y progreso ─────────────────────────────────────

    def get_job_status(self, job_id: str, user_id: str) -> JobStatusDTO:
        """
        Retorna estado actual y progreso de un job.
        Si está en processing, incluye processed_texts/total_texts.
        """
        job = self._job_repo.get_by_id_and_user(job_id, user_id)
        if job is None:
            raise JobNotFoundError(f"Job '{job_id}' no encontrado para usuario '{user_id}'")

        logger.debug("get_job_status: job_id=%s status=%s", job_id, job.status)
        return JobMapper.to_status_dto(job)

    # ── Caso de uso 2: Resultados paginados ───────────────────────────────────

    def get_paginated_results(
        self,
        job_id: str,
        user_id: str,
        query: ResultsQuery,
    ) -> PaginatedResultsDTO:
        """
        Retorna resultados paginados de un job.
        Aplica filtros opcionales por sentimiento.
        """
        job = self._job_repo.get_by_id_and_user(job_id, user_id)
        if job is None:
            raise JobNotFoundError(f"Job '{job_id}' no encontrado para usuario '{user_id}'")

        results, total = self._result_repo.get_paginated_by_job(
            job_id=job_id,
            page=query.page,
            per_page=query.per_page,
            sentiment_filter=query.sentiment_filter,
        )

        logger.debug(
            "get_paginated_results: job_id=%s page=%d total=%d",
            job_id, query.page, total,
        )
        return TextResultMapper.to_paginated_dto(
            job_id=job_id,
            results=results,
            total=total,
            page=query.page,
            per_page=query.per_page,
        )

    # ── Caso de uso 3: Reporte agregado con caché ─────────────────────────────

    def get_aggregated_report(self, job_id: str, user_id: str) -> ReportDTO:
        """
        Retorna reporte agregado (counts + average_score).
        
        Política de caché:
        - Solo cachea jobs COMPLETADOS (reporte inmutable → regla DDD)
        - Thread-safe: usa Lock para lectura/escritura del diccionario
        """
        job = self._job_repo.get_by_id_and_user(job_id, user_id)
        if job is None:
            raise JobNotFoundError(f"Job '{job_id}' no encontrado para usuario '{user_id}'")

        if not job.is_completed:
            raise JobStillProcessingError(
                f"Job '{job_id}' aún no está completado (status: {job.status.value}). "
                "El reporte solo está disponible cuando el job finaliza."
            )

        # Intentar leer del caché (thread-safe)
        with self._cache_lock:
            if job_id in self._report_cache:
                logger.debug("cache HIT para reporte job_id=%s", job_id)
                cached_dto = self._report_cache[job_id]
                cached_dto.cached = True
                return cached_dto

        # Cache MISS: calcular desde BD
        logger.debug("cache MISS para reporte job_id=%s, calculando...", job_id)
        report = self._result_repo.get_aggregated_report(job_id)
        dto = ReportMapper.to_dto(report, cached=False)

        # Guardar en caché con LRU simple
        with self._cache_lock:
            if len(self._report_cache) >= self._cache_max_size:
                oldest_key = next(iter(self._report_cache))
                del self._report_cache[oldest_key]
                logger.debug("Caché lleno, eviccionado job_id=%s", oldest_key)
            self._report_cache[job_id] = dto

        return dto

    def invalidate_cache(self, job_id: str) -> None:
        """Invalida entrada de caché (útil en tests o re-runs)."""
        with self._cache_lock:
            self._report_cache.pop(job_id, None)

    @property
    def cache_size(self) -> int:
        with self._cache_lock:
            return len(self._report_cache)
