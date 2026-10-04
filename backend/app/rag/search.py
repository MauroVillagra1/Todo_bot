"""
Búsqueda de evidencias para una pregunta (RAG-01, pasos SQL + full-text).

Full-text de Postgres en español con prefijos sobre los lexemas de la pregunta
('exam':*), porque el stemmer reduce "examen"→"exam" pero "exámenes"→"examen".
Sin LLM ni embeddings: si esto no alcanza, la etapa 7 suma pgvector.
"""
from dataclasses import dataclass
from datetime import datetime

from sqlalchemy import text
from sqlalchemy.orm import Session

from app.ingest.classify import clasificar

MAX_RESULTADOS = 5
MAX_CHUNKS_POR_INFORMACION = 2
PUNTAJE_MINIMO = 0.01

_SQL = text("""
WITH q AS (
    SELECT to_tsquery('spanish', string_agg(quote_literal(lexeme) || ':*', ' | ')) AS tsq
    FROM unnest(to_tsvector('spanish', :pregunta))
)
SELECT c.id AS chunk_id, i.id AS informacion_id, p.titulo, c.texto, p.url,
       f.nombre AS fuente, coalesce(p.fecha_modificacion, p.fecha_publicacion) AS fecha,
       i.estado::text AS estado, i.tipo::text AS tipo,
       ts_rank(c.tsv, q.tsq)
         * CASE i.estado::text
             WHEN 'CONFIRMADA' THEN 1.0 WHEN 'PROBABLE' THEN 0.8
             WHEN 'NO_CONFIRMADA' THEN 0.5 ELSE 0.25 END
         * CASE WHEN i.tipo::text = :tipo THEN 1.5 ELSE 1.0 END AS puntaje
FROM q
JOIN chunks c ON c.tsv @@ q.tsq
JOIN publicaciones p ON p.id = c.publicacion_id AND p.vigente
JOIN evidencias e ON e.publicacion_id = p.id
JOIN informaciones i ON i.id = e.informacion_id AND i.estado::text NOT IN ('REEMPLAZADA')
JOIN fuentes f ON f.id = p.fuente_id
WHERE q.tsq IS NOT NULL
ORDER BY puntaje DESC, fecha DESC NULLS LAST
LIMIT :limite
""")


@dataclass
class Resultado:
    chunk_id: int
    informacion_id: int
    titulo: str
    texto: str
    url: str
    fuente: str
    fecha: datetime | None
    estado: str
    puntaje: float


def buscar(db: Session, pregunta: str, max_resultados: int = MAX_RESULTADOS) -> list[Resultado]:
    tipo, ambiguo = clasificar(pregunta, "")
    filas = db.execute(
        _SQL,
        {"pregunta": pregunta, "tipo": "" if ambiguo else tipo.value, "limite": max_resultados * 4},
    ).mappings().all()

    resultados: list[Resultado] = []
    por_informacion: dict[int, int] = {}
    for f in filas:
        if f["puntaje"] < PUNTAJE_MINIMO:
            continue
        if por_informacion.get(f["informacion_id"], 0) >= MAX_CHUNKS_POR_INFORMACION:
            continue
        por_informacion[f["informacion_id"]] = por_informacion.get(f["informacion_id"], 0) + 1
        resultados.append(Resultado(**{k: f[k] for k in Resultado.__dataclass_fields__}))
        if len(resultados) == max_resultados:
            break
    return resultados
