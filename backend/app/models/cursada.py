"""
Modelos del dominio de cursadas:
  - Cursada         → instancia real de una materia en una comisión y período
  - CursadaProfesor → tabla puente cursada ↔ profesor (1 o varios)
  - CursadaExcepcion → cambios temporales (suspensiones, reubicaciones)
"""
import enum
from datetime import date, datetime

from sqlalchemy import (
    Date,
    DateTime,
    Enum,
    ForeignKey,
    String,
    Text,
    UniqueConstraint,
    func,
)
from sqlalchemy.dialects.postgresql import JSON
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base


class ModalidadEnum(str, enum.Enum):
    presencial = "presencial"
    virtual = "virtual"
    hibrida = "hibrida"


class TipoExcepcionEnum(str, enum.Enum):
    reubicacion = "reubicacion"   # clase en otra aula u horario temporalmente
    suspension = "suspension"      # clase cancelada


# ── Cursada ───────────────────────────────────────────────────────────────────

class Cursada(Base):
    """
    Instancia concreta de una materia dictada en una comisión
    durante un período académico. Nunca se borra (historial permanente).
    """
    __tablename__ = "cursadas"

    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    materia_id: Mapped[int] = mapped_column(ForeignKey("materias.id"), nullable=False, index=True)
    comision_id: Mapped[int] = mapped_column(ForeignKey("comisiones.id"), nullable=False, index=True)
    periodo_id: Mapped[int] = mapped_column(ForeignKey("periodos_academicos.id"), nullable=False, index=True)

    aula: Mapped[str | None] = mapped_column(String(50))
    # Ej: "Lunes y Miércoles 18:00–20:00" — texto libre para flexibilidad
    horario: Mapped[str | None] = mapped_column(String(200))
    modalidad: Mapped[ModalidadEnum] = mapped_column(
        Enum(ModalidadEnum), default=ModalidadEnum.presencial, nullable=False
    )
    # Campo JSON libre para datos adicionales (link de aula virtual, etc.)
    info_adicional: Mapped[dict | None] = mapped_column(JSON)

    creado_en: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    actualizado_en: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False,
    )

    # Relaciones
    materia: Mapped["Materia"] = relationship("Materia", back_populates="cursadas")
    comision: Mapped["Comision"] = relationship("Comision", back_populates="cursadas")
    periodo: Mapped["PeriodoAcademico"] = relationship("PeriodoAcademico", back_populates="cursadas")
    profesores: Mapped[list["CursadaProfesor"]] = relationship(
        "CursadaProfesor", back_populates="cursada", cascade="all, delete-orphan"
    )
    excepciones: Mapped[list["CursadaExcepcion"]] = relationship(
        "CursadaExcepcion", back_populates="cursada", cascade="all, delete-orphan"
    )
    materiales: Mapped[list["MaterialApoyo"]] = relationship(
        "MaterialApoyo", back_populates="cursada", cascade="all, delete-orphan"
    )

    def __repr__(self) -> str:
        return f"<Cursada id={self.id} materia={self.materia_id} comision={self.comision_id}>"


# ── CursadaProfesor (tabla puente cursada ↔ profesor) ────────────────────────

class CursadaProfesor(Base):
    """Permite asignar uno o varios profesores a una misma cursada."""
    __tablename__ = "cursada_profesor"
    __table_args__ = (
        UniqueConstraint("cursada_id", "profesor_id", name="uq_cursada_profesor"),
    )

    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    cursada_id: Mapped[int] = mapped_column(ForeignKey("cursadas.id"), nullable=False, index=True)
    profesor_id: Mapped[int] = mapped_column(ForeignKey("usuarios.id"), nullable=False, index=True)

    asignado_en: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )

    # Relaciones
    cursada: Mapped["Cursada"] = relationship("Cursada", back_populates="profesores")
    profesor: Mapped["Usuario"] = relationship("Usuario", back_populates="cursadas_como_profesor")

    def __repr__(self) -> str:
        return f"<CursadaProfesor cursada={self.cursada_id} profesor={self.profesor_id}>"


# ── CursadaExcepcion ──────────────────────────────────────────────────────────

class CursadaExcepcion(Base):
    """
    Representa un cambio puntual (UN DÍA) sobre una cursada:
      - reubicacion: la clase se mueve a otra aula u horario ese día.
      - suspension:  la clase se cancela ese día.
    """
    __tablename__ = "cursada_excepciones"

    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    cursada_id: Mapped[int] = mapped_column(ForeignKey("cursadas.id"), nullable=False, index=True)
    tipo: Mapped[TipoExcepcionEnum] = mapped_column(Enum(TipoExcepcionEnum), nullable=False)
    motivo: Mapped[str | None] = mapped_column(Text)
    # Un solo día — no hay rango
    fecha: Mapped[date] = mapped_column(Date, nullable=False, index=True)

    # Datos alternativos para reubicaciones (nulos en suspensiones)
    aula_nueva: Mapped[str | None] = mapped_column(String(50))
    horario_nuevo: Mapped[str | None] = mapped_column(String(200))

    cargado_por: Mapped[int] = mapped_column(ForeignKey("usuarios.id"), nullable=False)

    creado_en: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )

    cursada: Mapped["Cursada"] = relationship("Cursada", back_populates="excepciones")
    autor: Mapped["Usuario"] = relationship("Usuario", foreign_keys=[cargado_por])

    def __repr__(self) -> str:
        return f"<CursadaExcepcion cursada={self.cursada_id} tipo={self.tipo} fecha={self.fecha}>"
