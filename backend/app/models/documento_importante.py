"""
Documentos importantes: notas y formularios que los estudiantes descargan (cambio de comisión,
ampliación de cupo, etc.). Los sube un ADMIN; cualquiera los descarga.

El archivo se guarda en la base (son livianos, hasta 2 MB) con carga diferida: listar no lo lee
(cupo de transferencia de Neon). Su texto y su descripción entran al pipeline como una
publicación más, así el chat sabe para qué sirve cada uno y lo cita con el link de descarga.
"""
from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, Integer, LargeBinary, String, Text, func
from sqlalchemy.orm import Mapped, deferred, mapped_column

from app.core.database import Base


class DocumentoImportante(Base):
    __tablename__ = "documentos_importantes"

    id: Mapped[int] = mapped_column(primary_key=True)
    nombre: Mapped[str] = mapped_column(String(200), nullable=False)
    descripcion: Mapped[str] = mapped_column(Text, nullable=False)  # para qué sirve, cuándo se presenta
    archivo_nombre: Mapped[str] = mapped_column(String(255), nullable=False)
    content_type: Mapped[str] = mapped_column(String(120), nullable=False)
    tamano: Mapped[int] = mapped_column(Integer, nullable=False)  # bytes
    contenido: Mapped[bytes] = deferred(mapped_column(LargeBinary, nullable=False))
    texto_extraido: Mapped[str | None] = deferred(mapped_column(Text))
    subido_por: Mapped[int | None] = mapped_column(ForeignKey("usuarios.id", ondelete="SET NULL"))
    creado_en: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)
