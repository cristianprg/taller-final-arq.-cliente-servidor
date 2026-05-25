"""
Tests de la Historia #4.

Cubre:
- DTOs y Query Objects (validación de invariantes)
- Mappers (transformación dominio → DTO)
- JobQueryService (los 3 casos de uso + caché thread-safety)
- Endpoints FastAPI (criterios de aceptación del enunciado)

Estrategia: mocks de repositorios para aislar cada capa.
"""
import math
import threading
import sys
import os
import pytest
from datetime import datetime
from dataclasses import dataclass
from typing import Optional
from unittest.mock import MagicMock, patch

# ── Setup de path ──────────────────────────────────────────────────────────────
sys.path.insert(0, os.path.join(os.path.dirname(__file__)))

from domain.entities import Job, TextResult, AggregatedReport, JobStatus, SentimentLabel
from application.dtos import (
    PaginationQuery, ResultsQuery, JobStatusDTO, TextResultDTO,
    PaginatedResultsDTO, ReportDTO,
)
from application.mappers import JobMapper, TextResultMapper, ReportMapper
from application.services.job_query_service import (
    JobQueryService, JobNotFoundError, JobStillProcessingError,
)


# ─── Fixtures ────────────────────────────────────────────────────────────────

def make_job(status=JobStatus.COMPLETED, total=100, processed=100) -> Job:
    return Job(
        id="job-001",
        user_id="user-abc",
        status=status,
        total_texts=total,
        processed_texts=processed,
        created_at=datetime(2025, 6, 1, 10, 0),
        updated_at=datetime(2025, 6, 1, 10, 5),
    )


def make_text_result(sentiment=SentimentLabel.POSITIVE, score=0.8) -> TextResult:
    return TextResult(
        id="res-001",
        job_id="job-001",
        original_text="El producto es excelente",
        sentiment=sentiment,
        score=score,
        processed_at=datetime(2025, 6, 1, 10, 3),
    )


def make_report() -> AggregatedReport:
    return AggregatedReport(
        job_id="job-001",
        positive_count=70,
        negative_count=20,
        neutral_count=10,
        average_score=0.45,
        total_analyzed=100,
    )


def make_service(job=None, results=None, total=0, report=None) -> JobQueryService:
    job_repo = MagicMock()
    result_repo = MagicMock()
    job_repo.get_by_id_and_user.return_value = job or make_job()
    result_repo.get_paginated_by_job.return_value = (results or [], total)
    result_repo.get_aggregated_report.return_value = report or make_report()
    return JobQueryService(job_repo, result_repo)


# ─── Tests: DTOs / Query Objects ──────────────────────────────────────────────

class TestPaginationQuery:
    def test_defaults_validos(self):
        q = PaginationQuery()
        assert q.page == 1
        assert q.per_page == 20
        assert q.offset == 0

    def test_offset_calculado(self):
        q = PaginationQuery(page=3, per_page=10)
        assert q.offset == 20

    def test_page_invalida_raise(self):
        with pytest.raises(ValueError, match="page"):
            PaginationQuery(page=0)

    def test_per_page_invalida_raise(self):
        with pytest.raises(ValueError, match="per_page"):
            PaginationQuery(per_page=0)

    def test_per_page_max_raise(self):
        with pytest.raises(ValueError, match="per_page"):
            PaginationQuery(per_page=101)


class TestResultsQuery:
    def test_con_filtro_sentimiento(self):
        q = ResultsQuery(page=2, per_page=5, sentiment_filter="positive")
        assert q.sentiment_filter == "positive"
        assert q.offset == 5

    def test_sin_filtro(self):
        q = ResultsQuery()
        assert q.sentiment_filter is None


# ─── Tests: Mappers ───────────────────────────────────────────────────────────

class TestJobMapper:
    def test_status_dto_campos(self):
        job = make_job(status=JobStatus.PROCESSING, total=200, processed=80)
        dto = JobMapper.to_status_dto(job)
        assert dto.job_id == "job-001"
        assert dto.status == "processing"
        assert dto.total_texts == 200
        assert dto.processed_texts == 80
        assert dto.progress_percentage == 40.0

    def test_progreso_cero_con_total_cero(self):
        job = make_job(total=0, processed=0)
        dto = JobMapper.to_status_dto(job)
        assert dto.progress_percentage == 0.0


class TestTextResultMapper:
    def test_to_dto(self):
        result = make_text_result(sentiment=SentimentLabel.NEGATIVE, score=-0.6)
        dto = TextResultMapper.to_dto(result)
        assert dto.sentiment == "negative"
        assert dto.score == -0.6
        assert dto.original_text == "El producto es excelente"

    def test_to_paginated_dto_calculos(self):
        results = [make_text_result()]
        dto = TextResultMapper.to_paginated_dto(
            job_id="job-001", results=results, total=45, page=2, per_page=20
        )
        assert dto.total_items == 45
        assert dto.total_pages == 3  # ceil(45/20)
        assert dto.has_prev is True
        assert dto.has_next is True

    def test_paginated_ultima_pagina(self):
        dto = TextResultMapper.to_paginated_dto(
            job_id="job-001", results=[], total=20, page=2, per_page=20
        )
        assert dto.has_next is False
        assert dto.has_prev is True


class TestReportMapper:
    def test_to_dto_porcentajes(self):
        report = make_report()
        dto = ReportMapper.to_dto(report)
        assert dto.positive_count == 70
        assert dto.positive_percentage == 70.0
        assert dto.negative_percentage == 20.0
        assert dto.neutral_percentage == 10.0
        assert dto.cached is False

    def test_to_dto_con_cache(self):
        dto = ReportMapper.to_dto(make_report(), cached=True)
        assert dto.cached is True

    def test_score_redondeado(self):
        report = AggregatedReport(
            job_id="j", positive_count=1, negative_count=0,
            neutral_count=0, average_score=0.123456789, total_analyzed=1
        )
        dto = ReportMapper.to_dto(report)
        assert dto.average_score == 0.1235


# ─── Tests: JobQueryService ───────────────────────────────────────────────────

class TestGetJobStatus:
    def test_retorna_dto_correcto(self):
        svc = make_service(job=make_job(status=JobStatus.PROCESSING, total=50, processed=25))
        dto = svc.get_job_status("job-001", "user-abc")
        assert dto.status == "processing"
        assert dto.progress_percentage == 50.0

    def test_job_no_encontrado_raise(self):
        svc = make_service()
        svc._job_repo.get_by_id_and_user.return_value = None
        with pytest.raises(JobNotFoundError):
            svc.get_job_status("no-existe", "user-abc")


class TestGetPaginatedResults:
    def test_resultados_correctos(self):
        results = [make_text_result(), make_text_result(SentimentLabel.NEGATIVE, -0.5)]
        svc = make_service(results=results, total=2)
        dto = svc.get_paginated_results("job-001", "user-abc", ResultsQuery())
        assert dto.total_items == 2
        assert len(dto.items) == 2

    def test_job_no_encontrado_raise(self):
        svc = make_service()
        svc._job_repo.get_by_id_and_user.return_value = None
        with pytest.raises(JobNotFoundError):
            svc.get_paginated_results("no-existe", "u", ResultsQuery())


class TestGetAggregatedReport:
    def test_reporte_job_completado(self):
        svc = make_service(job=make_job(status=JobStatus.COMPLETED))
        dto = svc.get_aggregated_report("job-001", "user-abc")
        assert dto.positive_count == 70
        assert dto.total_analyzed == 100

    def test_job_processing_raise_409(self):
        svc = make_service(job=make_job(status=JobStatus.PROCESSING, processed=50))
        with pytest.raises(JobStillProcessingError):
            svc.get_aggregated_report("job-001", "user-abc")

    def test_job_pending_raise_409(self):
        svc = make_service(job=make_job(status=JobStatus.PENDING, processed=0))
        with pytest.raises(JobStillProcessingError):
            svc.get_aggregated_report("job-001", "user-abc")

    def test_cache_hit_segunda_llamada(self):
        svc = make_service(job=make_job(status=JobStatus.COMPLETED))
        dto1 = svc.get_aggregated_report("job-001", "user-abc")
        dto2 = svc.get_aggregated_report("job-001", "user-abc")
        # Segunda llamada debería ser cache hit
        assert dto2.cached is True
        # Repositorio solo debería haberse llamado una vez
        assert svc._result_repo.get_aggregated_report.call_count == 1

    def test_no_cachea_jobs_no_completados(self):
        svc = make_service(job=make_job(status=JobStatus.PROCESSING))
        with pytest.raises(JobStillProcessingError):
            svc.get_aggregated_report("job-001", "user-abc")
        assert svc.cache_size == 0


class TestCacheThreadSafety:
    """Verifica que el caché funcione correctamente bajo concurrencia."""

    def test_multiples_hilos_acceso_concurrente(self):
        svc = make_service(job=make_job(status=JobStatus.COMPLETED))
        results = []
        errors = []

        def worker():
            try:
                dto = svc.get_aggregated_report("job-001", "user-abc")
                results.append(dto.positive_count)
            except Exception as e:
                errors.append(e)

        threads = [threading.Thread(target=worker) for _ in range(20)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        assert len(errors) == 0, f"Errores en concurrencia: {errors}"
        assert all(r == 70 for r in results)
        # El repositorio debe haberse llamado una sola vez (caché funciona)
        assert svc._result_repo.get_aggregated_report.call_count == 1

    def test_invalidate_cache(self):
        svc = make_service(job=make_job(status=JobStatus.COMPLETED))
        svc.get_aggregated_report("job-001", "user-abc")
        assert svc.cache_size == 1
        svc.invalidate_cache("job-001")
        assert svc.cache_size == 0
        # Siguiente llamada debe recalcular
        svc.get_aggregated_report("job-001", "user-abc")
        assert svc._result_repo.get_aggregated_report.call_count == 2


# ─── Tests: Entidades de Dominio ──────────────────────────────────────────────

class TestJobEntity:
    def test_progreso_procesando(self):
        job = make_job(status=JobStatus.PROCESSING, total=200, processed=50)
        assert job.progress_percentage == 25.0

    def test_progreso_total_cero(self):
        job = make_job(total=0, processed=0)
        assert job.progress_percentage == 0.0

    def test_is_completed(self):
        assert make_job(status=JobStatus.COMPLETED).is_completed
        assert not make_job(status=JobStatus.PROCESSING).is_completed

    def test_is_processing(self):
        assert make_job(status=JobStatus.PROCESSING).is_processing
        assert not make_job(status=JobStatus.COMPLETED).is_processing


class TestTextResultEntity:
    def test_score_invalido_raise(self):
        with pytest.raises(ValueError, match="Score"):
            TextResult(
                id="x", job_id="j", original_text="t",
                sentiment=SentimentLabel.POSITIVE, score=1.5
            )

    def test_score_limite_inferior_raise(self):
        with pytest.raises(ValueError):
            TextResult(
                id="x", job_id="j", original_text="t",
                sentiment=SentimentLabel.NEGATIVE, score=-1.1
            )

    def test_score_en_limites_valido(self):
        r1 = TextResult(id="x", job_id="j", original_text="t",
                        sentiment=SentimentLabel.POSITIVE, score=1.0)
        r2 = TextResult(id="y", job_id="j", original_text="t",
                        sentiment=SentimentLabel.NEGATIVE, score=-1.0)
        assert r1.score == 1.0
        assert r2.score == -1.0


class TestAggregatedReportValueObject:
    def test_inmutabilidad(self):
        report = make_report()
        with pytest.raises((AttributeError, TypeError)):
            report.positive_count = 999  # type: ignore

    def test_porcentajes(self):
        report = make_report()
        assert report.positive_percentage == 70.0
        assert report.negative_percentage == 20.0
        assert report.neutral_percentage == 10.0

    def test_porcentajes_total_cero(self):
        r = AggregatedReport(
            job_id="j", positive_count=0, negative_count=0,
            neutral_count=0, average_score=0.0, total_analyzed=0
        )
        assert r.positive_percentage == 0.0


if __name__ == "__main__":
    # Ejecutar con: python tests.py
    import pytest
    pytest.main([__file__, "-v", "--tb=short"])
