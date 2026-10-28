"""
Calendario académico (solo ADMIN lo edita; el chat lo responde con SQL, sin LLM).
Cada fila es una actividad con fecha o rango: inicio de clases, inscripciones, plazos para
presentar notas, recesos, pruebas de suficiencia, feriados y asuetos.
Los turnos de exámenes finales viven en mesas_fechas (models/mesa.py).
"""
from datetime import date

from sqlalchemy import Date, String
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base

CATEGORIAS = {
    "CLASES": "Clases",
    "INSCRIPCION": "Inscripción",
    "NOTAS": "Presentación de notas",
    "SUFICIENCIA": "Prueba de suficiencia",
    "EXAMENES": "Exámenes",
    "RECESO": "Receso",
    "FERIADO": "Feriado",
    "ASUETO": "Asueto",
    "PLAZO": "Plazo / vencimiento",
    "OTRO": "Otro",
}


class EventoCalendario(Base):
    __tablename__ = "calendario_eventos"

    id: Mapped[int] = mapped_column(primary_key=True)
    fecha_inicio: Mapped[date] = mapped_column(Date, nullable=False, index=True)
    fecha_fin: Mapped[date | None] = mapped_column(Date)  # vacío = un solo día
    actividad: Mapped[str] = mapped_column(String(300), nullable=False)
    categoria: Mapped[str] = mapped_column(String(20), nullable=False, default="OTRO")
    detalle: Mapped[str | None] = mapped_column(String(300))

    def hasta(self) -> date:
        return self.fecha_fin or self.fecha_inicio
