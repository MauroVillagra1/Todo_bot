"""
Modelos del dominio académico base:
  - Materia
  - PeriodoAcademico
  - Comision
  - UsuarioComision (tabla puente alumno ↔ comisión)
"""
import enum
from datetime import date, datetime

from sqlalchemy import (
    Date,
    DateTime,
    Enum,
    ForeignKey,
    String,
    UniqueConstraint,
    func,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base


class DuracionEnum(str, enum.Enum):
    anual = "anual"
    cuatrimestral = "cuatrimestral"


class TipoPeriodoEnum(str, enum.Enum):
    anual = "anual"
    primer_cuatrimestre = "primer_cuatrimestre"
    segundo_cuatrimestre = "segundo_cuatrimestre"


# ── Materia ───────────────────────────────────────────────────────────────────

class Materia(Base):
    __tablename__ = "materias"

    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    nombre: Mapped[str] = mapped_column(String(200), nullable=False)
    # Código corto único, ej: "MAT101"
    codigo: Mapped[str] = mapped_column(String(20), unique=True, nullable=False, index=True)
    duracion: Mapped[DuracionEnum] = mapped_column(Enum(DuracionEnum), nullable=False)

    creado_en: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )

    # Cursadas que instancian esta materia
    cursadas: Mapped[list["Cursada"]] = relationship("Cursada", back_populates="materia")

    def __repr__(self) -> str:
        return f"<Materia {self.codigo} — {self.nombre}>"


# ── PeriodoAcademico ──────────────────────────────────────────────────────────

class PeriodoAcademico(Base):
    __tablename__ = "periodos_academicos"

    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    # Ej: "2025 — Primer Cuatrimestre"
    nombre: Mapped[str] = mapped_column(String(100), nullable=False)
    tipo: Mapped[TipoPeriodoEnum] = mapped_column(Enum(TipoPeriodoEnum), nullable=False)
    fecha_inicio: Mapped[date] = mapped_column(Date, nullable=False)
    fecha_fin: Mapped[date] = mapped_column(Date, nullable=False)

    creado_en: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )

    # Comisiones y cursadas que pertenecen a este período
    comisiones: Mapped[list["Comision"]] = relationship("Comision", back_populates="periodo")
    cursadas: Mapped[list["Cursada"]] = relationship("Cursada", back_populates="periodo")

    def __repr__(self) -> str:
        return f"<PeriodoAcademico {self.nombre}>"


# ── Comision ──────────────────────────────────────────────────────────────────

class Comision(Base):
    __tablename__ = "comisiones"

    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    # Ej: "2K1", "3N2"
    nombre: Mapped[str] = mapped_column(String(50), nullable=False)
    periodo_id: Mapped[int] = mapped_column(ForeignKey("periodos_academicos.id"), nullable=False)

    creado_en: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )

    # Relaciones
    periodo: Mapped["PeriodoAcademico"] = relationship("PeriodoAcademico", back_populates="comisiones")
    alumnos: Mapped[list["UsuarioComision"]] = relationship(
        "UsuarioComision", back_populates="comision", cascade="all, delete-orphan"
    )
    cursadas: Mapped[list["Cursada"]] = relationship("Cursada", back_populates="comision")

    def __repr__(self) -> str:
        return f"<Comision {self.nombre} (periodo_id={self.periodo_id})>"


# ── UsuarioComision (tabla puente alumno ↔ comisión) ─────────────────────────

class UsuarioComision(Base):
    """
    Un alumno puede estar en una sola comisión por período,
    pero el modelo permite múltiples inscripciones históricas.
    La restricción de unicidad por período se aplica a nivel de negocio
    en el servicio correspondiente.
    """
    __tablename__ = "usuario_comision"
    __table_args__ = (
        UniqueConstraint("usuario_id", "comision_id", name="uq_usuario_comision"),
    )

    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    usuario_id: Mapped[int] = mapped_column(ForeignKey("usuarios.id"), nullable=False, index=True)
    comision_id: Mapped[int] = mapped_column(ForeignKey("comisiones.id"), nullable=False, index=True)

    inscripto_en: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )

    # Relaciones
    usuario: Mapped["Usuario"] = relationship("Usuario", back_populates="comisiones")
    comision: Mapped["Comision"] = relationship("Comision", back_populates="alumnos")

    def __repr__(self) -> str:
        return f"<UsuarioComision usuario={self.usuario_id} comision={self.comision_id}>"
