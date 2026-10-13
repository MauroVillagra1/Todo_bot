"""
Búsqueda de evidencias para una pregunta (RAG-01, pasos SQL + full-text).

Full-text de Postgres en español con prefijos sobre los lexemas de la pregunta
('exam':*), porque el stemmer reduce "examen"→"exam" pero "exámenes"→"examen".
Sin tildes de los dos lados (sin_tildes, migración 13): casi nadie las escribe.
Si eso no trae nada, se afloja: alguna palabra de la pregunta y después partes de
palabras en título o texto, y por último palabras parecidas (pg_trgm).

Además, si hay embeddings (services/embeddings.py), se buscan los chunks más parecidos en
significado ("¿cómo me anoto?" → "Inscripción a cursado") y se combinan con la búsqueda
precisa por posición en cada lista (RRF). Si la API de embeddings falla, todo sigue por palabras.
"""
import re
from dataclasses import dataclass
from datetime import datetime

from sqlalchemy import text
from sqlalchemy.orm import Session

from app.ingest.classify import clasificar, normalizar
from app.services import embeddings

MAX_RESULTADOS = 5
MAX_CHUNKS_POR_INFORMACION = 2
# Fichas del mismo tipo ("Aula virtual: Inglés I — …", "Aula virtual: Programación II — …"):
# como mucho estas, para que entre también la página que resume todo
MAX_POR_GRUPO_DE_TITULO = 3
# Candidatos que trae cada consulta por resultado pedido: con 18 fichas "Aula virtual" de una
# carrera, la página que las resume quedaba en el puesto 20 y no entraba
CANDIDATOS_POR_RESULTADO = 10
PUNTAJE_MINIMO = 0.01

# Proporción mínima de palabras de la pregunta que deben aparecer en el chunk.
# Sin esto, "¿Quién ganó el mundial?" traía "Paz Mundial" o "Logo ganador".
COBERTURA_MINIMA = 0.6

# Lexemas que indican "cuándo" pero casi nunca están en los avisos ("¿cuándo es la
# próxima mesa?" → solo importa "mesa"); la fecha la resuelve la IA con la de hoy.
LEXEMAS_IGNORADOS = ["proxim", "siguient", "pront", "falt", "cuant",
                     # "lista de…", "cuáles son las…": no están en el texto y bajan la cobertura
                     "list", "cual"]

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

# Los más cercanos en significado (distancia coseno de pgvector, sin índice: búsqueda exacta)
_CANDIDATOS_SEMANTICO = """
WITH cercanos AS (
    SELECT c.*, 1 - (c.embedding <=> CAST(:vector AS halfvec)) AS similitud
    FROM chunks c WHERE c.embedding IS NOT NULL
    ORDER BY c.embedding <=> CAST(:vector AS halfvec)
    LIMIT :cercanos
), candidatos AS (
    SELECT *, 1 AS n, 1 AS coinciden FROM cercanos WHERE similitud >= :umbral_semantico
)
"""
# Debajo de esto el parecido es casual (Gemini da ~0,5 entre textos sin relación)
UMBRAL_SEMANTICO = 0.62
CERCANOS = 40
RRF_K = 60  # fusión por ranking: 1/(K + posición) en cada lista

_PUNTAJE = """
SELECT c.id AS chunk_id, i.id AS informacion_id,
       -- Sin el texto: se piden muchos candidatos y el texto solo de los elegidos (_con_textos)
       coalesce(p.titulo, d.nombre) AS titulo, '' AS texto, coalesce(p.url, d.url) AS url,
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
_SQL_SEMANTICO = text(_CANDIDATOS_SEMANTICO + _PUNTAJE.format(
    rango="(c.similitud - :umbral_semantico) / (1 - :umbral_semantico)", titulo_completo="false"))
_hay_trgm: bool | None = None
_hay_embeddings: bool | None = None


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
    return _con_textos(db, _elegir(db, pregunta, max_resultados, excluir, flexible))


def _con_textos(db: Session, resultados: list[Resultado]) -> list[Resultado]:
    if resultados:
        textos = dict(db.execute(text("SELECT id, texto FROM chunks WHERE id = ANY(:ids)"),
                                 {"ids": [r.chunk_id for r in resultados]}).all())
        for r in resultados:
            r.texto = textos.get(r.chunk_id, "")
    return resultados


def _elegir(db: Session, pregunta: str, max_resultados: int,
            excluir: list[int] | None, flexible: bool) -> list[Resultado]:
    tipo, ambiguo = clasificar(pregunta, "")
    parametros = {
        "pregunta": pregunta, "tipo": "" if ambiguo else tipo.value, "limite": max_resultados * CANDIDATOS_POR_RESULTADO,
        "ignorados": LEXEMAS_IGNORADOS, "peso_titulo": PESO_TITULO, "excluir": list(excluir or []),
        "peso_futuro": PESO_FECHA_FUTURA if _TEMPORAL.search(normalizar(pregunta)) else 1.0,
        "similitud": SIMILITUD_MINIMA,
    }
    sql, cobertura, minimo = _PASADAS_ESTRICTAS[0]
    filas = db.execute(sql, {**parametros, "cobertura": cobertura}).mappings().all()
    precisos = [f for f in filas if f["puntaje"] >= minimo]
    # Con la pregunta anterior (flexible=False) solo palabras: por significado siempre
    # aparecería algo del tema viejo y no se detectaría el cambio de tema.
    # Si las palabras ya alcanzan, el significado no se usa: mezclado o reordenando traía
    # textos de otra carrera ("tecnicatura en programación" → materias de Ingeniería en Sistemas)
    alcanza = len(_mejores(precisos, 0.0, max_resultados)) >= max_resultados
    semanticos = _semanticos(db, pregunta, parametros) if flexible and not alcanza else []
    if precisos or semanticos:
        return _mejores(_fusionar(precisos, semanticos), 0.0, max_resultados)

    pasadas = _PASADAS_FLEXIBLES + _pasada_aproximada(db) if flexible else []
    for sql, cobertura, minimo in pasadas:
        filas = db.execute(sql, {**parametros, "cobertura": cobertura}).mappings().all()
        resultados = _mejores(filas, minimo, max_resultados)
        if resultados:
            return resultados
    return []


def _semanticos(db: Session, pregunta: str, parametros: dict) -> list:
    global _hay_embeddings
    if _hay_embeddings is None:
        _hay_embeddings = embeddings.hay_columna(db)
    vector = embeddings.de_pregunta(pregunta) if _hay_embeddings else None
    if vector is None:
        return []
    return db.execute(_SQL_SEMANTICO, {
        **parametros, "cobertura": 0.0, "vector": embeddings.a_sql(vector),
        "cercanos": CERCANOS, "umbral_semantico": UMBRAL_SEMANTICO,
    }).mappings().all()


def _fusionar(*listas) -> list:
    """Reciprocal Rank Fusion: lo que está alto en las dos listas queda primero."""
    puntos: dict[int, float] = {}
    filas: dict[int, dict] = {}
    for lista in listas:
        for posicion, fila in enumerate(lista):
            puntos[fila["chunk_id"]] = puntos.get(fila["chunk_id"], 0.0) + 1 / (RRF_K + posicion)
            filas.setdefault(fila["chunk_id"], fila)
    return [filas[i] for i in sorted(puntos, key=puntos.get, reverse=True)]


def _grupo_de_titulo(titulo: str | None) -> str:
    """'Aula virtual: Inglés I — Tecnicatura…' → 'aula virtual'; sin prefijo, el título entero."""
    titulo = normalizar(titulo or "")
    prefijo, dos_puntos, _ = titulo.partition(":")
    return prefijo.strip() if dos_puntos and len(prefijo) <= 30 else titulo.strip()


def _mejores(filas, minimo: float, max_resultados: int) -> list[Resultado]:
    resultados: list[Resultado] = []
    por_informacion: dict[int, int] = {}
    por_grupo: dict[str, int] = {}
    for f in filas:
        if f["puntaje"] < minimo:
            continue
        if por_informacion.get(f["informacion_id"], 0) >= MAX_CHUNKS_POR_INFORMACION:
            continue
        grupo = _grupo_de_titulo(f["titulo"])
        if por_grupo.get(grupo, 0) >= MAX_POR_GRUPO_DE_TITULO:
            continue
        por_informacion[f["informacion_id"]] = por_informacion.get(f["informacion_id"], 0) + 1
        por_grupo[grupo] = por_grupo.get(grupo, 0) + 1
        resultados.append(Resultado(**{k: f[k] for k in Resultado.__dataclass_fields__}))
        if len(resultados) == max_resultados:
            break
    return resultados
