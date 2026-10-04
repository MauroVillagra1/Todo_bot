"""
Modelo MetricaDiaria — contadores livianos por día (OBS-01), sin servicios externos.
Ej.: documentos_procesados, duplicados_descartados, llamadas_llm,
embeddings_generados, consultas, cache_hits, cache_misses, errores_ingesta.
"""
from datetime import date

from sqlalchemy import Date, Integer, String
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base


class MetricaDiaria(Base):
    __tablename__ = "metricas_diarias"

    dia: Mapped[date] = mapped_column(Date, primary_key=True)
    metrica: Mapped[str] = mapped_column(String(50), primary_key=True)
    valor: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
