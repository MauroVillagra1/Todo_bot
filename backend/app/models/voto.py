"""
Modelo Voto — opinión de un usuario sobre una respuesta del chat.

  👍 (valor 1)                 → la información usada sube un poco en la búsqueda
  👎 NO_SIRVE (valor -1)       → el chat busca de nuevo excluyendo esas fuentes
  👎 INCORRECTO (valor -1)     → además queda como reporte para que un MOD lo revise

El efecto en la búsqueda está acotado (ver informaciones.puntaje_votos y rag/search.py):
unos pocos votos no pueden esconder información oficial.
"""
import enum
from datetime import datetime

from sqlalchemy import (
    Boolean, DateTime, Enum, ForeignKey, Integer, String, UniqueConstraint, func,
)
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base


class MotivoVotoEnum(str, enum.Enum):
    NO_SIRVE   = "NO_SIRVE"    # no respondía lo que pregunté
    INCORRECTO = "INCORRECTO"  # tiene un dato equivocado


# Peso de cada voto sobre la información que usó la respuesta
PESOS = {None: 1, MotivoVotoEnum.NO_SIRVE: -1, MotivoVotoEnum.INCORRECTO: -2}


def peso(valor: int, motivo: "MotivoVotoEnum | None") -> int:
    return PESOS[None] if valor > 0 else PESOS[motivo or MotivoVotoEnum.NO_SIRVE]


class Voto(Base):
    __tablename__ = "votos"
    __table_args__ = (UniqueConstraint("mensaje_id", "usuario_id", name="uq_voto_mensaje_usuario"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    mensaje_id: Mapped[int] = mapped_column(ForeignKey("mensajes_chat.id", ondelete="CASCADE"),
                                            nullable=False, index=True)
    usuario_id: Mapped[int] = mapped_column(ForeignKey("usuarios.id", ondelete="CASCADE"), nullable=False)
    valor: Mapped[int] = mapped_column(Integer, nullable=False)  # 1 | -1
    motivo: Mapped[MotivoVotoEnum | None] = mapped_column(Enum(MotivoVotoEnum, name="motivovotoenum"))
    comentario: Mapped[str | None] = mapped_column(String(500))
    # Revisión de los reportes INCORRECTO por un MOD
    revisado: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False, index=True)
    revisor_id: Mapped[int | None] = mapped_column(ForeignKey("usuarios.id"))
    resolucion: Mapped[str | None] = mapped_column(String(300))
    creado_en: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
