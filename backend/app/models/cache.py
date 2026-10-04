"""
Modelo CacheRespuesta — respuestas del chat reutilizables (RAG-05).
La clave incluye una "versión de los datos": cuando la ingesta cambia algo,
las claves viejas dejan de coincidir solas, sin borrar nada a mano.
"""
from datetime import datetime

from sqlalchemy import JSON, DateTime, Integer, String, func
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base


class CacheRespuesta(Base):
    __tablename__ = "cache_respuestas"

    clave: Mapped[str] = mapped_column(String(64), primary_key=True)
    respuesta: Mapped[dict] = mapped_column(JSON().with_variant(JSONB(), "postgresql"), nullable=False)
    expira_en: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, index=True)
    hits: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    creado_en: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
