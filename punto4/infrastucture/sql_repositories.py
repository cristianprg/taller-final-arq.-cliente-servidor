"""
Infrastructure Layer - Persistencia SQL con SQLAlchemy.

Implementa las interfaces de dominio con SQLAlchemy (ORM).
Esta capa conoce los detalles de BD, pero las capas superiores no.

DECISIONES DE DISEÑO:
- scoped_session → thread-safe: cada hilo obtiene su propia sesión
- Índices en job_id y status → consultas < 200ms (criterio de aceptación)
- get_aggregated_report usa SQL agregado (COUNT, AVG) en lugar de traer
  todos los registros → eficiente hasta millones de filas
"""
import uuid
from datetime import datetime
from typing import Optional

from sqlalchemy import (
    Column, String, Integer, Float, Enum as SAEnum,
    DateTime, ForeignKey, Index, func, create_engine, text,
)
from sqlalchemy.orm import DeclarativeBase, Session, scoped_session, sessionmaker

from domain.entities import (
    Job, JobStatus, TextResult, SentimentLabel, AggregatedReport,
)
from domain.interfaces import JobRepository, TextResultRepository


# ─── ORM Models ──────────────────────────────────────────────────────────────

class Base(DeclarativeBase):
    pass


class JobModel(Base):
    __tablename__ = "jobs"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    user_id = Column(String(36), nullable=False, index=True)
    status = Column(SAEnum(JobStatus), nullable=False, default=JobStatus.PENDING, index=True)
    total_texts = Column(Integer, nullable=False, default=0)
    processed_texts = Column(Integer, nullable=False, default=0)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)
    error_message = Column(String(1024), nullable=True)

    # Índice compuesto para consultas por usuario + estado
    __table_args__ = (
        Index("ix_jobs_user_status", "user_id", "status"),
    )


class TextResultModel(Base):
    __tablename__ = "text_results"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    job_id = Column(String(36), ForeignKey("jobs.id", ondelete="CASCADE"), nullable=False, index=True)
    original_text = Column(String(5000), nullable=False)
    sentiment = Column(SAEnum(SentimentLabel), nullable=False, index=True)
    score = Column(Float, nullable=False)
    processed_at = Column(DateTime, default=datetime.utcnow, nullable=False)

    # Índice compuesto para paginación filtrada
    __table_args__ = (
        Index("ix_results_job_sentiment", "job_id", "sentiment"),
    )


# ─── Mappers ORM → Domain ─────────────────────────────────────────────────────

def _model_to_job(m: JobModel) -> Job:
    return Job(
        id=m.id,
        user_id=m.user_id,
        status=m.status,
        total_texts=m.total_texts,
        processed_texts=m.processed_texts,
        created_at=m.created_at,
        updated_at=m.updated_at,
        error_message=m.error_message,
    )


def _model_to_text_result(m: TextResultModel) -> TextResult:
    return TextResult(
        id=m.id,
        job_id=m.job_id,
        original_text=m.original_text,
        sentiment=m.sentiment,
        score=m.score,
        processed_at=m.processed_at,
    )


# ─── Repository Implementations ───────────────────────────────────────────────

class SQLJobRepository(JobRepository):
    """
    Implementación SQL del repositorio de Jobs.
    Usa scoped_session para thread-safety.
    """

    def __init__(self, session: scoped_session):
        self._session = session

    def get_by_id(self, job_id: str) -> Optional[Job]:
        model = self._session.get(JobModel, job_id)
        return _model_to_job(model) if model else None

    def get_by_id_and_user(self, job_id: str, user_id: str) -> Optional[Job]:
        model = (
            self._session.query(JobModel)
            .filter(JobModel.id == job_id, JobModel.user_id == user_id)
            .first()
        )
        return _model_to_job(model) if model else None


class SQLTextResultRepository(TextResultRepository):
    """
    Implementación SQL del repositorio de resultados de texto.
    Las agregaciones se hacen en SQL para máxima eficiencia.
    """

    def __init__(self, session: scoped_session):
        self._session = session

    def get_paginated_by_job(
        self,
        job_id: str,
        page: int,
        per_page: int,
        sentiment_filter: Optional[str] = None,
    ) -> tuple[list[TextResult], int]:
        query = self._session.query(TextResultModel).filter(
            TextResultModel.job_id == job_id
        )

        if sentiment_filter:
            query = query.filter(TextResultModel.sentiment == sentiment_filter)

        total = query.count()
        offset = (page - 1) * per_page
        models = query.order_by(TextResultModel.processed_at).offset(offset).limit(per_page).all()

        return [_model_to_text_result(m) for m in models], total

    def get_aggregated_report(self, job_id: str) -> AggregatedReport:
        """
        Usa SQL agregado: COUNT con CASE WHEN + AVG.
        Eficiente incluso con > 10k registros.
        """
        result = self._session.query(
            func.count(TextResultModel.id).label("total"),
            func.sum(
                func.case((TextResultModel.sentiment == SentimentLabel.POSITIVE, 1), else_=0)
            ).label("positive"),
            func.sum(
                func.case((TextResultModel.sentiment == SentimentLabel.NEGATIVE, 1), else_=0)
            ).label("negative"),
            func.sum(
                func.case((TextResultModel.sentiment == SentimentLabel.NEUTRAL, 1), else_=0)
            ).label("neutral"),
            func.avg(TextResultModel.score).label("avg_score"),
        ).filter(TextResultModel.job_id == job_id).one()

        return AggregatedReport(
            job_id=job_id,
            positive_count=int(result.positive or 0),
            negative_count=int(result.negative or 0),
            neutral_count=int(result.neutral or 0),
            average_score=float(result.avg_score or 0.0),
            total_analyzed=int(result.total or 0),
        )


# ─── Factory / DB Setup ───────────────────────────────────────────────────────

def create_db_session(database_url: str) -> scoped_session:
    """
    Crea una scoped_session thread-safe.
    Cada hilo obtiene su propia sesión SQLAlchemy.
    """
    engine = create_engine(
        database_url,
        pool_pre_ping=True,         # verifica conexión antes de usar
        pool_size=10,               # conexiones concurrentes
        max_overflow=20,
    )
    Base.metadata.create_all(engine)
    factory = sessionmaker(bind=engine, autocommit=False, autoflush=False)
    return scoped_session(factory)
