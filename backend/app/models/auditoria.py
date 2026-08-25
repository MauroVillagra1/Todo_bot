"""
Modelo RegistroCambios — auditoría genérica de toda modificación relevante.
Se escribe desde los servicios mediante la función helper `registrar_cambio`.
Nunca se borra ni edita.
"""
from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, Integer, String, Text, func
from sqlalchemy.dialects.postgresql import JSON
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base


class RegistroCambios(Base):
    __tablename__ = "registro_cambios"

    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    # Nombre de la tabla afectada, ej: "cursadas", "cursada_excepciones"
    tabla_afectada: Mapped[str] = mapped_column(String(100), nullable=False, index=True)
    # ID del registro modificado en esa tabla
    registro_id: Mapped[int] = mapped_column(Integer, nullable=False, index=True)
    # Snapshot del estado anterior (JSON) — puede ser None en creaciones
    valor_anterior: Mapped[dict | None] = mapped_column(JSON)
    # Snapshot del estado nuevo (JSON)
    valor_nuevo: Mapped[dict | None] = mapped_column(JSON)
    # Descripción breve de la acción: "creacion", "actualizacion", "inactivacion"
    accion: Mapped[str] = mapped_column(String(50), nullable=False)

    # Quién hizo el cambio
    usuario_id: Mapped[int] = mapped_column(ForeignKey("usuarios.id"), nullable=False, index=True)

    fecha: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False, index=True
    )

    # Relaciones
    usuario: Mapped["Usuario"] = relationship("Usuario", foreign_keys=[usuario_id])

    def __repr__(self) -> str:
        return (
            f"<RegistroCambios tabla={self.tabla_afectada} "
            f"id={self.registro_id} accion={self.accion} fecha={self.fecha}>"
        )
