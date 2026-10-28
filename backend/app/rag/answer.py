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
from itertools import zip_longest
import re
from datetime import date, datetime, timedelta, timezone

from sqlalchemy import func
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.ingest.classify import MESES, normalizar
from app.models.cache import CacheRespuesta
from app.models.informacion import Informacion
from app.models.ingesta import Chunk
from app.rag.conversacion import responder_conversacion
from app.rag.extractivo import responder_extractivo
from app.rag.calendario import responder_calendario
from app.rag.horarios import responder_horario
from app.rag.mesas import responder_mesa
from app.rag.search import MAX_RESULTADOS, Resultado, buscar
from app.services import llm
from app.services.autoria import autores, nota_de_carga
from app.services.metricas import incrementar

logger = logging.getLogger(__name__)

MAX_CONTEXTO = 6000  # caracteres (~1500 tokens)
MAX_TOKENS_RESPUESTA = 500
# Con datos de la base (horarios, calendario, mesas) el contexto y la respuesta pueden ser listas largas
MAX_DATOS_BASE = 5000
MAX_TOKENS_CON_DATOS = 1000
FUENTE_BASE = "Datos de la base de la facultad"

SIN_EVIDENCIA = "No encontré información institucional sobre eso."
SIN_LLM = "No pude generar la respuesta en este momento. Estas publicaciones pueden servirte:"

SISTEMA = f"""Sos Juliette, asistente informativa de la UTN Facultad Regional Tucumán.
Reglas:
- Respondé SOLO con la información del CONTEXTO. No inventes fechas, lugares, links, resoluciones ni fuentes.
- Citá cada dato con el número de su fuente entre corchetes, por ejemplo [1].
- Si el contexto no alcanza para responder, respondé exactamente: "{SIN_EVIDENCIA}"
- Si una fuente figura como DESACTUALIZADA, avisalo. Si lo que pregunta solo aparece en fuentes
  DESACTUALIZADAS (por ejemplo, una convocatoria que ya cerró), no digas que no encontraste nada:
  contá qué se publicó y cuándo, aclarando que ya no está vigente y que no hay una versión actual.
- Para "próximo", "cuándo es", "falta mucho" y similares, compará con la FECHA DE HOY: elegí la fecha
  más cercana que sea hoy o posterior, y no presentes como futuras las fechas que ya pasaron.
- Las fechas marcadas "(ya pasó)" son anteriores a hoy: si es el cierre de una inscripción,
  convocatoria o postulación, decí que ya cerró ese día (aunque la fuente figure vigente).
- Si hay mensajes anteriores en la conversación, usalos solo para entender a qué se refiere la
  pregunta actual ("¿y cuándo cierra?", "¿quién la da?"); los datos salen igual del CONTEXTO.
- Una fuente puede ser "Datos de la base de la facultad" (horarios, calendario académico, mesas de
  examen y tribunales, paros): es la información oficial y estructurada. Las fuentes "Carga de
  moderadores" y "Sugerencias de usuarios" son novedades que cargaron personas: si cambian o
  complementan algo de los datos oficiales (una clase virtual, un cambio de aula, una clase suspendida),
  decilo explícitamente en la respuesta, combinándolo con el dato oficial.
- Interpretá la pregunta y respondé lo que la persona necesita, no repitas todo el contexto.
- Respondé en español, breve (máximo 5 oraciones o una lista corta), sin tablas. Si piden una lista
  ("todos los feriados", "qué materias tengo"), listá todos los elementos que correspondan."""

# De mejor a peor: el estado de la respuesta es el peor entre sus fuentes
_ORDEN_ESTADO = ["CONFIRMADA", "PROBABLE", "NO_CONFIRMADA", "CONTRADICTORIA", "DESACTUALIZADA"]


def _ahora() -> datetime:
    return datetime.now(timezone.utc)


ARGENTINA = timezone(timedelta(hours=-3))  # sin horario de verano


def _hoy() -> str:
    return f"{_ahora().astimezone(ARGENTINA):%d/%m/%Y}"


def _utc(fecha: datetime | None) -> datetime | None:
    if fecha and fecha.tzinfo is None:
        return fecha.replace(tzinfo=timezone.utc)
    return fecha


def clave_cache(db: Session, pregunta: str) -> str:
    """Pregunta normalizada + versión de los datos (cambia cuando la ingesta toca algo)."""
    total, ultima = db.query(func.count(Informacion.id), func.max(Informacion.updated_at)).one()
    # Los chunks se pueden regenerar sin tocar informaciones (ej. reextraer PDFs)
    ultimo_chunk = db.query(func.max(Chunk.id)).scalar()
    # La fecha también: "¿cuándo es la próxima mesa?" cambia de respuesta de un día al otro
    base = f"{normalizar(pregunta).strip(' ?¿!¡.')}|{total}|{ultima}|{ultimo_chunk}|{_hoy()}"
    return hashlib.sha256(base.encode("utf-8")).hexdigest()


# "11 de octubre de 2026", "del 10 al 15 de octubre", "11/10/2026" (las numéricas solo con año:
# "24/7" o "1/2" no son fechas). Sin año se asume el de la publicación.
_RE_FECHA_TEXTO = re.compile(
    rf"\b(\d{{1,2}})\s+(?:al\s+(\d{{1,2}})\s+)?de\s+({'|'.join(MESES)})(?:\s+(?:de\s+|del\s+)?(\d{{4}}))?\b",
    re.IGNORECASE)
_RE_FECHA_NUMERICA = re.compile(r"\b(\d{1,2})/(\d{1,2})/(\d{4})\b")


def _fecha(anio: int, mes: int, dia: int) -> date | None:
    try:
        return date(anio, mes, dia)
    except ValueError:
        return None


def marcar_fechas_pasadas(texto: str, publicada: date | None, hoy: date) -> str:
    """Agrega "(ya pasó)" a las fechas anteriores a hoy: los modelos gratis comparan mal
    fechas ("inscripción hasta el 11/10" el 12/10 la daban por abierta)."""
    def marcar(m: re.Match, fecha: date | None) -> str:
        return f"{m.group(0)} (ya pasó)" if fecha and fecha < hoy else m.group(0)

    def por_texto(m: re.Match) -> str:
        anio = int(m.group(4)) if m.group(4) else (publicada or hoy).year
        return marcar(m, _fecha(anio, MESES[m.group(3).lower()], int(m.group(2) or m.group(1))))

    texto = _RE_FECHA_TEXTO.sub(por_texto, texto)
    return _RE_FECHA_NUMERICA.sub(
        lambda m: marcar(m, _fecha(int(m.group(3)), int(m.group(2)), int(m.group(1)))), texto)


def _contexto(resultados: list[Resultado], max_caracteres: int = MAX_CONTEXTO) -> str:
    bloques, largo = [], 0
    hoy = _ahora().astimezone(ARGENTINA).date()
    for n, r in enumerate(resultados, 1):
        fecha = f"{r.fecha:%d/%m/%Y}" if r.fecha else "sin fecha"
        texto = marcar_fechas_pasadas(r.texto, r.fecha.date() if r.fecha else None, hoy)
        bloque = f"[{n}] {r.titulo} — {r.fuente}, {fecha}, estado {r.estado}\n{texto}"
        if largo + len(bloque) > max_caracteres and bloques:
            break
        bloques.append(bloque)
        largo += len(bloque)
    return "\n\n".join(bloques)


def _fuente(n: int, r: Resultado) -> dict:
    return {
        "numero": n,
        "informacion_id": r.informacion_id,
        "titulo": r.titulo,
        "url": r.url,
        "fuente": r.fuente,
        "fecha": r.fecha.date().isoformat() if r.fecha else None,
        "estado": r.estado,
    }


# Información que cargan personas (panel, importaciones, sugerencias aceptadas): ver routers/informacion.py
# y routers/sugerencias.py. Las respuestas con SQL (horarios, calendario, mesas) la suman como novedad.
FUENTES_CARGADAS = ("Carga de moderadores", "Sugerencias de usuarios")
MAX_NOVEDADES = 3
# Palabras que no alcanzan para decir que una novedad habla de lo mismo que la pregunta
_GENERICAS_NOVEDAD = {
    "clase", "clases", "lunes", "martes", "miercoles", "jueves", "viernes", "sabado", "domingo", "manana",
    "hoy", "ayer", "semana", "como", "cuando", "donde", "horario", "horarios", "materia", "materias", "hay",
    "habra", "tengo", "tenemos", "sera", "seran", "esta", "este", "estos", "estas", "para", "sobre", "algun",
    "alguna", "cambio", "cambios", "dato", "datos", "final", "finales", "mesa", "mesas", "examen", "fecha",
    "fechas", "dias", "facultad", "cuatrimestre", "anual", "comision", "aula", "que", "cual", "cuales",
}


def _palabras_clave(texto: str) -> set[str]:
    return {t for t in re.findall(r"[a-z]+", normalizar(texto)) if len(t) >= 4 and t not in _GENERICAS_NOVEDAD}


def _con_novedades(db: Session, pregunta: str, salida: dict) -> dict:
    """
    Horarios, calendario y mesas se responden con SQL sin mirar lo cargado a mano: si alguien cargó
    o sugirió algo sobre lo mismo ("la clase del lunes de Administración de Recursos será virtual"),
    se agrega abajo con quién lo cargó.
    """
    try:
        claves = _palabras_clave(pregunta)
        if not claves:
            return salida
        resultados = [r for r in buscar(db, pregunta, flexible=False)
                      if r.fuente in FUENTES_CARGADAS and claves & _palabras_clave(f"{r.titulo} {r.texto}")]
        ids = list(dict.fromkeys(r.informacion_id for r in resultados))[:MAX_NOVEDADES]
        if not ids:
            return salida
        infos = {i.id: i for i in db.query(Informacion).filter(Informacion.id.in_(ids))}
        autores_por_info = autores(db, ids)
        fuentes = list(salida.get("fuentes", []))
        lineas = ["", "📢 **Novedades cargadas sobre esto:**"]
        for i in ids:
            info = infos.get(i)
            if not info:
                continue
            numero = len(fuentes) + 1
            r = next(r for r in resultados if r.informacion_id == i)
            fuentes.append({**_fuente(numero, r), "titulo": info.titulo})
            cuerpo = info.contenido.strip()
            if cuerpo.startswith(info.titulo):  # la primera línea suele ser el título
                cuerpo = cuerpo[len(info.titulo):].strip()
            lineas.append(f"- **{info.titulo}**" + (f": {cuerpo[:400]}" if cuerpo else "") + f" [{numero}]")
            if i in autores_por_info:
                lineas.append(f"  _{autores_por_info[i]}_")
        return {**salida, "respuesta": salida["respuesta"].rstrip() + "\n" + "\n".join(lineas), "fuentes": fuentes}
    except Exception as e:  # las novedades son un extra: la respuesta principal sale igual
        logger.warning("No se pudieron sumar las novedades: %s", str(e)[:200])
        return salida


def _con_autoria(db: Session, salida: dict) -> dict:
    """Al pie, en cursiva (gris en el chat): quién cargó la información citada, si la cargó una persona."""
    citadas = [f["informacion_id"] for f in salida.get("fuentes", [])
               if f.get("informacion_id") and f"[{f['numero']}]" in salida["respuesta"]]
    try:
        nota = nota_de_carga(db, citadas) if citadas else None
    except Exception as e:  # la nota es un extra: sin ella la respuesta sale igual
        logger.warning("No se pudo saber quién cargó la información: %s", str(e)[:200])
        nota = None
    if nota:
        salida["respuesta"] = f"{salida['respuesta']}\n\n{nota}"
    return salida


def _peor_estado(estados: list[str]) -> str:
    return max(estados, key=lambda e: _ORDEN_ESTADO.index(e) if e in _ORDEN_ESTADO else 0)


def armar_respuesta(texto_llm: str, resultados: list[Resultado]) -> dict:
    """Valida las citas del modelo y arma estado, fuentes y fecha desde la base."""
    if SIN_EVIDENCIA.lower().rstrip(".") in texto_llm.lower():
        return {"respuesta": SIN_EVIDENCIA, "estado": "NO_CONFIRMADA", "fuentes": [], "fecha_informacion": None}

    # "[1, 2]" o "[1-2]" → "[1][2]": el modelo a veces agrupa las citas
    texto_llm = re.sub(r"\[(\d+(?:\s*[,;y-]\s*\d+)+)\]",
                       lambda m: "".join(f"[{n}]" for n in re.findall(r"\d+", m.group(1))), texto_llm)
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


def responder(db: Session, pregunta: str, historial: list[dict], excluir: list[int] | None = None) -> dict:
    """
    Devuelve {respuesta, estado, fuentes, fecha_informacion, desde_cache}.
    `historial`: últimos mensajes de la conversación (formato chat), puede estar vacío.
    `excluir`: "no me sirvió" → informaciones que no se pueden usar (sin caché ni horarios).
    """
    settings = get_settings()
    incrementar(db, "consultas")
    if excluir is not None:
        return {**_buscar_y_responder(db, pregunta, historial, "", excluir), "desde_cache": False}

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

    # Si falló la IA no se cachea: cuando vuelva el cupo, la misma pregunta tendrá respuesta completa
    if clave and salida["respuesta"] != SIN_LLM and not salida.pop("sin_ia", False):
        existente = db.get(CacheRespuesta, clave)
        expira = _ahora() + timedelta(hours=settings.CACHE_TTL_HORAS)
        if existente:  # entrada vencida: se renueva
            existente.respuesta, existente.expira_en = salida, expira
        else:
            db.add(CacheRespuesta(clave=clave, respuesta=salida, expira_en=expira))
    return {**salida, "desde_cache": False}


def _responder_sin_cache(db: Session, pregunta: str, historial: list[dict], anterior: str) -> dict:
    # Saludos, agradecimientos, ayuda: respuestas fijas, sin LLM
    charla = responder_conversacion(pregunta)
    if charla:
        incrementar(db, "conversacion")
        return charla

    # Calendario académico, mesas de examen y horarios salen de la base con SQL. No responden solos:
    # se le pasan a la IA junto con lo que cargaron o sugirieron personas, y ella interpreta la
    # pregunta y arma la respuesta. Si la IA no está disponible, se usa la respuesta armada con SQL.
    # Seguimientos: "¿y el lunes?" después de "¿hay clases mañana?", "¿y Física?" después de una mesa.
    datos = None
    calendario = responder_calendario(db, pregunta) or (
        anterior and responder_calendario(db, anterior) and _es_del_dia(anterior)
        and responder_calendario(db, f"hay clases {pregunta}"))
    if calendario:
        incrementar(db, "consultas_calendario_sql")
        datos = calendario
    if not datos:
        mesa = responder_mesa(db, pregunta) or (
            anterior and responder_mesa(db, anterior) and responder_mesa(db, f"final de {pregunta}"))
        if mesa:
            incrementar(db, "consultas_mesas_sql")
            datos = mesa
    if not datos:
        horario = responder_horario(db, pregunta, anterior)
        if horario:
            incrementar(db, "consultas_horario_sql")
            datos = horario

    return _buscar_y_responder(db, pregunta, historial, anterior, [], datos=datos)


def _es_del_dia(pregunta: str) -> bool:
    return bool(re.search(r"\b(hay clases?|abre|abierta|cerrada|feriado|paro)\b", normalizar(pregunta)))


def _como_fuente(datos: dict) -> Resultado:
    """La respuesta armada con SQL, como fuente del contexto (sin sus números de cita, que cambian)."""
    texto = re.sub(r"\s*\[\d+\]", "", datos["respuesta"])[:MAX_DATOS_BASE]
    origen = (datos.get("fuentes") or [{}])[0]
    return Resultado(chunk_id=0, informacion_id=None, titulo=origen.get("titulo") or FUENTE_BASE, texto=texto,
                     url=origen.get("url") or get_settings().SITE_URL, fuente=FUENTE_BASE, fecha=None,
                     estado="CONFIRMADA", puntaje=0)


def _buscar_y_responder(db: Session, pregunta: str, historial: list[dict], anterior: str,
                        excluir: list[int], datos: dict | None = None) -> dict:
    # Para preguntas de seguimiento se busca también con la pregunta anterior
    # Con la pregunta anterior solo la búsqueda precisa: la flexible traería el tema viejo
    resultados = buscar(db, f"{anterior} {pregunta}".strip(), excluir=excluir, flexible=not anterior)
    if anterior:
        # También con la pregunta sola, intercalada: "y de mecatrónica?" después de programación
        # (con la anterior solo salía programación) o un cambio de tema sin cobertura
        sola = buscar(db, pregunta, excluir=excluir)
        intercalados = [r for par in zip_longest(resultados, sola) for r in par if r]
        vistos: set[int] = set()
        resultados = [r for r in intercalados if not (r.chunk_id in vistos or vistos.add(r.chunk_id))]
        resultados = resultados[:MAX_RESULTADOS]
    if datos:  # los datos de la base van primero: son la fuente [1]
        resultados = [_como_fuente(datos), *resultados]
    if not resultados:
        incrementar(db, "consultas_sin_evidencia")
        return {"respuesta": SIN_EVIDENCIA, "estado": "NO_CONFIRMADA", "fuentes": [], "fecha_informacion": None}

    contexto = _contexto(resultados, max_caracteres=MAX_CONTEXTO + (MAX_DATOS_BASE if datos else 0))
    mensajes = [
        {"role": "system", "content": f"{SISTEMA}\n\nFECHA DE HOY: {_hoy()}\n\nCONTEXTO:\n{contexto}"},
        *historial,
        {"role": "user", "content": pregunta},
    ]
    incrementar(db, "llamadas_llm")
    try:
        texto_llm = llm.completar(mensajes, max_tokens=MAX_TOKENS_CON_DATOS if datos else MAX_TOKENS_RESPUESTA)
    except Exception as e:
        logger.warning("LLM no disponible: %s", str(e)[:300])
        incrementar(db, "errores_llm")
    else:
        salida = armar_respuesta(texto_llm, resultados)
        if not (datos and salida["respuesta"] == SIN_EVIDENCIA):
            return _con_autoria(db, salida)
        # La IA dijo que no sabía pese a tener los datos de la base: vale la respuesta con SQL

    if datos:  # sin IA: la respuesta armada con SQL, más lo cargado por personas sobre lo mismo
        return {**_con_novedades(db, pregunta, datos), "sin_ia": True}

    # Sin cupo o sin servicio de IA: respuesta extractiva con frases textuales de las fuentes
    texto, usados = responder_extractivo(pregunta, resultados)
    if usados:
        incrementar(db, "respuestas_extractivas")
        fuentes = [(n, resultados[n - 1]) for n in usados]
        fechas = [r.fecha for _, r in fuentes if r.fecha]
        return _con_autoria(db, {
            "respuesta": texto,
            "estado": _peor_estado([r.estado for _, r in fuentes]),
            "fuentes": [_fuente(n, r) for n, r in fuentes],
            "fecha_informacion": max(fechas).date().isoformat() if fechas else None,
            "sin_ia": True,
        })
    return {
        "respuesta": SIN_LLM,
        "estado": "NO_CONFIRMADA",
        "fuentes": [_fuente(n, r) for n, r in enumerate(resultados, 1)],
        "fecha_informacion": None,
    }
