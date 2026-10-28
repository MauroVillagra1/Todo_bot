"""
Respuestas del calendario académico con SQL, sin LLM.

  "¿Hay clases mañana?" / "¿El viernes abre la facultad?" → paro, feriado, asueto, receso o día de clases
  "¿Qué feriados hay en noviembre?" / "¿Cuándo es el próximo feriado?"
  "¿Cuándo empieza el segundo cuatrimestre?" / "¿Cuándo son las vacaciones de invierno?"
  "¿Hasta cuándo presento la nota de cambio de comisión?" / "¿Cuándo es la prueba de suficiencia de inglés?"
  "¿Qué hay en el calendario en agosto?"
"""
import re
from datetime import date, timedelta

from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.ingest.horarios import normalizar
from app.models.calendario import EventoCalendario
from app.models.mesa import MesaFecha
from app.rag.fechas import MESES, anio_del_mes, dia, fecha_mencionada, hoy_argentina, mes_mencionado, rango
from app.services.avisos import paros

MAX_EVENTOS = 12
_VERBOS_INICIO_FIN = r"(empieza|empiezan|empieza|inicia|inician|inicio|comienza|comienzan|comienzo|arranca|arrancan|" \
                     r"termina|terminan|fin|finaliza|finalizan|finalizacion|cuando|dura)"
_NOTAS = r"(nota|notas|cambio de comision|ampliacion de cupo|fuera de termino|cambio de plan|baja de regularidad|" \
         r"cursado simultaneo|cambio de especialidad|recursado)"
_PLAZO = r"(cuando|plazo|fecha|fechas|hasta|presento|presentar|presentacion|entregar|entrego|vence)"


def _fuente() -> dict:
    return {"numero": 1, "titulo": "Calendario académico 2026 — Resolución N.º 2394/2025 CD (UTN FRT)",
            "url": get_settings().SITE_URL, "fuente": "UTN FRT", "fecha": None, "estado": "CONFIRMADA"}


def _salida(lineas: list[str], con_fuente: bool = True) -> dict:
    return {"respuesta": "\n".join(lineas).strip(), "estado": "CONFIRMADA",
            "fuentes": [_fuente()] if con_fuente else [], "fecha_informacion": None}


def _linea(e: EventoCalendario, hoy: date) -> str:
    cuando = rango(e.fecha_inicio, e.fecha_fin)
    texto = f"- {cuando[0].upper() + cuando[1:]}: {e.actividad}"
    if e.detalle and e.categoria not in ("FERIADO", "ASUETO"):
        texto += f" ({e.detalle})"
    elif e.detalle:
        texto += f" — {e.detalle}"
    if e.hasta() < hoy:
        texto += " _(ya pasó)_"
    return texto


def responder_calendario(db: Session, pregunta: str, hoy: date | None = None) -> dict | None:
    hoy = hoy or hoy_argentina()
    n = normalizar(pregunta)
    palabras = set(re.findall(r"[a-z]+", n))

    if re.search(r"\b(hay clases?|habra clases?|se dicta clases?|abre la facultad|facultad (esta )?(abierta|cerrada)|"
                 r"esta abierta la facultad|es feriado|hay paro|hay asueto)\b", n):
        return _estado_del_dia(db, fecha_mencionada(pregunta, hoy) or hoy, hoy)

    eventos = db.query(EventoCalendario).order_by(EventoCalendario.fecha_inicio, EventoCalendario.id).all()
    if not eventos:
        return None
    mes = mes_mencionado(pregunta)

    if palabras & {"feriado", "feriados", "asueto", "asuetos", "laborable", "laborables", "finde", "puente"}:
        elegidos = [e for e in eventos if e.categoria in ("FERIADO", "ASUETO")]
        return _lista(elegidos, hoy, mes, "Feriados y asuetos", proximos=6)
    if palabras & {"receso", "vacaciones", "receso"}:
        elegidos = [e for e in eventos if e.categoria == "RECESO"]
        if "invierno" in palabras:
            elegidos = [e for e in elegidos if e.fecha_inicio.month in (6, 7, 8)]
        elif "verano" in palabras:
            elegidos = [e for e in elegidos if e.fecha_inicio.month in (12, 1, 2)]
        return _lista(elegidos, hoy, None, "Receso académico")
    if "suficiencia" in palabras:
        elegidos = [e for e in eventos if e.categoria == "SUFICIENCIA"]
        for clave in ("ingles", "idioma", "informatica", "representacion"):
            if clave in palabras:
                elegidos = [e for e in elegidos if clave in normalizar(e.actividad)] or elegidos
        return _lista(elegidos, hoy, None, "Pruebas de suficiencia")
    if re.search(r"\bmesas? especial(es)?\b", n):
        return _lista([e for e in eventos if "mesas especiales" in normalizar(e.actividad)], hoy, None,
                      "Fechas reservadas para mesas especiales")
    if "equivalencia" in palabras or "equivalencias" in palabras:
        return _lista([e for e in eventos if "equivalencia" in normalizar(e.actividad)], hoy, None, "Equivalencias")
    if re.search(_NOTAS, n) and re.search(rf"\b{_PLAZO}\b", n):
        return _notas(eventos, n, hoy)
    if re.search(r"\b(cuatrimestre|clases|ciclo lectivo|periodo lectivo)\b", n) and re.search(rf"\b{_VERBOS_INICIO_FIN}\b", n) \
            and not re.search(r"\b\d\s*k\s*\d", n):
        return _clases(eventos, n, hoy)
    if re.search(r"\binscripcion(es)?\b.*\b(materias|asignaturas|cursado|cuatrimestre|carreras|cursar)\b", n) \
            and re.search(rf"\b{_PLAZO}\b", n):
        return _lista([e for e in eventos if e.categoria == "INSCRIPCION"], hoy, None, "Inscripciones a cursado")
    if "planillas" in palabras:
        return _lista([e for e in eventos if "planillas" in normalizar(e.actividad)], hoy, None,
                      "Presentación de planillas de regularidad")
    if "calendario" in palabras or (mes and re.search(r"\b(que hay|actividades|fechas importantes|eventos)\b", n)):
        return _mes_o_proximos(db, eventos, hoy, mes)
    return None


def _lista(elegidos: list[EventoCalendario], hoy: date, mes: int | None, titulo: str, proximos: int = 0) -> dict | None:
    if not elegidos:
        return None
    if mes:
        anio = anio_del_mes(mes, hoy, {(e.fecha_inicio.year, e.fecha_inicio.month) for e in elegidos})
        elegidos = [e for e in elegidos if (e.fecha_inicio.year, e.fecha_inicio.month) == (anio, mes)]
        if not elegidos:
            return _salida([f"No hay {titulo.lower()} en {MESES[mes - 1]} de {anio} según el calendario académico [1]."])
        titulo += f" de {MESES[mes - 1]} {anio}"
    elif proximos:
        futuros = [e for e in elegidos if e.hasta() >= hoy]
        elegidos = futuros[:proximos] or elegidos[-proximos:]
        titulo = f"Próximos {titulo.lower()}"
    lineas = [f"{titulo}, según el calendario académico 2026 [1]:", *[_linea(e, hoy) for e in elegidos[:MAX_EVENTOS]]]
    return _salida(lineas)


def _notas(eventos: list[EventoCalendario], n: str, hoy: date) -> dict | None:
    notas = [e for e in eventos if e.categoria == "NOTAS"]
    # Solo las ventanas que mencionan el trámite preguntado (si se nombra uno)
    for tramite in ("cambio de comision", "ampliacion de cupo", "fuera de termino", "cambio de plan",
                    "baja de regularidad", "cursado simultaneo", "cambio de especialidad", "recursado"):
        if tramite in n:
            notas = [e for e in notas if tramite in normalizar(e.actividad)] or notas
            break
    respuesta = _lista(notas, hoy, None, "Plazos para presentar notas")
    if respuesta:
        respuesta["respuesta"] += ("\n\n📄 Los modelos de nota (cambio de comisión, ampliación de cupo, "
                                   "inscripción fuera de término, cambio de plan) se descargan en **Documentos**, en el menú.")
    return respuesta


def _clases(eventos: list[EventoCalendario], n: str, hoy: date) -> dict | None:
    clases = [e for e in eventos if e.categoria == "CLASES"]
    if re.search(r"\b(primer|1er|1|primero|1º|1o)\s*cuatri", n):
        clases = [e for e in clases if "1º" in e.actividad]
    elif re.search(r"\b(segundo|2do|2|2º|2o)\s*cuatri", n):
        clases = [e for e in clases if "2º" in e.actividad]
    if re.search(r"\b(ciclo|periodo) lectivo\b", n):
        clases = [e for e in eventos if "lectivo" in normalizar(e.actividad)] + clases
    return _lista(clases, hoy, None, "Fechas de clases")


def _mes_o_proximos(db: Session, eventos: list[EventoCalendario], hoy: date, mes: int | None) -> dict:
    mesas = db.query(MesaFecha).order_by(MesaFecha.fecha_examen, MesaFecha.mesa).all()
    if mes:
        anio = anio_del_mes(mes, hoy, {(e.fecha_inicio.year, e.fecha_inicio.month) for e in eventos})
        elegidos = [e for e in eventos if (e.fecha_inicio.year, e.fecha_inicio.month) == (anio, mes)
                    or (e.fecha_inicio < date(anio, mes, 1) <= e.hasta())]
        examenes = [m for m in mesas if (m.fecha_examen.year, m.fecha_examen.month) == (anio, mes)]
        titulo = f"Calendario académico de **{MESES[mes - 1]} {anio}** [1]:"
    else:
        elegidos = [e for e in eventos if e.hasta() >= hoy][:8]
        hasta = elegidos[-1].hasta() if elegidos else hoy
        examenes = [m for m in mesas if hoy <= m.fecha_examen <= hasta]
        titulo = "Próximas fechas del calendario académico [1]:"
    lineas = [titulo, *[_linea(e, hoy) for e in elegidos]]
    if examenes:
        lineas += ["", "Exámenes finales:"]
        lineas += [f"- Mesa {'I' * m.mesa}: examen el {dia(m.fecha_examen)} (inscripción hasta el {dia(m.cierre_inscripcion)})"
                   for m in examenes]
    if len(lineas) == 1:
        lineas.append("No hay actividades cargadas para ese período.")
    return _salida(lineas)


def _estado_del_dia(db: Session, d: date, hoy: date) -> dict:
    """¿Hay clases ese día? Paro → feriado/asueto → receso → domingo → período de clases."""
    cuando = "hoy" if d == hoy else "mañana" if d == hoy + timedelta(days=1) else f"el {dia(d)}"
    cuando_txt = f"{cuando} ({dia(d)})" if cuando in ("hoy", "mañana") else cuando
    lineas: list[str] = []
    con_fuente = False

    for p in paros(db, d, d):
        lineas.append(f"⚠️ **{p.titulo}**")
        lineas.append(p.contenido)
        lineas.append("")
    eventos = db.query(EventoCalendario).filter(EventoCalendario.fecha_inicio <= d).all()
    del_dia = [e for e in eventos if e.hasta() >= d]
    no_hay = [e for e in del_dia if e.categoria in ("FERIADO", "RECESO")
              or (e.categoria == "ASUETO" and "academico" in normalizar(e.detalle or ""))]
    administrativo = [e for e in del_dia if e.categoria == "ASUETO" and e not in no_hay]
    clases = [e for e in del_dia if e.categoria == "CLASES" and "Clases del" in e.actividad]

    if no_hay:
        con_fuente = True
        e = no_hay[0]
        motivo = "receso académico" if e.categoria == "RECESO" else f"{(e.detalle or 'feriado').lower()}: {e.actividad}"
        lineas.insert(0, f"No, {cuando_txt} no hay clases: es {motivo} [1].")
    elif lineas:  # hubo paro
        lineas.insert(0, f"{cuando_txt[0].upper() + cuando_txt[1:]} hay paro:")
    elif d.weekday() == 6:
        lineas.append(f"{cuando_txt[0].upper() + cuando_txt[1:]} es domingo: no hay clases.")
    elif clases:
        con_fuente = True
        lineas.append(f"Sí, {cuando_txt} es día de clases ({clases[0].actividad.lower()}) según el calendario "
                      "académico [1]. No hay feriados ni paros cargados para ese día.")
        if administrativo:
            lineas.append(f"Ese día hay {administrativo[0].detalle.lower()} ({administrativo[0].actividad}).")
    else:
        con_fuente = True
        lineas.append(f"{cuando_txt[0].upper() + cuando_txt[1:]} no es período de clases según el calendario "
                      "académico [1] (puede haber mesas de examen o actividades administrativas).")
    return _salida(lineas, con_fuente)
