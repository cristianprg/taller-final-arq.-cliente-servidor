"""
Domain Layer - Interfaces (contratos de repositorios).
Define QUÉ se necesita, no CÓMO se implementa.
El dominio no depende de nada externo.
"""
from abc import ABC, abstractmethod
from typing import Optional
from domain.entities import Job, TextResult, AggregatedReport


class JobRepository(ABC):
    """Contrato para persistencia de Jobs."""

    @abstractmethod
    def get_by_id(self, job_id: str) -> Optional[Job]:
        """Obtiene un job por su ID. Retorna None si no existe."""
        ...

    @abstractmethod
    def get_by_id_and_user(self, job_id: str, user_id: str) -> Optional[Job]:
        """Obtiene un job verificando que pertenezca al usuario (autorización)."""
        ...


class TextResultRepository(ABC):
    """Contrato para persistencia de resultados de texto."""

    @abstractmethod
    def get_paginated_by_job(
        self,
        job_id: str,
        page: int,
        per_page: int,
        sentiment_filter: Optional[str] = None,
    ) -> tuple[list[TextResult], int]:
        """
        Retorna (lista_resultados, total_count).
        Soporta filtro opcional por sentimiento.
        """
        ...

    @abstractmethod
    def get_aggregated_report(self, job_id: str) -> AggregatedReport:
        """
        Calcula el reporte agregado directamente en la BD.
        Más eficiente que traer todos los registros a Python.
        """
        ...
