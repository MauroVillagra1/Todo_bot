"""
Búsqueda de evidencias para una pregunta (RAG-01, pasos SQL + full-text).

Full-text de Postgres en español con prefijos sobre los lexemas de la pregunta
('exam':*), porque el stemmer reduce "examen"→"exam" pero "exámenes"→"examen".
Sin tildes de los dos lados (sin_tildes, migración 13): casi nadie las escribe.
Si eso no trae nada, se afloja: alguna palabra de la pregunta y después partes de
palabras en título o texto, y por último palabras parecidas (pg_trgm). Sin LLM ni embeddings.
"""
import re
from dataclasses import dataclass
from datetime import datetime

from sqlalchemy import text
from sqlalchemy.orm import Session

from app.ingest.classify import clasificar, normalizar

MAX_RESULTADOS = 5
MAX_CHUNKS_POR_INFORMACION = 2
PUNTAJE_MINIMO = 0.01

# Proporción mínima de palabras de la pregunta que deben aparecer en el chunk.
# Sin esto, "¿Quién ganó el mundial?" traía "Paz Mundial" o "Logo ganador".
COBERTURA_MINIMA = 0.6

# Lexemas que indican "cuándo" pero casi nunca están en los avisos ("¿cuándo es la
# próxima mesa?" → solo importa "mesa"); la fecha la resuelve la IA con la de hoy.
LEXEMAS_IGNORADOS = ["proxim", "siguient", "pront", "falt", "cuant"]

# En esas preguntas pesa más lo que tiene fechas por venir: el calendario con las
# mesas de noviembre sirve más que un aviso confirmado de una mesa que ya pasó.
_TEMPORAL = re.compile(r"\b(proxim[oa]s?|siguientes?|pronto|falta|cuanto|cuando)\b")
PESO_FECHA_FUTURA = 3.0
PESO_TITULO = 4.0

_CANDIDATOS_FTS = """
WITH lex AS (
    SELECT lexeme FROM unnest(to_tsvector('spanish', sin_tildes(:pregunta)))
    WHERE lexeme <> ALL(:ignorados)
), pat AS (
    -- Prefijo solo con raíces de 4+ letras: 'bec':* (de "becas") traía "become"
    SELECT quote_literal(lexeme) || CASE WHEN length(lexeme) > 3 THEN ':*' ELSE '' END AS p FROM lex
), q AS (
    SELECT to_tsquery('spanish', string_agg(p, ' | ')) AS tsq,
           to_tsquery('spanish', string_agg(p, ' & ')) AS tsq_todas,
           count(*) AS n
    FROM pat
), candidatos AS (
    SELECT c.*, q.tsq, q.tsq_todas, q.n,
           (SELECT count(*) FROM pat WHERE c.tsv @@ to_tsquery('spanish', pat.p)) AS coinciden
    FROM q JOIN chunks c ON c.tsv @@ q.tsq
)
"""

# Coincidencia parcial: cada raíz de la pregunta como subcadena del título o del texto
# ("jov" encuentra "Jóvenes", "s.r.l" encuentra "S.R.L."). Último recurso: no usa índice.
_CANDIDATOS_PARCIAL = """
WITH lex AS (
    SELECT DISTINCT lexeme FROM unnest(to_tsvector('spanish', sin_tildes(:pregunta)))
    WHERE length(lexeme) >= 3 AND lexeme <> ALL(:ignorados)
), q AS (
    SELECT count(*) AS n FROM lex
), candidatos AS (
    SELECT c.*, q.n, m.coinciden, m.en_titulo
    FROM q, chunks c
    LEFT JOIN publicaciones p0 ON p0.id = c.publicacion_id
    LEFT JOIN documentos d0 ON d0.id = c.documento_id
    CROSS JOIN LATERAL (
        SELECT count(*) FILTER (WHERE strpos(lower(sin_tildes(coalesce(p0.titulo, d0.nombre, '') || ' ' || c.texto)),
                                             lexeme) > 0) AS coinciden,
               count(*) FILTER (WHERE strpos(lower(sin_tildes(coalesce(p0.titulo, d0.nombre, ''))), lexeme) > 0)
                 AS en_titulo
        FROM lex
    ) m
    WHERE m.coinciden > 0
)
"""

# Palabras parecidas (errores de tipeo: "becsa", "santnder"), con pg_trgm (migración 21)
_CANDIDATOS_APROXIMADO = """
WITH lex AS (
    SELECT DISTINCT lexeme FROM unnest(to_tsvector('spanish', sin_tildes(:pregunta)))
    WHERE length(lexeme) >= 4 AND lexeme <> ALL(:ignorados)
), q AS (
    SELECT count(*) AS n FROM lex
), candidatos AS (
    SELECT c.*, q.n, m.coinciden, m.en_titulo
    FROM q, chunks c
    LEFT JOIN publicaciones p0 ON p0.id = c.publicacion_id
    LEFT JOIN documentos d0 ON d0.id = c.documento_id
    CROSS JOIN LATERAL (
        SELECT count(*) FILTER (WHERE word_similarity(lexeme, lower(sin_tildes(
                   coalesce(p0.titulo, d0.nombre, '') || ' ' || c.texto))) >= :similitud) AS coinciden,
               count(*) FILTER (WHERE word_similarity(lexeme, lower(sin_tildes(coalesce(p0.titulo, d0.nombre, ''))))
                   >= :similitud) AS en_titulo
        FROM lex
    ) m
    WHERE m.coinciden > 0
)
"""
SIMILITUD_MINIMA = 0.55

_PUNTAJE = """
SELECT c.id AS chunk_id, i.id AS informacion_id,
       coalesce(p.titulo, d.nombre) AS titulo, c.texto, coalesce(p.url, d.url) AS url,
       f.nombre AS fuente,
       -- Fecha de publicación: muchas "modificaciones" son ediciones masivas del sitio
       coalesce(p.fecha_publicacion, p.fecha_modificacion, d.fecha_publicacion, d.fecha_captura) AS fecha,
       i.estado::text AS estado, i.tipo::text AS tipo,
       {rango}
         * power(c.coinciden::float / c.n, 2)
         * CASE i.estado::text
             WHEN 'CONFIRMADA' THEN 1.0 WHEN 'PROBABLE' THEN 0.8
             WHEN 'NO_CONFIRMADA' THEN 0.5 ELSE 0.25 END
         * CASE WHEN i.tipo::text = :tipo THEN 1.5 ELSE 1.0 END
         -- Todas las palabras de la pregunta en el título: es de eso ("Beca de Verano en Austria")
         * CASE WHEN {titulo_completo} THEN :peso_titulo ELSE 1.0 END
         -- Votos de los usuarios: ±10 % por punto, acotado entre la mitad y +30 %
         * greatest(0.5, least(1.3, 1 + 0.1 * i.puntaje_votos))
         -- Con fecha_inicio = fechas leídas del texto (sin fechas el vencimiento es "1 año" supuesto)
         * CASE WHEN i.fecha_inicio IS NOT NULL AND i.fecha_fin >= current_date
                THEN :peso_futuro ELSE 1.0 END AS puntaje
FROM candidatos c
-- Un chunk viene de una publicación (post/página) o de un documento (PDF)
LEFT JOIN publicaciones p ON p.id = c.publicacion_id
LEFT JOIN documentos d ON d.id = c.documento_id
JOIN evidencias e ON e.publicacion_id = p.id OR e.documento_id = d.id
JOIN informaciones i ON i.id = e.informacion_id AND i.estado::text NOT IN ('REEMPLAZADA')
JOIN fuentes f ON f.id = coalesce(p.fuente_id, d.fuente_id)
WHERE coalesce(p.vigente, d.vigente)
  -- "No me sirvió": se busca de nuevo sin las informaciones que ya se usaron
  AND NOT (i.id = ANY(CAST(:excluir AS integer[])))
  AND c.coinciden >= greatest(1, ceil(c.n * :cobertura))
ORDER BY puntaje DESC, fecha DESC NULLS LAST
LIMIT :limite
"""

_SQL_FTS = text(_CANDIDATOS_FTS + _PUNTAJE.format(
    rango="ts_rank(c.tsv, c.tsq)",
    titulo_completo="to_tsvector('spanish', sin_tildes(coalesce(p.titulo, d.nombre, ''))) @@ c.tsq_todas"))
# Sin ts_rank: pesa más que la palabra esté en el título
_SQL_PARCIAL = text(_CANDIDATOS_PARCIAL + _PUNTAJE.format(
    rango="(1.0 + c.en_titulo) / 10", titulo_completo="c.en_titulo = c.n"))

# Pasadas de búsqueda, de la más precisa a la más amplia: (sql, cobertura, puntaje mínimo).
# Si una no trae nada se prueba la siguiente; "no encontré" solo si no hay ninguna coincidencia.
_PASADAS_ESTRICTAS = [(_SQL_FTS, COBERTURA_MINIMA, PUNTAJE_MINIMO)]
_PASADAS_FLEXIBLES = [
    (_SQL_FTS, 0.0, 0.0),      # alguna palabra de la pregunta, ordenado por cuántas coinciden
    (_SQL_PARCIAL, 0.0, 0.0),  # parte de una palabra en el título o el texto
]
_SQL_APROXIMADO = text(_CANDIDATOS_APROXIMADO + _PUNTAJE.format(
    rango="(1.0 + c.en_titulo) / 10", titulo_completo="c.en_titulo = c.n"))
_hay_trgm: bool | None = None


def _pasada_aproximada(db: Session) -> list:
    """Solo si la base tiene pg_trgm (el Postgres embebido de desarrollo puede no tenerla)."""
    global _hay_trgm
    if _hay_trgm is None:
        _hay_trgm = db.execute(text("SELECT 1 FROM pg_extension WHERE extname = 'pg_trgm'")).first() is not None
    return [(_SQL_APROXIMADO, 0.0, 0.0)] if _hay_trgm else []


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


def buscar(db: Session, pregunta: str, max_resultados: int = MAX_RESULTADOS,
           excluir: list[int] | None = None, flexible: bool = True) -> list[Resultado]:
    """`flexible`: si la búsqueda precisa no trae nada, prueba con alguna palabra y con partes de palabras."""
    tipo, ambiguo = clasificar(pregunta, "")
    parametros = {
        "pregunta": pregunta, "tipo": "" if ambiguo else tipo.value, "limite": max_resultados * 4,
        "ignorados": LEXEMAS_IGNORADOS, "peso_titulo": PESO_TITULO, "excluir": list(excluir or []),
        "peso_futuro": PESO_FECHA_FUTURA if _TEMPORAL.search(normalizar(pregunta)) else 1.0,
        "similitud": SIMILITUD_MINIMA,
    }
    pasadas = _PASADAS_ESTRICTAS + (_PASADAS_FLEXIBLES + _pasada_aproximada(db) if flexible else [])
    for sql, cobertura, minimo in pasadas:
        filas = db.execute(sql, {**parametros, "cobertura": cobertura}).mappings().all()
        resultados = _mejores(filas, minimo, max_resultados)
        if resultados:
            return resultados
    return []


def _mejores(filas, minimo: float, max_resultados: int) -> list[Resultado]:
    resultados: list[Resultado] = []
    por_informacion: dict[int, int] = {}
    for f in filas:
        if f["puntaje"] < minimo:
            continue
        if por_informacion.get(f["informacion_id"], 0) >= MAX_CHUNKS_POR_INFORMACION:
            continue
        por_informacion[f["informacion_id"]] = por_informacion.get(f["informacion_id"], 0) + 1
        resultados.append(Resultado(**{k: f[k] for k in Resultado.__dataclass_fields__}))
        if len(resultados) == max_resultados:
            break
    return resultados
