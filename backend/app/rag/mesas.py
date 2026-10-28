"""
Respuestas de mesas de examen final con SQL, sin LLM.

  "¿Cuándo rindo Sistemas Operativos?"     → su mesa, próximas fechas (examen e inscripción) y tribunal
  "¿Qué materias se rinden en la mesa 2?"  → materias de esa mesa y sus próximas fechas
  "¿Cuándo son las mesas de diciembre?"    → los turnos de ese mes
  "¿Cuándo son las próximas mesas?"        → el próximo turno de cada mesa
  "¿En qué mesas está Zamudio?"            → tribunales donde figura esa persona
  "¿Quiénes evalúan Física I en el final?" → el tribunal primero (presidente y vocales), después las fechas
Siempre recuerda que la regularidad es permanente y que con 4 aplazos se recursa.
"""
import re
from collections import defaultdict
from datetime import date

from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.ingest.horarios import normalizar
from app.models.mesa import MesaFecha, MesaMateria
from app.rag.fechas import MESES, anio_del_mes, dia, hoy_argentina, mes_mencionado
from app.rag.horarios import (
    DIAS, PALABRAS_HORARIO, RUIDO, VACIAS, _ES_ROMANO, _coincide, _tokens, bonito, materias_que_coinciden,
)

REGLA = ("📌 **La regularidad de una materia es permanente** (no vence). "
         "Si desaprobás el final **4 veces**, tenés que recursar la materia.")
PALABRAS_MESA = {
    "rindo", "rendir", "rinde", "rinden", "rendimos", "rindes", "mesa", "mesas", "final", "finales",
    "examen", "examenes", "tribunal", "tribunales", *(_TRIBUNAL := {
        "presidente", "presidentes", "vocal", "vocales", "evalua", "evaluan", "evaluador", "evaluadores",
        "evaluadora", "jurado", "jurados", "integra", "integran", "conforman", "componen", "toma", "toman",
    }),
}
# Preguntas sobre la regularidad sin hablar de una mesa: se responde solo la regla
_REGULARIDAD = re.compile(r"\b(regularidad\b.*\b(vence|dura|permanente|pierd|caduc)|aplazos?|recursar|cuantas veces|cuantos intentos)")
# No son exámenes finales: van al calendario académico
_OTROS_EXAMENES = {"suficiencia", "especial", "especiales", "parcial", "parciales", "ingreso"}
# Palabras de una pregunta de mesas que no son parte del nombre de una materia
_GENERICAS = PALABRAS_MESA | {
    "inscripcion", "inscribo", "inscribirme", "inscribir", "anotar", "anoto", "anotarme", "proxima", "proximas",
    "proximo", "proximos", "fecha", "fechas", "turno", "turnos", "llamado", "llamados", "hora", "cierre",
    "cierra", "hasta", "puedo", "presidente", "vocal", "vocales", "quien", "quienes", "toma", "toman", "dia",
    "mes", "este", "esta", "va", "sera", "seran", "cuando", "donde", "sede", "anexo", "concepcion", "central",
    "casa", "isi", "sistemas", "ingenieria", "rendir", *[normalizar(m) for m in MESES], "setiembre",
    "profesor", "profesores", "profesora", "docente", "docentes", "me", "nos", "integrantes", "miembros",
}
MAX_FECHAS = 3


def _romano(n: int) -> str:
    return {1: "I", 2: "II", 3: "III"}.get(n, str(n))


def _mesa_pedida(n: str) -> int | None:
    if m := re.search(r"\bmesa\s*(iii|ii|i|1|2|3)\b", n):
        return {"i": 1, "ii": 2, "iii": 3}.get(m.group(1)) or int(m.group(1))
    return None


def _fuentes(con_tribunal: bool) -> list[dict]:
    url = get_settings().SITE_URL
    fuentes = [{"numero": 1, "titulo": "Calendario académico 2026 (Res. 2394/2025 CD) — turnos de exámenes finales",
                "url": url, "fuente": "UTN FRT", "fecha": None, "estado": "CONFIRMADA"}]
    if con_tribunal:
        fuentes.append({"numero": 2, "titulo": "Tribunales docentes — mesas de examen final 2025 (I.S.I.)",
                        "url": url, "fuente": "UTN FRT", "fecha": None, "estado": "CONFIRMADA"})
    return fuentes


def _salida(lineas: list[str], con_tribunal: bool = False) -> dict:
    lineas += ["", REGLA]
    return {"respuesta": "\n".join(lineas).strip(), "estado": "CONFIRMADA",
            "fuentes": _fuentes(con_tribunal), "fecha_informacion": None}


def _linea_fecha(f: MesaFecha, hoy: date, con_mesa: bool = False) -> str:
    quien = f"Mesa {_romano(f.mesa)} — " if con_mesa else ""
    turno = f"{f.turno}º turno: " if f.turno else ""
    texto = f"- {quien}{turno}examen el **{dia(f.fecha_examen)}** · inscripción hasta el {dia(f.cierre_inscripcion)}"
    if f.cierre_inscripcion < hoy <= f.fecha_examen:
        texto += " _(inscripción cerrada)_"
    return texto


def _proximas(fechas: list[MesaFecha], mesa: int, hoy: date) -> list[MesaFecha]:
    return [f for f in fechas if f.mesa == mesa and f.fecha_examen >= hoy][:MAX_FECHAS]


def _tribunal(t: MesaMateria) -> str:
    hora = f"{t.hora} h" if t.hora else "hora a confirmar"
    if not t.presidente:
        return f"- {t.sede}, {hora}: tribunal a confirmar"
    vocales = [v for v in (t.vocal1, t.vocal2) if v]
    texto = f"- {t.sede}, {hora}: {t.presidente} (presidente)"
    return texto + (f"; vocales: {' y '.join(vocales)}" if vocales else "")


def _personas(db: Session, pregunta: str) -> list[str]:
    nombres = {p for fila in db.query(MesaMateria.presidente, MesaMateria.vocal1, MesaMateria.vocal2).all()
               for p in fila if p}
    vocabulario = {t for p in nombres for t in normalizar(p).split() if len(t) >= 4}
    preg = [t for t in re.findall(r"[a-z]+", normalizar(pregunta))
            if len(t) >= 4 and t not in _GENERICAS and t not in PALABRAS_HORARIO]
    claves = [t for t in preg if t in vocabulario]
    if not claves:
        return []
    return sorted(p for p in nombres if all(c in normalizar(p).split() for c in claves))


def _resto(pregunta: str) -> list[str]:
    """Palabras que podrían nombrar una materia (si no coincide ninguna, la pregunta no es para esto)."""
    return [t for t in _tokens(pregunta)
            if t not in _GENERICAS and t not in RUIDO and t not in VACIAS and t not in DIAS
            and t not in _ES_ROMANO and not re.fullmatch(r"\d+", t) and len(t) > 2
            and t not in {"materia", "materias", "hay", "son", "las", "los", "que", "cuales"}]


def responder_mesa(db: Session, pregunta: str, hoy: date | None = None) -> dict | None:
    hoy = hoy or hoy_argentina()
    n = normalizar(pregunta)
    palabras = set(re.findall(r"[a-z]+", n))
    if palabras & _OTROS_EXAMENES:
        return None
    if not palabras & PALABRAS_MESA:
        if _REGULARIDAD.search(n):
            return {"respuesta": REGLA, "estado": "CONFIRMADA", "fuentes": [], "fecha_informacion": None}
        return None

    fechas = db.query(MesaFecha).order_by(MesaFecha.fecha_examen, MesaFecha.mesa).all()
    if not fechas:
        return None
    mesa = _mesa_pedida(n)
    mes = mes_mencionado(pregunta)
    catalogo = {m for (m,) in db.query(MesaMateria.materia_norm).distinct()}
    materias = materias_que_coinciden(catalogo, pregunta)
    # "Química Orgánica Avanzada" no es "Química": la materia tiene que cubrir lo que nombra la pregunta
    resto = _resto(pregunta)
    if resto:
        materias = [m for m in materias
                    if sum(any(_coincide(q, t) for t in _tokens(m)) for q in resto) / len(resto) >= 0.5]
    pide_tribunal = bool(palabras & (_TRIBUNAL | {"tribunal", "tribunales", "quien", "quienes"}))
    candidatas: list[str] = []
    if not materias and resto:
        # "algoritmos" nombra dos materias: si todas las palabras están en pocas materias, se muestran todas
        candidatas = [m for m in catalogo if all(any(_coincide(q, t) for t in _tokens(m)) for q in resto)]
        if len(candidatas) <= 3:
            materias = sorted(candidatas)
    personas = _personas(db, pregunta) if not materias else []

    if materias:
        return _por_materia(db, materias, fechas, hoy, tribunal_primero=pide_tribunal)
    if personas:
        return _por_persona(db, personas)
    if mesa:
        return _por_mesa(db, mesa, fechas, hoy)
    if mes:
        return _por_mes(mes, fechas, hoy)
    if resto and pide_tribunal:
        return _sin_materia(db, resto, varias=len(candidatas) > 3)
    if resto:
        return None  # nombra algo que no está en las mesas (otra carrera, un parcial…): sigue el RAG
    return _proximas_mesas(fechas, hoy)


def _por_materia(db: Session, materias: list[str], fechas: list[MesaFecha], hoy: date,
                 tribunal_primero: bool = False) -> dict:
    filas = db.query(MesaMateria).filter(MesaMateria.materia_norm.in_(materias)).all()
    por_materia: dict[str, list[MesaMateria]] = defaultdict(list)
    for f in filas:
        por_materia[f.materia_norm].append(f)
    lineas: list[str] = []
    con_tribunal = False
    for norma in sorted(por_materia, key=lambda m: por_materia[m][0].materia)[:3]:
        grupo = sorted(por_materia[norma], key=lambda t: (t.sede != "Casa Central", t.sede))
        mesa = grupo[0].mesa
        lineas.append(f"**{bonito(grupo[0].materia)}** se rinde en la **Mesa {_romano(mesa)}** [1].")
        proximas = _proximas(fechas, mesa, hoy)
        bloque_fechas = (["Próximas fechas:", *[_linea_fecha(f, hoy) for f in proximas]] if proximas
                         else ["No hay más fechas cargadas para esta mesa en el ciclo lectivo."])
        # Cargados desde el panel puede faltar el año del listado: igual se muestran
        tribunales = [t for t in grupo if t.presidente or t.vocal1 or t.vocal2]
        if tribunales:
            con_tribunal = True
            anio = next((t.anio_tribunal for t in tribunales if t.anio_tribunal), None)
            bloque_tribunal = [f"Tribunal que evalúa el final{f' (listado {anio}, puede cambiar)' if anio else ''} [2]:",
                               *[_tribunal(t) for t in tribunales]]
        else:
            bloque_tribunal = ["Todavía no hay tribunal cargado para esta materia."]
        lineas += [*bloque_tribunal, *bloque_fechas] if tribunal_primero else [*bloque_fechas, *bloque_tribunal]
        lineas.append("")
    return _salida(lineas, con_tribunal)


def _sin_materia(db: Session, resto: list[str], varias: bool = False) -> dict:
    """Pregunta de tribunal sin una materia clara: se dice y se sugieren las parecidas."""
    nombres = {m for (m,) in db.query(MesaMateria.materia)}
    parecidas = sorted(bonito(m) for m in nombres if any(_coincide(q, t) for q in resto for t in _tokens(m)))[:8]
    buscado = " ".join(resto)
    if varias:
        lineas = [f"Hay varias materias con «{buscado}» en las mesas de examen. ¿Cuál querés consultar?"]
    else:
        lineas = [f"No encontré «{buscado}» entre las materias de las mesas de examen."]
        if parecidas:
            lineas.append("¿Quisiste decir alguna de estas?")
    lineas += [f"- {m}" for m in parecidas]
    return {"respuesta": "\n".join(lineas), "estado": "CONFIRMADA", "fuentes": [], "fecha_informacion": None}


def _por_persona(db: Session, personas: list[str]) -> dict:
    filas = db.query(MesaMateria).order_by(MesaMateria.mesa, MesaMateria.materia).all()
    lineas = []
    for p in personas[:3]:
        roles = []
        for t in filas:
            rol = "presidente" if t.presidente == p else "vocal" if p in (t.vocal1, t.vocal2) else None
            if rol:
                roles.append(f"- {bonito(t.materia)} — Mesa {_romano(t.mesa)}, {t.sede}"
                             + (f", {t.hora} h" if t.hora else "") + f" ({rol})")
        lineas += [f"Tribunales donde figura **{p}** (listado 2025) [2]:", *roles, ""]
    return _salida(lineas, con_tribunal=True)


def _por_mesa(db: Session, mesa: int, fechas: list[MesaFecha], hoy: date) -> dict:
    nombres = sorted({bonito(m) for (m,) in db.query(MesaMateria.materia).filter(MesaMateria.mesa == mesa)})
    lineas = [f"Materias que se rinden en la **Mesa {_romano(mesa)}** [2]:", *[f"- {m}" for m in nombres], ""]
    proximas = _proximas(fechas, mesa, hoy)
    if proximas:
        lineas += ["Próximas fechas [1]:", *[_linea_fecha(f, hoy) for f in proximas]]
    return _salida(lineas, con_tribunal=True)


def _por_mes(mes: int, fechas: list[MesaFecha], hoy: date) -> dict:
    anio = anio_del_mes(mes, hoy, {(f.fecha_examen.year, f.fecha_examen.month) for f in fechas})
    del_mes = [f for f in fechas if (f.fecha_examen.year, f.fecha_examen.month) == (anio, mes)]
    if not del_mes:
        return _salida([f"No hay mesas de examen final en {MESES[mes - 1]} de {anio} [1]."])
    lineas = [f"Mesas de examen final de **{MESES[mes - 1]} {anio}** [1]:",
              *[_linea_fecha(f, hoy, con_mesa=True) for f in del_mes]]
    return _salida(lineas)


def _proximas_mesas(fechas: list[MesaFecha], hoy: date) -> dict:
    lineas = ["Próximas mesas de examen final [1]:"]
    for mesa in (1, 2, 3):
        lineas += [_linea_fecha(f, hoy, con_mesa=True) for f in _proximas(fechas, mesa, hoy)[:2]]
    lineas.append("")
    lineas.append("_Preguntá por una materia (ej. “¿cuándo rindo Sistemas Operativos?”) para ver su mesa y su tribunal._")
    return _salida(lineas)
