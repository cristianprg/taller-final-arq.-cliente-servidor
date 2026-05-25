"""
Domain Layer - Entidades del dominio.
Reglas de negocio puras, sin dependencias de frameworks.
"""
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Optional


class JobStatus(str, Enum):
    PENDING = "pending"
    PROCESSING = "processing"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"


class SentimentLabel(str, Enum):
    POSITIVE = "positive"
    NEGATIVE = "negative"
    NEUTRAL = "neutral"


@dataclass
class Job:
    """Entidad de dominio que representa un trabajo de análisis."""
    id: str
    user_id: str
    status: JobStatus
    total_texts: int
    processed_texts: int = 0
    created_at: datetime = field(default_factory=datetime.utcnow)
    updated_at: datetime = field(default_factory=datetime.utcnow)
    error_message: Optional[str] = None

    # Regla de negocio: progreso calculado
    @property
    def progress_percentage(self) -> float:
        if self.total_texts == 0:
            return 0.0
        return round((self.processed_texts / self.total_texts) * 100, 2)

    @property
    def is_completed(self) -> bool:
        return self.status == JobStatus.COMPLETED

    @property
    def is_processing(self) -> bool:
        return self.status == JobStatus.PROCESSING


@dataclass
class TextResult:
    """Entidad de dominio que representa el resultado de análisis de un texto."""
    id: str
    job_id: str
    original_text: str
    sentiment: SentimentLabel
    score: float          # [-1.0, 1.0]
    processed_at: datetime = field(default_factory=datetime.utcnow)

    def __post_init__(self):
        # Invariante de dominio: score debe estar en rango válido
        if not -1.0 <= self.score <= 1.0:
            raise ValueError(f"Score {self.score} fuera del rango [-1.0, 1.0]")


@dataclass(frozen=True)
class AggregatedReport:
    """
    Value Object - Reporte agregado inmutable.
    Regla de negocio DDD: un reporte agregado es inmutable.
    """
    job_id: str
    positive_count: int
    negative_count: int
    neutral_count: int
    average_score: float
    total_analyzed: int

    @property
    def positive_percentage(self) -> float:
        if self.total_analyzed == 0:
            return 0.0
        return round((self.positive_count / self.total_analyzed) * 100, 2)

    @property
    def negative_percentage(self) -> float:
        if self.total_analyzed == 0:
            return 0.0
        return round((self.negative_count / self.total_analyzed) * 100, 2)

    @property
    def neutral_percentage(self) -> float:
        if self.total_analyzed == 0:
            return 0.0
        return round((self.neutral_count / self.total_analyzed) * 100, 2)
