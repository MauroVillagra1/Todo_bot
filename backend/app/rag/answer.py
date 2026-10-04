"""
Respuesta del chat (RAG-01 a RAG-05).

  caché → búsqueda → (sin evidencia: respuesta fija, sin LLM)
        → contexto mínimo numerado → LLM → validar citas → estado + fuentes + fecha

Las fuentes que ve el usuario las arma el backend con los datos de la base:
el modelo solo cita números [n]. Un número que no existe se descarta, así
nunca se muestra una fuente o URL inventada.
"""
import hashlib
import logging
import re
from datetime import datetime, timedelta, timezone

from sqlalchemy import func
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.ingest.classify import normalizar
from app.models.cache import CacheRespuesta
from app.models.informacion import Informacion
from app.models.ingesta import Chunk
from app.rag.horarios import responder_horario
from app.rag.search import Resultado, buscar
from app.services import llm
from app.services.metricas import incrementar

logger = logging.getLogger(__name__)

MAX_CONTEXTO = 6000  # caracteres (~1500 tokens)
MAX_TOKENS_RESPUESTA = 500

SIN_EVIDENCIA = "No encontré información institucional sobre eso."
SIN_LLM = "No pude generar la respuesta en este momento. Estas publicaciones pueden servirte:"

SISTEMA = f"""Sos UTNIA, asistente informativo de la UTN Facultad Regional Tucumán.
Reglas:
- Respondé SOLO con la información del CONTEXTO. No inventes fechas, lugares, links, resoluciones ni fuentes.
- Citá cada dato con el número de su fuente entre corchetes, por ejemplo [1].
- Si el contexto no alcanza para responder, respondé exactamente: "{SIN_EVIDENCIA}"
- Si una fuente figura como DESACTUALIZADA, avisalo.
- Respondé en español, breve (máximo 5 oraciones o una lista corta), sin tablas."""

# De mejor a peor: el estado de la respuesta es el peor entre sus fuentes
_ORDEN_ESTADO = ["CONFIRMADA", "PROBABLE", "NO_CONFIRMADA", "CONTRADICTORIA", "DESACTUALIZADA"]


def _ahora() -> datetime:
    return datetime.now(timezone.utc)


def _utc(fecha: datetime | None) -> datetime | None:
    if fecha and fecha.tzinfo is None:
        return fecha.replace(tzinfo=timezone.utc)
    return fecha


def clave_cache(db: Session, pregunta: str) -> str:
    """Pregunta normalizada + versión de los datos (cambia cuando la ingesta toca algo)."""
    total, ultima = db.query(func.count(Informacion.id), func.max(Informacion.updated_at)).one()
    # Los chunks se pueden regenerar sin tocar informaciones (ej. reextraer PDFs)
    ultimo_chunk = db.query(func.max(Chunk.id)).scalar()
    base = f"{normalizar(pregunta).strip(' ?¿!¡.')}|{total}|{ultima}|{ultimo_chunk}"
    return hashlib.sha256(base.encode("utf-8")).hexdigest()


def _contexto(resultados: list[Resultado]) -> str:
    bloques, largo = [], 0
    for n, r in enumerate(resultados, 1):
        fecha = f"{r.fecha:%d/%m/%Y}" if r.fecha else "sin fecha"
        bloque = f"[{n}] {r.titulo} — {r.fuente}, {fecha}, estado {r.estado}\n{r.texto}"
        if largo + len(bloque) > MAX_CONTEXTO and bloques:
            break
        bloques.append(bloque)
        largo += len(bloque)
    return "\n\n".join(bloques)


def _fuente(n: int, r: Resultado) -> dict:
    return {
        "numero": n,
        "titulo": r.titulo,
        "url": r.url,
        "fuente": r.fuente,
        "fecha": r.fecha.date().isoformat() if r.fecha else None,
        "estado": r.estado,
    }


def _peor_estado(estados: list[str]) -> str:
    return max(estados, key=lambda e: _ORDEN_ESTADO.index(e) if e in _ORDEN_ESTADO else 0)


def armar_respuesta(texto_llm: str, resultados: list[Resultado]) -> dict:
    """Valida las citas del modelo y arma estado, fuentes y fecha desde la base."""
    if SIN_EVIDENCIA.lower().rstrip(".") in texto_llm.lower():
        return {"respuesta": SIN_EVIDENCIA, "estado": "NO_CONFIRMADA", "fuentes": [], "fecha_informacion": None}

    citados = sorted({int(n) for n in re.findall(r"\[(\d+)\]", texto_llm)})
    validos = [n for n in citados if 1 <= n <= len(resultados)]
    # Citas a números inexistentes se borran del texto
    texto = re.sub(
        r"\[(\d+)\]", lambda m: m.group(0) if int(m.group(1)) in validos else "", texto_llm
    ).strip()

    if validos:
        usados = [(n, resultados[n - 1]) for n in validos]
        estado = _peor_estado([r.estado for _, r in usados])
    else:
        # Respondió sin citar: no se puede verificar → se muestran las consultadas
        usados = list(enumerate(resultados, 1))
        estado = "NO_CONFIRMADA"

    fechas = [r.fecha for _, r in usados if r.fecha]
    return {
        "respuesta": texto,
        "estado": estado,
        "fuentes": [_fuente(n, r) for n, r in usados],
        "fecha_informacion": max(fechas).date().isoformat() if fechas else None,
    }


def responder(db: Session, pregunta: str, historial: list[dict]) -> dict:
    """
    Devuelve {respuesta, estado, fuentes, fecha_informacion, desde_cache}.
    `historial`: últimos mensajes de la conversación (formato chat), puede estar vacío.
    """
    settings = get_settings()
    incrementar(db, "consultas")

    # La caché solo aplica a preguntas sin contexto previo: con historial,
    # "¿y cuándo cierra?" significa algo distinto en cada conversación.
    clave = clave_cache(db, pregunta) if not historial else None
    if clave:
        hit = db.get(CacheRespuesta, clave)
        if hit and _utc(hit.expira_en) > _ahora():
            hit.hits += 1
            incrementar(db, "cache_hits")
            return {**hit.respuesta, "desde_cache": True}
        incrementar(db, "cache_misses")

    anterior = next((m["content"] for m in reversed(historial) if m["role"] == "user"), "")
    salida = _responder_sin_cache(db, pregunta, historial, anterior)

    if clave and salida["respuesta"] != SIN_LLM:  # si falló la IA no se cachea
        existente = db.get(CacheRespuesta, clave)
        expira = _ahora() + timedelta(hours=settings.CACHE_TTL_HORAS)
        if existente:  # entrada vencida: se renueva
            existente.respuesta, existente.expira_en = salida, expira
        else:
            db.add(CacheRespuesta(clave=clave, respuesta=salida, expira_en=expira))
    return {**salida, "desde_cache": False}


def _responder_sin_cache(db: Session, pregunta: str, historial: list[dict], anterior: str) -> dict:
    # Horarios: se responden con SQL sobre las grillas, sin LLM
    horario = responder_horario(db, pregunta, anterior)
    if horario:
        incrementar(db, "consultas_horario_sql")
        return horario

    # Para preguntas de seguimiento se busca también con la pregunta anterior
    resultados = buscar(db, f"{anterior} {pregunta}".strip())
    if not resultados:
        incrementar(db, "consultas_sin_evidencia")
        return {"respuesta": SIN_EVIDENCIA, "estado": "NO_CONFIRMADA", "fuentes": [], "fecha_informacion": None}

    mensajes = [
        {"role": "system", "content": f"{SISTEMA}\n\nCONTEXTO:\n{_contexto(resultados)}"},
        *historial,
        {"role": "user", "content": pregunta},
    ]
    incrementar(db, "llamadas_llm")
    try:
        return armar_respuesta(llm.completar(mensajes, max_tokens=MAX_TOKENS_RESPUESTA), resultados)
    except Exception as e:
        # Sin cupo o sin servicio de IA: igual se muestran las evidencias
        logger.warning("LLM no disponible: %s", str(e)[:300])
        incrementar(db, "errores_llm")
        return {
            "respuesta": SIN_LLM,
            "estado": "NO_CONFIRMADA",
            "fuentes": [_fuente(n, r) for n, r in enumerate(resultados, 1)],
            "fecha_informacion": None,
        }
