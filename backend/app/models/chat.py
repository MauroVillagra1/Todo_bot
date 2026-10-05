"""
Modelo MensajeChat — historial de conversaciones persistido en Postgres.
En serverless (Vercel) no hay memoria compartida entre invocaciones,
así que el historial y el límite de consultas por minuto se apoyan en esta tabla.
"""
from datetime import datetime

from sqlalchemy import JSON, DateTime, ForeignKey, Index, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base


class MensajeChat(Base):
    __tablename__ = "mensajes_chat"
    __table_args__ = (
        # Usado por el rate limit: mensajes de un usuario en el último minuto
        Index("ix_mensajes_chat_usuario_fecha", "usuario_id", "creado_en"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    conversacion_id: Mapped[str] = mapped_column(String(36), nullable=False, index=True)
    usuario_id: Mapped[int] = mapped_column(
        ForeignKey("usuarios.id", ondelete="CASCADE"), nullable=False
    )
    # "user" | "assistant" — mismo formato que la API de chat de los LLM
    rol: Mapped[str] = mapped_column(String(10), nullable=False)
    contenido: Mapped[str] = mapped_column(Text, nullable=False)
    # Respuestas: qué informaciones usó (para los votos y para "buscar en otras fuentes")
    informacion_ids: Mapped[list | None] = mapped_column(JSON)
    creado_en: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )

    def __repr__(self) -> str:
        return f"<MensajeChat conv={self.conversacion_id} rol={self.rol}>"
