"""
Respuestas de horarios con SQL, sin LLM (PRO-04: "¿se resuelve con SQL?").

Entiende preguntas como:
  "¿Cuándo se dicta Análisis Matemático I?"      → esa materia en todas las comisiones
  "¿Qué tiene la 2K03 los jueves?"                → grilla de la comisión, filtrada por día
  "¿Quién da Redes de Datos en la 4k2?"           → materia + comisión (con docente)
  "¿Qué electivas hay en 4º año a la noche?"      → electivas filtradas por año y turno

Si la pregunta no es de horarios (o no se encuentra nada), devuelve None y
sigue el RAG normal.
"""
import re
from collections import defaultdict

from sqlalchemy import exists
from sqlalchemy.orm import Session

from app.ingest.horarios import NOMBRE_DIA, normalizar, normalizar_comision, normalizar_materia
from app.models.horario import HorarioClase
from app.models.informacion import EstadoInformacionEnum as E, Evidencia, Informacion
from app.models.ingesta import Documento, Fuente

DIAS = {"lunes": 1, "martes": 2, "miercoles": 3, "jueves": 4, "viernes": 5, "sabado": 6}
PALABRAS_HORARIO = {
    "horario", "horarios", "hora", "horas", "cuando", "dia", "dias", "dicta", "dictan", "dictado",
    "cursa", "curso", "cursan", "cursar", "cursada", "clase", "clases", "aula", "aulas", "comision",
    "comisiones", "materia", "materias", "tiene", "tengo", "tienen", "profesor", "profesora", "profe",
    "docente", "docentes", "quien", "da", "dan", "electiva", "electivas", "turno", "lab", "laboratorio",
}
VACIAS = {"de", "la", "el", "los", "las", "y", "del", "en", "a", "para", "que", "con", "un", "una", "e"}
ROMANOS = {"1": "i", "2": "ii", "3": "iii", "4": "iv", "5": "v"}
_ES_ROMANO = {"i", "ii", "iii", "iv", "v"}
ORDINALES = {"primer": 1, "primero": 1, "segundo": 2, "tercer": 3, "tercero": 3, "cuarto": 4, "quinto": 5}
MAX_LINEAS = 45
_ESTADOS_EXCLUIDOS = (E.DESACTUALIZADA, E.REEMPLAZADA)


def _tokens(texto: str) -> list[str]:
    return [ROMANOS.get(t, t) for t in normalizar_materia(texto).split()]


def _coincide(q: str, m: str) -> bool:
    if m in _ES_ROMANO or q in _ES_ROMANO:
        return q == m
    if len(m) < 3 or len(q) < 3:
        return q == m
    # Abreviaturas del PDF ("algorit", "est", "arq") contra palabras completas, y viceversa
    return q.startswith(m) or m.startswith(q)


def _puntaje(preg: list[str], materia_norm: str) -> float:
    claves = [t for t in _tokens(materia_norm) if t not in VACIAS and (len(t) >= 2 or t in _ES_ROMANO)]
    if not claves:
        return 0.0
    # El número de la materia tiene que coincidir: "Análisis Matemático 1" no es "II"
    num_materia = next((t for t in claves if t in _ES_ROMANO), None)
    num_preg = [t for t in preg if t in _ES_ROMANO]
    if num_materia and num_preg and num_materia not in num_preg:
        return 0.0
    sin_numero = [t for t in claves if t not in _ES_ROMANO]
    acertadas = sum(any(_coincide(q, t) for q in preg) for t in sin_numero)
    if acertadas < min(2, len(sin_numero)):
        return 0.0
    return acertadas / len(sin_numero)


def _filtros(pregunta: str) -> dict:
    n = normalizar(pregunta)
    palabras = set(re.findall(r"[a-z0-9]+", n))
    anio = None
    if m := re.search(r"\b([1-5])\s*(?:er|ero|do|ro|to|vo|°|º|o)?\s*ano\b", n):
        anio = int(m.group(1))
    elif m := re.search(r"\b(primer|primero|segundo|tercer|tercero|cuarto|quinto)\s+ano\b", n):
        anio = ORDINALES[m.group(1)]
    return {
        "comisiones": {c for c in (normalizar_comision(x) for x in re.findall(r"\b\d\s*k\s*\d{1,2}\b", n)) if c},
        "dias": {DIAS[d] for d in palabras if d in DIAS},
        "turno": next((t for t in ("mañana", "tarde", "noche") if normalizar(t) in palabras), None),
        "plan": (m.group(1) if (m := re.search(r"plan\s*(20\d\d)", n)) else None),
        "anio": anio,
        "electivas": bool(palabras & {"electiva", "electivas"}),
        "es_horario": bool(palabras & PALABRAS_HORARIO),
    }


def _vigentes(db: Session):
    """Bloques de PDFs vigentes cuya información no está desactualizada."""
    vigente = exists().where(
        Evidencia.documento_id == Documento.id,
        Evidencia.informacion_id == Informacion.id,
        Informacion.estado.notin_(_ESTADOS_EXCLUIDOS),
    )
    return (
        db.query(HorarioClase, Documento)
        .join(Documento, Documento.id == HorarioClase.documento_id)
        .filter(Documento.vigente.is_(True), vigente)
    )


def _materias_de(db: Session, pregunta: str) -> list[str]:
    preg = _tokens(pregunta)
    catalogo = {m for (m,) in db.query(HorarioClase.materia_norm).distinct()}
    puntajes = {m: _puntaje(preg, m) for m in catalogo}
    mejor = max(puntajes.values(), default=0)
    if mejor < 0.6:
        return []
    return [m for m, p in puntajes.items() if p >= mejor - 0.15]


def responder_horario(db: Session, pregunta: str, anterior: str = "") -> dict | None:
    f = _filtros(pregunta)
    materias = _materias_de(db, pregunta)
    # Seguimiento ("¿y los martes?"): comisión/materia de la pregunta anterior
    if anterior and not f["comisiones"] and not materias:
        previo = _filtros(anterior)
        f["comisiones"] = previo["comisiones"]
        materias = _materias_de(db, anterior)
        f["es_horario"] = f["es_horario"] or previo["es_horario"]

    if not (f["comisiones"] or materias or (f["electivas"] and (f["anio"] or f["turno"]))):
        return None
    if not f["es_horario"] and not f["comisiones"]:
        return None  # "¿Hay becas para sistemas de información?" no es de horarios

    consulta = _vigentes(db)
    if f["comisiones"]:
        consulta = consulta.filter(HorarioClase.comision.in_(f["comisiones"]))
    if materias:
        consulta = consulta.filter(HorarioClase.materia_norm.in_(materias))
    if f["dias"]:
        consulta = consulta.filter(HorarioClase.dia.in_(f["dias"]))
    if f["plan"]:
        consulta = consulta.filter(HorarioClase.plan == f["plan"])
    if f["anio"]:
        consulta = consulta.filter(HorarioClase.anio == f["anio"])
    if f["electivas"]:
        consulta = consulta.filter(HorarioClase.electiva.is_(True))
    filas = consulta.all()
    if f["turno"]:
        filas = [(h, d) for h, d in filas if h.turno and f["turno"] in h.turno.lower()]
    if not filas:
        return None

    # Si la misma comisión/período aparece en varios PDFs, vale el más reciente
    def fecha(d: Documento):
        return d.fecha_publicacion or d.fecha_captura

    mas_reciente: dict[tuple, Documento] = {}
    for h, d in filas:
        clave = (h.plan, h.comision, h.periodo)
        if clave not in mas_reciente or fecha(d) > fecha(mas_reciente[clave]):
            mas_reciente[clave] = d
    filas = [(h, d) for h, d in filas if mas_reciente[(h.plan, h.comision, h.periodo)].id == d.id]

    # Agrupar por comisión (y plan/período), ordenado por día y hora
    grupos: dict[tuple, list[HorarioClase]] = defaultdict(list)
    for h, _ in filas:
        grupos[(h.plan or "", h.comision or "", h.periodo or "", h.turno or "", h.aula or "")].append(h)

    docs = sorted({d.id: d for _, d in filas}.values(), key=lambda d: d.id)
    numero = {d.id: i for i, d in enumerate(docs, 1)}
    doc_de = {h.id: d for h, d in filas}

    titulo = "Horarios"
    if materias:
        nombres = sorted({h.materia for h, _ in filas})
        titulo += " de " + " / ".join(f"**{n}**" for n in nombres[:3])
    if f["dias"]:
        titulo += " (" + ", ".join(NOMBRE_DIA[d] for d in sorted(f["dias"])) + ")"
    lineas = [f"{titulo}, según los horarios publicados por el Departamento de Sistemas:", ""]

    for (plan, comision, periodo, turno, aula), bloques in sorted(grupos.items(), key=lambda g: (g[0][1], g[0][0])):
        datos = ", ".join(x for x in (f"Plan {plan}" if plan else "", periodo, f"turno {turno.lower()}" if turno else "",
                                      f"aula {aula}" if aula else "") if x)
        cita = f"[{numero[doc_de[bloques[0].id].id]}]"
        lineas.append(f"**{comision or 'Sin comisión'}** ({datos}) {cita}")
        for b in sorted(bloques, key=lambda b: (b.dia, b.inicio)):
            extra = "".join(x for x in (f" (electiva)" if b.electiva else "",
                                        f" — {b.docente}" if b.docente else "", f" — {b.lugar}" if b.lugar else ""))
            materia = "" if len(materias) == 1 and not f["electivas"] else f" {b.materia}"
            lineas.append(f"- {NOMBRE_DIA[b.dia]} {b.inicio} a {b.fin}:{materia}{extra}".replace(": —", ":").rstrip(":"))
        lineas.append("")
        if len(lineas) > MAX_LINEAS:
            lineas.append("_(Hay más resultados: indicá una comisión o un día para acotar.)_")
            break

    fuentes_nombre = dict(db.query(Fuente.id, Fuente.nombre).all())
    estados = dict(
        db.query(Evidencia.documento_id, Informacion.estado)
        .join(Informacion, Informacion.id == Evidencia.informacion_id)
        .filter(Evidencia.documento_id.in_([d.id for d in docs]))
        .all()
    )
    fuentes = [
        {
            "numero": numero[d.id],
            "titulo": d.nombre or d.url.rsplit("/", 1)[-1],
            "url": d.url,
            "fuente": fuentes_nombre.get(d.fuente_id, ""),
            "fecha": fecha(d).date().isoformat() if fecha(d) else None,
            "estado": estados[d.id].value if d.id in estados else "CONFIRMADA",
        }
        for d in docs
    ]
    fechas = [x["fecha"] for x in fuentes if x["fecha"]]
    return {
        "respuesta": "\n".join(lineas).strip(),
        "estado": "CONFIRMADA" if all(x["estado"] == "CONFIRMADA" for x in fuentes) else "PROBABLE",
        "fuentes": fuentes,
        "fecha_informacion": max(fechas) if fechas else None,
    }
