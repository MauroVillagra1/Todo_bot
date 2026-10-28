"""
Mesas de examen final (solo ADMIN las edita; el chat las responde con SQL, sin LLM).

  MesaFecha   → cada llamado de la Mesa 1, 2 o 3: cierre de inscripción y fecha del examen
  MesaMateria → en qué mesa se rinde cada materia, con su tribunal (presidente y vocales),
                sede (Casa Central o Anexo Concepción) y hora de inicio
"""
from datetime import date

from sqlalchemy import Date, Integer, String
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base


class MesaFecha(Base):
    __tablename__ = "mesas_fechas"

    id: Mapped[int] = mapped_column(primary_key=True)
    mesa: Mapped[int] = mapped_column(Integer, nullable=False, index=True)  # 1, 2 o 3
    turno: Mapped[int | None] = mapped_column(Integer)  # 1º a 10º turno del ciclo lectivo
    cierre_inscripcion: Mapped[date] = mapped_column(Date, nullable=False)  # último día para inscribirse
    fecha_examen: Mapped[date] = mapped_column(Date, nullable=False, index=True)


class MesaMateria(Base):
    __tablename__ = "mesas_materias"

    id: Mapped[int] = mapped_column(primary_key=True)
    materia: Mapped[str] = mapped_column(String(200), nullable=False)
    materia_norm: Mapped[str] = mapped_column(String(200), nullable=False, index=True)
    mesa: Mapped[int] = mapped_column(Integer, nullable=False)
    sede: Mapped[str] = mapped_column(String(40), nullable=False, default="Casa Central")
    presidente: Mapped[str | None] = mapped_column(String(120))
    vocal1: Mapped[str | None] = mapped_column(String(120))
    vocal2: Mapped[str | None] = mapped_column(String(120))
    hora: Mapped[str | None] = mapped_column(String(5))  # "HH:MM"
    anio_tribunal: Mapped[int | None] = mapped_column(Integer)  # año del listado de tribunales
