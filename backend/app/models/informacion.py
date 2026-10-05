"""
Modelos de verificación (etapa 5).

  Informacion   → unidad de información que el chat puede citar, con estado
  Evidencia     → qué publicación/documento de qué fuente la respalda
  Verificacion  → cada evaluación del estado (por qué quedó CONFIRMADA, etc.)
  Historial     → versiones anteriores del contenido (nunca se borra nada)
"""
import enum
from datetime import date, datetime

from sqlalchemy import Date, DateTime, Enum, ForeignKey, Integer, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base


class TipoInformacionEnum(str, enum.Enum):
    INSCRIPCION  = "INSCRIPCION"
    EXAMEN       = "EXAMEN"
    CALENDARIO   = "CALENDARIO"    # calendario académico, horarios, cronogramas
    BECA         = "BECA"
    CONVOCATORIA = "CONVOCATORIA"  # pasantías, empleo, concursos, programas
    EVENTO       = "EVENTO"        # charlas, congresos, cursos, jornadas
    AVISO        = "AVISO"         # avisos a estudiantes de una materia/carrera
    TRAMITE      = "TRAMITE"
    NOTICIA      = "NOTICIA"       # notas institucionales, entrevistas
    OTRO         = "OTRO"


class EstadoInformacionEnum(str, enum.Enum):
    CONFIRMADA     = "CONFIRMADA"
    PROBABLE       = "PROBABLE"
    NO_CONFIRMADA  = "NO_CONFIRMADA"
    CONTRADICTORIA = "CONTRADICTORIA"  # Fase 2
    DESACTUALIZADA = "DESACTUALIZADA"
    REEMPLAZADA    = "REEMPLAZADA"     # Fase 2


class Informacion(Base):
    __tablename__ = "informaciones"

    id: Mapped[int] = mapped_column(primary_key=True)
    tipo: Mapped[TipoInformacionEnum] = mapped_column(
        Enum(TipoInformacionEnum, name="tipoinformacionenum"), nullable=False, index=True
    )
    titulo: Mapped[str] = mapped_column(String(500), nullable=False)
    contenido: Mapped[str] = mapped_column(Text, nullable=False)
    fecha_inicio: Mapped[date | None] = mapped_column(Date)
    fecha_fin: Mapped[date | None] = mapped_column(Date, index=True)
    estado: Mapped[EstadoInformacionEnum] = mapped_column(
        Enum(EstadoInformacionEnum, name="estadoinformacionenum"), nullable=False, index=True
    )
    confianza: Mapped[int] = mapped_column(Integer, nullable=False)  # 0-100
    # Suma de votos de los usuarios (👍 +1, no sirvió -1, incorrecto -2); ajusta el ranking, acotado
    puntaje_votos: Mapped[int] = mapped_column(Integer, default=0, server_default="0", nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False
    )


class Evidencia(Base):
    __tablename__ = "evidencias"

    id: Mapped[int] = mapped_column(primary_key=True)
    informacion_id: Mapped[int] = mapped_column(
        ForeignKey("informaciones.id", ondelete="CASCADE"), nullable=False, index=True
    )
    fuente_id: Mapped[int] = mapped_column(ForeignKey("fuentes.id"), nullable=False)
    documento_id: Mapped[int | None] = mapped_column(ForeignKey("documentos.id"), index=True)
    publicacion_id: Mapped[int | None] = mapped_column(ForeignKey("publicaciones.id"), index=True)
    tipo_de_evidencia: Mapped[str] = mapped_column(String(20), nullable=False, default="TEXTO")


class Verificacion(Base):
    __tablename__ = "verificaciones"

    id: Mapped[int] = mapped_column(primary_key=True)
    informacion_id: Mapped[int] = mapped_column(
        ForeignKey("informaciones.id", ondelete="CASCADE"), nullable=False, index=True
    )
    resultado: Mapped[EstadoInformacionEnum] = mapped_column(
        Enum(EstadoInformacionEnum, name="estadoinformacionenum"), nullable=False
    )
    puntuacion: Mapped[int] = mapped_column(Integer, nullable=False)
    fecha: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    explicacion: Mapped[str] = mapped_column(Text, nullable=False)


class Historial(Base):
    __tablename__ = "historial"

    id: Mapped[int] = mapped_column(primary_key=True)
    informacion_id: Mapped[int] = mapped_column(
        ForeignKey("informaciones.id", ondelete="CASCADE"), nullable=False, index=True
    )
    version: Mapped[int] = mapped_column(Integer, nullable=False)
    contenido_anterior: Mapped[str | None] = mapped_column(Text)
    contenido_nuevo: Mapped[str] = mapped_column(Text, nullable=False)
    motivo: Mapped[str] = mapped_column(String(200), nullable=False)
    fecha: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
