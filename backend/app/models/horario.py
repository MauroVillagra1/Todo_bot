"""
Modelo HorarioClase — un bloque de clase de una grilla de horarios (PDF).
Se genera en la ingesta (app/ingest/horarios.py) y permite responder
preguntas de horarios con SQL, sin LLM (rag/horarios.py).
Si el PDF cambia, sus filas se reemplazan (cascade desde documentos).
Las filas que agrega un ADMIN desde el panel no tienen documento (documento_id NULL).
"""
from sqlalchemy import Boolean, ForeignKey, Integer, String
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base


class HorarioClase(Base):
    __tablename__ = "horarios_clases"

    id: Mapped[int] = mapped_column(primary_key=True)
    documento_id: Mapped[int | None] = mapped_column(
        ForeignKey("documentos.id", ondelete="CASCADE"), index=True
    )
    comision: Mapped[str | None] = mapped_column(String(10), index=True)  # "1K01"
    anio: Mapped[int | None] = mapped_column(Integer)
    plan: Mapped[str | None] = mapped_column(String(10))
    turno: Mapped[str | None] = mapped_column(String(30))
    periodo: Mapped[str | None] = mapped_column(String(40))  # Anual | Primer/Segundo cuatrimestre
    aula: Mapped[str | None] = mapped_column(String(40))
    dia: Mapped[int] = mapped_column(Integer, nullable=False)  # 1 = lunes … 6 = sábado
    inicio: Mapped[str] = mapped_column(String(5), nullable=False)  # "HH:MM"
    fin: Mapped[str] = mapped_column(String(5), nullable=False)
    materia: Mapped[str] = mapped_column(String(200), nullable=False)
    materia_norm: Mapped[str] = mapped_column(String(200), nullable=False, index=True)
    docente: Mapped[str | None] = mapped_column(String(200))
    lugar: Mapped[str | None] = mapped_column(String(60))
    electiva: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
