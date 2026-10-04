"""
Modelos de la ingesta: de dónde sale la información y qué se capturó.

  Fuente       → sitio o cuenta de donde se obtiene contenido (activable)
  Documento    → página web o PDF capturado (original + texto extraído)
  Publicacion  → entrada con ID propio en su fuente (post de WordPress, IG…)
  Chunk        → fragmento de texto buscable de un documento o publicación
  Ingesta      → una corrida del worker sobre una fuente, con sus contadores

Un cambio de contenido no pisa el original: se guarda una fila nueva y la
anterior queda con vigente=False (requerimiento "conservar el original").
"""
import enum
from datetime import datetime

from sqlalchemy import (
    JSON, Boolean, CheckConstraint, Computed, DateTime, Enum, ForeignKey, Index,
    Integer, LargeBinary, String, Text, UniqueConstraint, func,
)
from sqlalchemy.dialects.postgresql import JSONB, TSVECTOR
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base

# JSONB en Postgres, JSON común en SQLite (tests)
_JSON = JSON().with_variant(JSONB(), "postgresql")


class TipoFuenteEnum(str, enum.Enum):
    WEB       = "WEB"        # sitio HTML (+ PDFs enlazados)
    WORDPRESS = "WORDPRESS"  # sitio WordPress con REST API pública
    INSTAGRAM = "INSTAGRAM"  # Fase 2: solo mecanismos permitidos
    WHATSAPP  = "WHATSAPP"   # Fase 2: solo mecanismos permitidos
    MANUAL    = "MANUAL"     # carga asistida por un MOD


class TipoDocumentoEnum(str, enum.Enum):
    HTML = "HTML"
    PDF  = "PDF"


class EstadoIngestaEnum(str, enum.Enum):
    EN_CURSO = "EN_CURSO"
    OK       = "OK"
    ERROR    = "ERROR"


class Fuente(Base):
    __tablename__ = "fuentes"
    __table_args__ = (
        CheckConstraint("confiabilidad_base BETWEEN 0 AND 100", name="ck_fuentes_confiabilidad"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    nombre: Mapped[str] = mapped_column(String(100), unique=True, nullable=False)
    tipo: Mapped[TipoFuenteEnum] = mapped_column(Enum(TipoFuenteEnum, name="tipofuenteenum"), nullable=False)
    url: Mapped[str] = mapped_column(String(500), nullable=False)
    confiabilidad_base: Mapped[int] = mapped_column(Integer, nullable=False)
    activa: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    # Parámetros del adaptador: endpoints, prefijos permitidos, límites por corrida
    config: Mapped[dict] = mapped_column(_JSON, default=dict, nullable=False)
    ultima_revision: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    creado_en: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )

    def __repr__(self) -> str:
        return f"<Fuente {self.nombre} activa={self.activa}>"


class Documento(Base):
    __tablename__ = "documentos"
    __table_args__ = (
        Index("ix_documentos_fuente_url", "fuente_id", "url"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    fuente_id: Mapped[int] = mapped_column(ForeignKey("fuentes.id"), nullable=False)
    url: Mapped[str] = mapped_column(String(1000), nullable=False)
    nombre: Mapped[str | None] = mapped_column(String(500))
    tipo: Mapped[TipoDocumentoEnum] = mapped_column(
        Enum(TipoDocumentoEnum, name="tipodocumentoenum"), nullable=False
    )
    # Original comprimido (gzip). Los PDFs grandes pueden ir a storage externo.
    contenido_original: Mapped[bytes | None] = mapped_column(LargeBinary)
    storage_key: Mapped[str | None] = mapped_column(String(500))
    texto_extraido: Mapped[str | None] = mapped_column(Text)
    # sha256 del contenido: detecta duplicados sin LLM
    hash: Mapped[str] = mapped_column(String(64), unique=True, nullable=False)
    etag: Mapped[str | None] = mapped_column(String(200))
    last_modified: Mapped[str | None] = mapped_column(String(100))
    fecha_publicacion: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    fecha_captura: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    vigente: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)


class Publicacion(Base):
    __tablename__ = "publicaciones"
    __table_args__ = (
        # Misma publicación con otro contenido = versión nueva (fila nueva)
        UniqueConstraint("fuente_id", "id_externo", "hash", name="uq_publicacion_version"),
        Index("ix_publicaciones_fuente_externo", "fuente_id", "id_externo"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    fuente_id: Mapped[int] = mapped_column(ForeignKey("fuentes.id"), nullable=False)
    id_externo: Mapped[str] = mapped_column(String(100), nullable=False)
    url: Mapped[str] = mapped_column(String(1000), nullable=False)
    titulo: Mapped[str | None] = mapped_column(String(500))
    contenido_original: Mapped[str] = mapped_column(Text, nullable=False)
    fecha_publicacion: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    fecha_modificacion: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    fecha_captura: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    hash: Mapped[str] = mapped_column(String(64), nullable=False)
    vigente: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)


class Chunk(Base):
    __tablename__ = "chunks"
    __table_args__ = (
        CheckConstraint(
            "(documento_id IS NULL) <> (publicacion_id IS NULL)",
            name="ck_chunks_un_origen",
        ),
        Index("ix_chunks_tsv", "tsv", postgresql_using="gin"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    documento_id: Mapped[int | None] = mapped_column(
        ForeignKey("documentos.id", ondelete="CASCADE"), index=True
    )
    publicacion_id: Mapped[int | None] = mapped_column(
        ForeignKey("publicaciones.id", ondelete="CASCADE"), index=True
    )
    orden: Mapped[int] = mapped_column(Integer, nullable=False)
    texto: Mapped[str] = mapped_column(Text, nullable=False)
    # sha256 del texto: si ya existe un chunk igual, se reutiliza su embedding
    hash: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    # Búsqueda full-text en español, calculada por Postgres (sin LLM).
    # Al consultar, usar prefijos sobre los lexemas de la pregunta ('exam':*):
    # el stemmer reduce "examen"→"exam" pero "exámenes"→"examen", y sin prefijo no coinciden.
    tsv = mapped_column(
        TSVECTOR().with_variant(Text(), "sqlite"),  # SQLite solo en tests
        Computed("to_tsvector('spanish', texto)", persisted=True),
    )
    # La columna `embedding` (pgvector) se agrega en la etapa 7, solo si hace falta


class Ingesta(Base):
    __tablename__ = "ingestas"

    id: Mapped[int] = mapped_column(primary_key=True)
    fuente_id: Mapped[int] = mapped_column(ForeignKey("fuentes.id"), nullable=False, index=True)
    estado: Mapped[EstadoIngestaEnum] = mapped_column(
        Enum(EstadoIngestaEnum, name="estadoingestaenum"),
        default=EstadoIngestaEnum.EN_CURSO,
        nullable=False,
    )
    inicio: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    fin: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    nuevos: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    sin_cambios: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    duplicados: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    errores: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    detalle_errores: Mapped[list] = mapped_column(_JSON, default=list, nullable=False)
