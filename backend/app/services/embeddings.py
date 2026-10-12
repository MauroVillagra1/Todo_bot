"""
Embeddings (vectores de significado) con la API gratuita de Gemini.

Sirven para que "¿cómo me anoto a las materias?" encuentre "Inscripción a cursado"
aunque no compartan palabras (rag/search.py). Se guardan en chunks.embedding como
halfvec(768): 1,5 KB por chunk, para no gastar el cupo de Neon.

  completar(db)   → vectoriza los chunks vigentes que no tienen (ingesta / script)
  de_pregunta(t)  → vector de una pregunta; None si no hay key o la API falla
"""
import logging
import time

import httpx
from sqlalchemy import text
from sqlalchemy.orm import Session

from app.core.config import get_settings

logger = logging.getLogger(__name__)

MODELO = "gemini-embedding-001"
DIMENSIONES = 768
URL = f"https://generativelanguage.googleapis.com/v1beta/models/{MODELO}:batchEmbedContents"
LOTE = 50                 # textos por pedido a la API
ESPERA_CUPO = 65          # segundos si la API corta por cupo por minuto (429)
REINTENTOS_CUPO = 5      # seguidos; después se corta y sigue en la próxima corrida

_cache_preguntas: dict[str, list[float]] = {}  # por proceso: la misma pregunta no se vectoriza dos veces


def _key() -> str:
    return (get_settings().GEMINI_API_KEY or "").strip()


def vectorizar(textos: list[str], tipo: str, timeout: float = 60) -> list[list[float]]:
    """`tipo`: RETRIEVAL_DOCUMENT para chunks, RETRIEVAL_QUERY para preguntas."""
    pedidos = [{"model": f"models/{MODELO}", "content": {"parts": [{"text": t}]},
                "taskType": tipo, "outputDimensionality": DIMENSIONES} for t in textos]
    resp = httpx.post(URL, headers={"x-goog-api-key": _key()}, json={"requests": pedidos}, timeout=timeout)
    if resp.status_code != 200:
        raise ValueError(f"HTTP {resp.status_code}: {resp.text[:200]}")
    return [e["values"] for e in resp.json()["embeddings"]]


def a_sql(vector: list[float]) -> str:
    """Formato de texto de pgvector: '[0.1,0.2,…]' (se castea a halfvec en el SQL)."""
    return "[" + ",".join(f"{x:.5f}" for x in vector) + "]"


def de_pregunta(pregunta: str) -> list[float] | None:
    if not _key():
        return None
    if pregunta not in _cache_preguntas:
        try:
            # Timeout corto: si la API tarda, se busca solo por palabras
            _cache_preguntas[pregunta] = vectorizar([pregunta], "RETRIEVAL_QUERY", timeout=4)[0]
        except Exception as e:
            logger.warning("Embedding de la pregunta no disponible: %s", str(e)[:200])
            return None
        if len(_cache_preguntas) > 500:
            _cache_preguntas.pop(next(iter(_cache_preguntas)))
    return _cache_preguntas[pregunta]


def hay_columna(db: Session) -> bool:
    return db.execute(text(
        "SELECT 1 FROM information_schema.columns WHERE table_name = 'chunks' AND column_name = 'embedding'"
    )).first() is not None


# Chunks vigentes sin vector (los de versiones viejas nunca se muestran: no se vectorizan)
_PENDIENTES = text("""
SELECT c.id, c.texto FROM chunks c
LEFT JOIN publicaciones p ON p.id = c.publicacion_id
LEFT JOIN documentos d ON d.id = c.documento_id
WHERE c.embedding IS NULL AND coalesce(p.vigente, d.vigente)
ORDER BY c.id LIMIT :limite
""")


def completar(db: Session, maximo: int | None = None) -> int:
    """Vectoriza chunks vigentes sin embedding. Devuelve cuántos se vectorizaron con la API."""
    if not _key() or not hay_columna(db):
        return 0
    # Mismo texto ya vectorizado (hash igual): se copia sin llamar a la API
    db.execute(text("""
        UPDATE chunks c SET embedding = o.embedding
        FROM chunks o WHERE c.embedding IS NULL AND o.hash = c.hash AND o.embedding IS NOT NULL
    """))
    # Versiones reemplazadas: el vector no se usa más y ocupa lugar en Neon
    db.execute(text("""
        UPDATE chunks c SET embedding = NULL
        WHERE c.embedding IS NOT NULL AND NOT coalesce(
            (SELECT vigente FROM publicaciones WHERE id = c.publicacion_id),
            (SELECT vigente FROM documentos WHERE id = c.documento_id))
    """))
    db.commit()

    hechos, cortes = 0, 0
    while maximo is None or hechos < maximo:
        limite = LOTE if maximo is None else min(LOTE, maximo - hechos)
        filas = db.execute(_PENDIENTES, {"limite": limite}).all()
        if not filas:
            break
        try:
            vectores = vectorizar([f.texto for f in filas], "RETRIEVAL_DOCUMENT")
        except ValueError as e:
            if "HTTP 429" in str(e) and cortes < REINTENTOS_CUPO:
                cortes += 1
                time.sleep(ESPERA_CUPO)
                continue
            raise
        for fila, vector in zip(filas, vectores):
            db.execute(text("UPDATE chunks SET embedding = CAST(:v AS halfvec) WHERE id = :id"),
                       {"v": a_sql(vector), "id": fila.id})
        db.commit()
        hechos += len(filas)
        cortes = 0  # el tope es de cortes seguidos: el cupo por minuto se renueva
    return hechos
