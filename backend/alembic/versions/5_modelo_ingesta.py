"""modelo de ingesta: fuentes, documentos, publicaciones, chunks, ingestas, métricas

Revision ID: modelo_ingesta
Revises: roles_mma
Create Date: 2026-10-03

Carga las 8 fuentes del documento de requerimientos (§3). Solo Sistemas FRT
queda activa: UTN FRT está caída e Instagram/WhatsApp son Fase 2.
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "modelo_ingesta"
down_revision: Union[str, None] = "roles_mma"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

tipo_fuente = postgresql.ENUM(
    "WEB", "WORDPRESS", "INSTAGRAM", "WHATSAPP", "MANUAL", name="tipofuenteenum", create_type=False
)
tipo_documento = postgresql.ENUM("HTML", "PDF", name="tipodocumentoenum", create_type=False)
estado_ingesta = postgresql.ENUM("EN_CURSO", "OK", "ERROR", name="estadoingestaenum", create_type=False)

_WP = "https://sistemasfrtutn.ar/wp-json/wp/v2"

FUENTES = [
    {
        "nombre": "UTN FRT (web)", "tipo": "WEB", "url": "https://frt.utn.edu.ar",
        "confiabilidad_base": 100, "activa": False,
        "config": {"prefijos_permitidos": ["https://frt.utn.edu.ar/"], "max_paginas": 200,
                   "nota": "Sitio caído al 03/10/2026; activar cuando vuelva."},
    },
    {
        "nombre": "Sistemas FRT", "tipo": "WORDPRESS", "url": "https://sistemasfrtutn.ar",
        "confiabilidad_base": 100, "activa": True,
        "config": {"api": _WP, "tipos": ["posts", "pages", "tp_event"], "por_pagina": 50},
    },
    {"nombre": "SAE FRT (Instagram)", "tipo": "INSTAGRAM", "url": "https://instagram.com/sae.frt.ofc",
     "confiabilidad_base": 100, "activa": False, "config": {}},
    {"nombre": "UTN Tucumán (Instagram)", "tipo": "INSTAGRAM", "url": "https://instagram.com/utntucuman",
     "confiabilidad_base": 100, "activa": False, "config": {}},
    {"nombre": "Ing. Civil FRT (Instagram)", "tipo": "INSTAGRAM",
     "url": "https://instagram.com/ing.civilutnfrtoficial",
     "confiabilidad_base": 90, "activa": False, "config": {}},
    {"nombre": "Ing. Sistemas FRT (Instagram)", "tipo": "INSTAGRAM",
     "url": "https://instagram.com/ing.sistemasinformacion.utnfrt",
     "confiabilidad_base": 90, "activa": False, "config": {}},
    {"nombre": "Canal WhatsApp 1", "tipo": "WHATSAPP",
     "url": "https://whatsapp.com/channel/0029VaYQ0rj2phHJITlkfZ1T",
     "confiabilidad_base": 50, "activa": False, "config": {}},
    {"nombre": "Canal WhatsApp 2", "tipo": "WHATSAPP",
     "url": "https://whatsapp.com/channel/0029VasYqrT9Gv7V5UHXHY0F",
     "confiabilidad_base": 50, "activa": False, "config": {}},
]


def upgrade() -> None:
    bind = op.get_bind()
    tipo_fuente.create(bind, checkfirst=True)
    tipo_documento.create(bind, checkfirst=True)
    estado_ingesta.create(bind, checkfirst=True)

    fuentes = op.create_table(
        "fuentes",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("nombre", sa.String(100), nullable=False, unique=True),
        sa.Column("tipo", tipo_fuente, nullable=False),
        sa.Column("url", sa.String(500), nullable=False),
        sa.Column("confiabilidad_base", sa.Integer(), nullable=False),
        sa.Column("activa", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("config", postgresql.JSONB(), nullable=False, server_default=sa.text("'{}'::jsonb")),
        sa.Column("ultima_revision", sa.DateTime(timezone=True)),
        sa.Column("creado_en", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.CheckConstraint("confiabilidad_base BETWEEN 0 AND 100", name="ck_fuentes_confiabilidad"),
    )

    op.create_table(
        "documentos",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("fuente_id", sa.Integer(), sa.ForeignKey("fuentes.id"), nullable=False),
        sa.Column("url", sa.String(1000), nullable=False),
        sa.Column("nombre", sa.String(500)),
        sa.Column("tipo", tipo_documento, nullable=False),
        sa.Column("contenido_original", sa.LargeBinary()),
        sa.Column("storage_key", sa.String(500)),
        sa.Column("texto_extraido", sa.Text()),
        sa.Column("hash", sa.String(64), nullable=False, unique=True),
        sa.Column("etag", sa.String(200)),
        sa.Column("last_modified", sa.String(100)),
        sa.Column("fecha_captura", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.Column("vigente", sa.Boolean(), nullable=False, server_default=sa.true()),
    )
    op.create_index("ix_documentos_fuente_url", "documentos", ["fuente_id", "url"])

    op.create_table(
        "publicaciones",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("fuente_id", sa.Integer(), sa.ForeignKey("fuentes.id"), nullable=False),
        sa.Column("id_externo", sa.String(100), nullable=False),
        sa.Column("url", sa.String(1000), nullable=False),
        sa.Column("titulo", sa.String(500)),
        sa.Column("contenido_original", sa.Text(), nullable=False),
        sa.Column("fecha_publicacion", sa.DateTime(timezone=True)),
        sa.Column("fecha_modificacion", sa.DateTime(timezone=True)),
        sa.Column("fecha_captura", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.Column("hash", sa.String(64), nullable=False),
        sa.Column("vigente", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.UniqueConstraint("fuente_id", "id_externo", "hash", name="uq_publicacion_version"),
    )
    op.create_index("ix_publicaciones_fuente_externo", "publicaciones", ["fuente_id", "id_externo"])

    op.create_table(
        "chunks",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("documento_id", sa.Integer(), sa.ForeignKey("documentos.id", ondelete="CASCADE")),
        sa.Column("publicacion_id", sa.Integer(), sa.ForeignKey("publicaciones.id", ondelete="CASCADE")),
        sa.Column("orden", sa.Integer(), nullable=False),
        sa.Column("texto", sa.Text(), nullable=False),
        sa.Column("hash", sa.String(64), nullable=False),
        sa.Column(
            "tsv", postgresql.TSVECTOR(),
            sa.Computed("to_tsvector('spanish', texto)", persisted=True),
        ),
        sa.CheckConstraint("(documento_id IS NULL) <> (publicacion_id IS NULL)", name="ck_chunks_un_origen"),
    )
    op.create_index("ix_chunks_documento_id", "chunks", ["documento_id"])
    op.create_index("ix_chunks_publicacion_id", "chunks", ["publicacion_id"])
    op.create_index("ix_chunks_hash", "chunks", ["hash"])
    op.create_index("ix_chunks_tsv", "chunks", ["tsv"], postgresql_using="gin")

    op.create_table(
        "ingestas",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("fuente_id", sa.Integer(), sa.ForeignKey("fuentes.id"), nullable=False),
        sa.Column("estado", estado_ingesta, nullable=False, server_default="EN_CURSO"),
        sa.Column("inicio", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.Column("fin", sa.DateTime(timezone=True)),
        sa.Column("nuevos", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("sin_cambios", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("duplicados", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("errores", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("detalle_errores", postgresql.JSONB(), nullable=False, server_default=sa.text("'[]'::jsonb")),
    )
    op.create_index("ix_ingestas_fuente_id", "ingestas", ["fuente_id"])

    op.create_table(
        "metricas_diarias",
        sa.Column("dia", sa.Date(), primary_key=True),
        sa.Column("metrica", sa.String(50), primary_key=True),
        sa.Column("valor", sa.Integer(), nullable=False, server_default="0"),
    )

    op.bulk_insert(fuentes, FUENTES)


def downgrade() -> None:
    for tabla in ("metricas_diarias", "ingestas", "chunks", "publicaciones", "documentos", "fuentes"):
        op.drop_table(tabla)
    bind = op.get_bind()
    estado_ingesta.drop(bind, checkfirst=True)
    tipo_documento.drop(bind, checkfirst=True)
    tipo_fuente.drop(bind, checkfirst=True)
