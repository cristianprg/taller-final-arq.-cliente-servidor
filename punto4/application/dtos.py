"""
Application Layer - DTOs (Data Transfer Objects).

Separan la representación de la API de las entidades de dominio.
Patrón DTO: define exactamente qué datos viajan entre capas.

JUSTIFICACIÓN TÉCNICA:
- Evita exposición directa de entidades de dominio en la API
- Permite versionar la API sin modificar el dominio
- Facilita la validación y serialización
"""
from dataclasses import dataclass
from typing import Optional
from domain.entities import JobStatus


# ─── Query Objects ────────────────────────────────────────────────────────────
# Patrón Query Object: encapsula parámetros de consulta con validación.

@dataclass(frozen=True)
class PaginationQuery:
    """Value Object para paginación con validación de invariantes."""
    page: int = 1
    per_page: int = 20

    def __post_init__(self):
        if self.page < 1:
            raise ValueError("page debe ser >= 1")
        if not 1 <= self.per_page <= 100:
            raise ValueError("per_page debe estar entre 1 y 100")

    @property
    def offset(self) -> int:
        return (self.page - 1) * self.per_page


@dataclass(frozen=True)
class ResultsQuery(PaginationQuery):
    """Query object para consulta de resultados con filtros opcionales."""
    sentiment_filter: Optional[str] = None


# ─── DTOs de respuesta ────────────────────────────────────────────────────────

@dataclass
class JobStatusDTO:
    """DTO para el estado y progreso de un job."""
    job_id: str
    status: str
    total_texts: int
    processed_texts: int
    progress_percentage: float
    created_at: str
    updated_at: str
    error_message: Optional[str] = None


@dataclass
class TextResultDTO:
    """DTO para un resultado individual de texto."""
    id: str
    original_text: str
    sentiment: str
    score: float
    processed_at: str


@dataclass
class PaginatedResultsDTO:
    """DTO para resultados paginados. Incluye metadatos de paginación."""
    job_id: str
    items: list[TextResultDTO]
    page: int
    per_page: int
    total_items: int
    total_pages: int
    has_next: bool
    has_prev: bool


@dataclass
class ReportDTO:
    """
    DTO para reporte agregado.
    Incluye conteos absolutos, porcentajes y promedio de score.
    """
    job_id: str
    positive_count: int
    negative_count: int
    neutral_count: int
    total_analyzed: int
    average_score: float
    positive_percentage: float
    negative_percentage: float
    neutral_percentage: float
    cached: bool = False   # indica si vino de caché (transparencia al cliente)
