"""
Respuestas de horarios con SQL, sin LLM (PRO-04: "¿se resuelve con SQL?").

Entiende preguntas como:
  "¿Cuándo se dicta Análisis Matemático I?"      → esa materia en todas las comisiones
  "¿Qué tiene la 2K03 los jueves?"                → grilla de la comisión, filtrada por día
  "¿Quién da Redes de Datos en la 4k2?"           → materia + comisión (con docente)
  "¿Qué materias da Moyano?"                      → todas las clases de ese docente
  "¿Qué electivas hay en 4º año a la noche?"      → electivas filtradas por año y turno

Si la pregunta no es de horarios (o no se encuentra nada), devuelve None y
sigue el RAG normal.
"""
import re
from collections import defaultdict
from datetime import date

from sqlalchemy import and_, exists, or_
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.ingest.horarios import NOMBRE_DIA, normalizar, separar_docentes, normalizar_comision, normalizar_materia
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
# Preguntas de exámenes ("¿cuándo rindo Física?"): van a la búsqueda de mesas, no a las grillas
PALABRAS_EXAMEN = {
    "rindo", "rendir", "rinde", "rinden", "rendimos", "mesa", "mesas", "final", "finales", "examen", "examenes",
}
VACIAS = {"de", "la", "el", "los", "las", "y", "del", "en", "a", "para", "que", "con", "un", "una", "e"}
ROMANOS = {"1": "i", "2": "ii", "3": "iii", "4": "iv", "5": "v"}
_ES_ROMANO = {"i", "ii", "iii", "iv", "v"}
ORDINALES = {"primer": 1, "primero": 1, "segundo": 2, "tercer": 3, "tercero": 3, "cuarto": 4, "quinto": 5}
MAX_LINEAS = 45
MAX_OPCIONES = 6
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


# Palabras de la pregunta que no son parte del nombre de una materia
RUIDO = {
    "que", "cual", "cuales", "cuando", "como", "donde", "hay", "es", "son", "se", "me", "mi", "mis",
    "esta", "este", "estan", "ano", "plan", "cuatrimestre", "primer", "primero", "segundo", "tercer",
    "tercero", "cuarto", "quinto", "manana", "tarde", "noche", "quiero", "necesito", "saber", "sabes",
    "por", "favor", "decime", "dime", "busco", "sobre", "hoy", "semana", "todas",
    "todos", "o", "u", "al", "las", "los", "lo", "le", "les", "yo", "vos", "tu", "su", "sus",
}


def _claves(materia_norm: str) -> list[str]:
    return [t for t in _tokens(materia_norm) if t not in VACIAS and (len(t) >= 2 or t in _ES_ROMANO)]


def _contenido(preg: list[str]) -> list[str]:
    """Palabras de la pregunta que podrían ser parte del nombre de la materia."""
    return [t for t in preg if t not in RUIDO and t not in VACIAS and t not in PALABRAS_HORARIO
            and t not in DIAS and t not in _ES_ROMANO and not re.fullmatch(r"\d+k?\d*|20\d\d", t)]


def _puntaje(preg: list[str], materia_norm: str) -> float:
    claves = _claves(materia_norm)
    if not claves:
        return 0.0
    # El número de la materia tiene que coincidir: "Análisis Matemático 1" no es "II"
    num_materia = next((t for t in claves if t in _ES_ROMANO), None)
    num_preg = [t for t in preg if t in _ES_ROMANO]
    if num_materia and num_preg and num_materia not in num_preg:
        return 0.0
    sin_numero = [t for t in claves if t not in _ES_ROMANO]
    acertadas = sum(any(_coincide(q, t) for q in preg) for t in sin_numero)
    cobertura_materia = acertadas / len(sin_numero)
    if acertadas >= min(2, len(sin_numero)) and cobertura_materia >= 0.6:
        return cobertura_materia
    # La pregunta nombra la materia en forma corta ("diseño ux" → "Diseño UX para productos
    # digitales"): todas sus palabras de contenido están en la materia
    contenido = _contenido(preg)
    if contenido and sum(len(t) for t in contenido) >= 4 \
            and all(any(_coincide(q, t) for t in sin_numero) for q in contenido):
        return 0.6 + 0.3 * cobertura_materia
    return 0.0


def _equivalentes(a: str, b: str) -> bool:
    """Misma materia escrita distinto ("algorit y est de datos" / "algoritmos y estructuras de datos")."""
    ca, cb = _claves(a), _claves(b)
    return bool(ca and cb) and all(any(_coincide(x, y) for y in cb) for x in ca) \
        and all(any(_coincide(y, x) for x in ca) for y in cb)


def _agrupar(materias: list[str]) -> list[list[str]]:
    grupos: list[list[str]] = []
    for m in sorted(materias, key=len, reverse=True):
        grupo = next((g for g in grupos if _equivalentes(g[0], m)), None)
        if grupo:
            grupo.append(m)
        else:
            grupos.append([m])
    return grupos


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
        "periodo": ("Primer cuatrimestre" if re.search(r"\b(primer|1er|1)\s*cuatri", n)
                    else "Segundo cuatrimestre" if re.search(r"\b(segundo|2do|2)\s*cuatri", n) else None),
        "es_horario": bool(palabras & PALABRAS_HORARIO),
        "es_examen": bool(palabras & PALABRAS_EXAMEN),
    }


def vigentes(db: Session):
    """
    Bloques de PDFs vigentes cuya información no está desactualizada, más los
    cargados a mano por un ADMIN (sin documento). Devuelve (HorarioClase, Documento | None).
    """
    vigente = exists().where(
        Evidencia.documento_id == Documento.id,
        Evidencia.informacion_id == Informacion.id,
        Informacion.estado.notin_(_ESTADOS_EXCLUIDOS),
    )
    return (
        db.query(HorarioClase, Documento)
        .outerjoin(Documento, Documento.id == HorarioClase.documento_id)
        .filter(or_(HorarioClase.documento_id.is_(None), and_(Documento.vigente.is_(True), vigente)))
    )


def _fecha(d: Documento):
    return d.fecha_publicacion or d.fecha_captura


def mas_recientes(filas: list[tuple]) -> list[tuple]:
    """
    Si la misma comisión/período aparece en varios PDFs, vale el más reciente.
    Los bloques cargados a mano (sin documento) siempre quedan.
    """
    mas_reciente: dict[tuple, Documento] = {}
    for h, d in filas:
        clave = (h.plan, h.comision, h.periodo)
        if d is not None and (clave not in mas_reciente or _fecha(d) > _fecha(mas_reciente[clave])):
            mas_reciente[clave] = d
    return [(h, d) for h, d in filas if d is None or mas_reciente[(h.plan, h.comision, h.periodo)].id == d.id]


def _materias_de(db: Session, pregunta: str) -> list[str]:
    preg = _tokens(pregunta)
    catalogo = {m for (m,) in db.query(HorarioClase.materia_norm).distinct()}
    puntajes = {m: _puntaje(preg, m) for m in catalogo}
    mejor = max(puntajes.values(), default=0)
    if mejor < 0.6:
        return []
    return [m for m, p in puntajes.items() if p >= mejor - 0.15]


def _personas(docente: str) -> list[str]:
    """'Vicente Francisco - Chibilisco Vicente' → dos personas (normalizadas)."""
    return [normalizar(p).replace(",", "") for p in separar_docentes(docente)]


def _docentes_texto(docente: str | None) -> str:
    """'Such Victor - Aparicio Gabriela' → 'Such Victor y Aparicio Gabriela'."""
    personas = separar_docentes(docente)
    return ", ".join(personas[:-1]) + " y " + personas[-1] if len(personas) > 1 else "".join(personas)


def _docentes_de(db: Session, pregunta: str) -> list[str]:
    """
    Personas nombradas en la pregunta (apellido y/o nombre), comparando con los
    docentes que figuran en los horarios. Todas las palabras de nombre que se
    reconocen en la pregunta tienen que estar en la misma persona.
    """
    personas = {p for (d,) in db.query(HorarioClase.docente).filter(HorarioClase.docente.isnot(None)).distinct()
                for p in _personas(d)}
    vocabulario = {t for p in personas for t in p.split() if len(t) >= 3}
    preg = [t for t in re.findall(r"[a-z]+", normalizar(pregunta))
            if len(t) >= 3 and t not in VACIAS and t not in PALABRAS_HORARIO and t not in DIAS]
    nombres = [t for t in preg if t in vocabulario]
    if not nombres:
        return []
    return sorted(p for p in personas if all(n in p.split() for n in nombres))


_SIGLAS = {"UX", "UI", "UX/UI", "IA", "TIC", "TICS", "IT", "I", "II", "III", "IV", "V", "GIS", "SIG"}


def bonito(nombre: str) -> str:
    """'DISEÑO UX PARA PRODUCTOS DIGITALES' → 'Diseño UX para productos digitales'."""
    if not nombre.isupper():
        return nombre
    palabras = [p if p in _SIGLAS else p.lower() for p in nombre.split()]
    if palabras and palabras[0] not in _SIGLAS:
        palabras[0] = palabras[0].capitalize()
    return " ".join(palabras)


def _materia_exacta(pregunta: str, materias: list[str]) -> bool:
    """La pregunta es solo el nombre de una materia ("diseño ux", "Redes de Datos")."""
    contenido = _contenido(_tokens(pregunta))
    return bool(materias) and len(contenido) == len([t for t in _tokens(pregunta) if t not in VACIAS])


def _aclaracion(db: Session, grupos: list[list[str]]) -> dict:
    """Pide precisar cuál materia, con opciones y un ejemplo de pregunta."""
    opciones = []  # (nombre, una comisión donde se dicta)
    for grupo in grupos:
        filas = db.query(HorarioClase.materia, HorarioClase.comision).filter(HorarioClase.materia_norm.in_(grupo)).all()
        cuenta: dict[str, int] = defaultdict(int)
        for m, _ in filas:
            cuenta[m] += 1
        if cuenta:
            nombre = max(cuenta, key=lambda g: (cuenta[g], sum(not c.isascii() for c in g)))
            opciones.append((bonito(nombre), next((c for _, c in filas if c), None)))
    opciones.sort()
    lineas = ["Encontré varias materias que coinciden. ¿A cuál te referís?", ""]
    lineas += [f"- {n}" for n, _ in opciones[:MAX_OPCIONES]]
    if len(opciones) > MAX_OPCIONES:
        lineas.append(f"- …y {len(opciones) - MAX_OPCIONES} más (probá con un nombre más completo)")
    ejemplo, comision = opciones[0]
    lineas += ["", f"Por ejemplo: “¿Cuándo se dicta {ejemplo}?”"
               + (f" o “¿Qué días tiene {ejemplo} la {comision}?”" if comision else "")]
    return {"respuesta": "\n".join(lineas), "estado": "ACLARACION", "fuentes": [], "fecha_informacion": None}


def cuatrimestre_terminado(hoy: date | None = None) -> str:
    """El cuatrimestre que no está en curso: de agosto a diciembre ya pasó el primero."""
    hoy = hoy or date.today()
    return "Primer cuatrimestre" if hoy.month >= 8 else "Segundo cuatrimestre"


def responder_horario(db: Session, pregunta: str, anterior: str = "", hoy: date | None = None) -> dict | None:
    f = _filtros(pregunta)
    if f["es_examen"] and not f["comisiones"]:
        return None
    materias = _materias_de(db, pregunta)
    docentes = _docentes_de(db, pregunta) if not materias else []
    # Seguimiento ("¿y los martes?"): comisión/materia de la pregunta anterior
    if anterior and not f["comisiones"] and not materias:
        previo = _filtros(anterior)
        f["comisiones"] = previo["comisiones"]
        materias = _materias_de(db, anterior)
        f["es_horario"] = f["es_horario"] or previo["es_horario"]

    if not (f["comisiones"] or materias or docentes or (f["electivas"] and (f["anio"] or f["turno"]))):
        return None
    if not f["es_horario"] and not f["comisiones"] and not _materia_exacta(pregunta, materias):
        return None  # "¿Hay becas para sistemas de información?" no es de horarios

    # Varias materias distintas coinciden y no hay comisión que acote: preguntar a cuál se refiere
    grupos = _agrupar(materias)
    if len(grupos) > 1 and not f["comisiones"] and not docentes:
        return _aclaracion(db, grupos)

    consulta = vigentes(db)
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
    if docentes:
        filas = [(h, d) for h, d in filas if h.docente and set(_personas(h.docente)) & set(docentes)]
    # Cuatrimestre: el pedido, o si no se pide, se ocultan los horarios del que no está en curso.
    # Por docente se muestra todo el año ("¿qué materias da Paredi?" incluye el 1er cuatrimestre).
    if f["periodo"]:
        filas = [(h, d) for h, d in filas if h.periodo in (f["periodo"], "Anual", None)]
    elif not docentes:
        filas = [(h, d) for h, d in filas if h.periodo != cuatrimestre_terminado(hoy)]
    if not filas:
        return None

    filas = mas_recientes(filas)
    fecha = _fecha

    # Si una comisión figura en dos planes (2008 y 2023), se muestra el más nuevo,
    # salvo que se pida un plan. Si la materia solo existe en el plan viejo, queda.
    planes_omitidos = set()
    if not f["plan"]:
        plan_nuevo: dict[str | None, str] = {}
        for h, _ in filas:
            plan_nuevo[h.comision] = max(plan_nuevo.get(h.comision, ""), h.plan or "")
        planes_omitidos = {h.plan for h, _ in filas if (h.plan or "") != plan_nuevo[h.comision]}
        filas = [(h, d) for h, d in filas if (h.plan or "") == plan_nuevo[h.comision]]

    # Agrupar por comisión (y plan/período), ordenado por día y hora
    grupos: dict[tuple, list[HorarioClase]] = defaultdict(list)
    for h, _ in filas:
        grupos[(h.plan or "", h.comision or "", h.periodo or "", h.turno or "", h.aula or "")].append(h)

    docs = sorted({d.id: d for _, d in filas if d is not None}.values(), key=lambda d: d.id)
    numero: dict[int | None, int] = {d.id: i for i, d in enumerate(docs, 1)}
    hay_manuales = any(d is None for _, d in filas)
    if hay_manuales:
        numero[None] = len(docs) + 1  # bloques cargados a mano en el panel
    doc_de = {h.id: (d.id if d else None) for h, d in filas}

    # Una materia puede venir escrita distinto ("Analisis Matematico I" / "Análisis Matemático I"):
    # se agrupa por su forma normalizada y se muestra la grafía más común (con tildes si empata)
    grafias: dict[str, dict[str, int]] = defaultdict(lambda: defaultdict(int))
    for h, _ in filas:
        grafias[h.materia_norm][h.materia] += 1
    nombre_de = {
        norma: bonito(max(cuenta, key=lambda g: (cuenta[g], sum(not c.isascii() for c in g))))
        for norma, cuenta in grafias.items()
    }
    varias_materias = len(nombre_de) > 1 or f["electivas"] or bool(docentes)

    titulo = "Horarios"
    if materias:
        titulo += " de " + " / ".join(f"**{n}**" for n in sorted(nombre_de.values())[:3])
    elif docentes:
        titulo = "Clases de " + " / ".join(f"**{p.title()}**" for p in docentes[:3])
        if len(docentes) > 3:
            titulo += f" (y {len(docentes) - 3} docentes más con ese nombre)"
    if f["dias"]:
        titulo += " (" + ", ".join(NOMBRE_DIA[d] for d in sorted(f["dias"])) + ")"
    lineas = [f"{titulo}, según los horarios publicados por el Departamento de Sistemas:", ""]

    for (plan, comision, periodo, turno, aula), bloques in sorted(grupos.items(), key=lambda g: (g[0][1], g[0][0])):
        datos = ", ".join(x for x in (f"Plan {plan}" if plan else "", periodo, f"turno {turno.lower()}" if turno else "",
                                      f"aula {aula}" if aula else "") if x)
        cita = " ".join(f"[{n}]" for n in sorted({numero[doc_de[b.id]] for b in bloques}))
        lineas.append(f"**{comision or 'Sin comisión'}** ({datos}) {cita}")
        for b in sorted(bloques, key=lambda b: (b.dia, b.inicio)):
            extra = "".join(x for x in (f" (electiva)" if b.electiva else "",
                                        f" — {_docentes_texto(b.docente)}" if _docentes_texto(b.docente) else "", f" — {b.lugar}" if b.lugar else ""))
            materia = f" {nombre_de[b.materia_norm]}" if varias_materias else ""
            lineas.append(f"- {NOMBRE_DIA[b.dia]} {b.inicio} a {b.fin}:{materia}{extra}".replace(": —", ":").rstrip(":"))
        lineas.append("")
        if len(lineas) > MAX_LINEAS:
            lineas.append("_(Hay más resultados: indicá una comisión o un día para acotar.)_")
            break
    if planes_omitidos:
        viejos = ", ".join(sorted(p for p in planes_omitidos if p))
        lineas.append(f"_Se muestra el plan más reciente. Si cursás el plan {viejos}, preguntá indicando “plan {viejos}”._")

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
    if hay_manuales:
        fuentes.append({
            "numero": numero[None], "titulo": "Horarios cargados por la administración", "url": get_settings().SITE_URL,
            "fuente": "UTNIA", "fecha": None, "estado": "CONFIRMADA",
        })
    fechas = [x["fecha"] for x in fuentes if x["fecha"]]
    return {
        "respuesta": "\n".join(lineas).strip(),
        "estado": "CONFIRMADA" if all(x["estado"] == "CONFIRMADA" for x in fuentes) else "PROBABLE",
        "fuentes": fuentes,
        "fecha_informacion": max(fechas) if fechas else None,
    }
