"""
Servicio de chat con IA.
Construye el contexto desde la DB según el rol del usuario
y consulta a Groq para generar la respuesta.
"""
import re
import unicodedata
import uuid
from datetime import date
from typing import Optional

from groq import Groq
from sqlalchemy import or_
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.models.academico import Comision, Materia, PeriodoAcademico, UsuarioComision
from app.models.cursada import Cursada, CursadaExcepcion, CursadaProfesor
from app.models.eventos import EventoCalendario
from app.models.usuario import RolEnum, Usuario

settings = get_settings()

# Historial en memoria por conversación
_historial: dict[str, list[dict]] = {}

# Palabras vacías que no aportan a la búsqueda
_STOPWORDS = {
    "que", "cual", "cuales", "como", "donde", "cuando", "quien", "quienes",
    "tiene", "tiene", "tengo", "tenes", "tiene", "tienen", "hay", "esta",
    "estan", "para", "por", "con", "del", "las", "los", "una", "uno", "unos",
    "unas", "este", "esta", "esto", "ese", "esa", "eso", "dame", "dime",
    "decime", "mostrame", "buscame", "sobre", "info", "informacion",
    "horario", "horarios", "materia", "materias", "comision", "comisiones",
    "profesor", "profesora", "profesores", "aula", "aulas", "clase", "clases",
}


# ─────────────────────────────────────────────────────────────────────────────
# Helpers
# ─────────────────────────────────────────────────────────────────────────────

def _norm(texto: str) -> str:
    """Quita tildes y pasa a minúsculas."""
    return "".join(
        c for c in unicodedata.normalize("NFD", texto.lower())
        if unicodedata.category(c) != "Mn"
    )


def _palabras_clave(pregunta: str) -> list[str]:
    """Extrae palabras útiles de la pregunta (sin stopwords, mínimo 3 chars)."""
    palabras = re.findall(r"[a-záéíóúüñ]+", _norm(pregunta))
    return [p for p in palabras if len(p) >= 3 and p not in _STOPWORDS]


def _nombres_profesores(cursada: Cursada, db: Session) -> str:
    asigs = db.query(CursadaProfesor).filter(CursadaProfesor.cursada_id == cursada.id).all()
    if not asigs:
        return "sin asignar"
    nombres = []
    for a in asigs:
        prof = db.query(Usuario).filter(Usuario.id == a.profesor_id).first()
        if prof:
            nombres.append(prof.nombre)
    return ", ".join(nombres) if nombres else "sin asignar"


def _formato_cursada(c: Cursada, db: Session, mostrar_comision: bool = True) -> str:
    prof = _nombres_profesores(c, db)
    partes = [f"{c.materia.nombre} ({c.materia.codigo})"]
    if mostrar_comision:
        partes.append(f"Comisión: {c.comision.nombre}")
    partes.append(f"Aula: {c.aula or 'sin asignar'}")
    partes.append(f"Horario: {c.horario or 'A confirmar'}")
    partes.append(f"Profesor(es): {prof}")
    return " | ".join(partes)


# ─────────────────────────────────────────────────────────────────────────────
# Búsqueda universal en la DB
# ─────────────────────────────────────────────────────────────────────────────

def _excepciones_vigentes(db: Session) -> str | None:
    """
    Devuelve las excepciones (suspensiones/reubicaciones) desde hoy en adelante.
    Se incluye en TODOS los contextos para que el chat las muestre proactivamente.
    """
    hoy = date.today()
    excepciones = (
        db.query(CursadaExcepcion)
        .filter(CursadaExcepcion.fecha >= hoy)
        .order_by(CursadaExcepcion.fecha.asc())
        .limit(20)
        .all()
    )
    if not excepciones:
        return None

    lineas = ["Suspensiones / reubicaciones próximas o de hoy:"]
    for ex in excepciones:
        cursada = db.get(Cursada, ex.cursada_id)
        if not cursada:
            continue
        es_hoy = ex.fecha == hoy
        linea = (
            f"  - {'⚠️ HOY' if es_hoy else str(ex.fecha)}"
            f" | {cursada.materia.nombre} ({cursada.materia.codigo})"
            f" | Comisión {cursada.comision.nombre}"
            f" | {ex.tipo.value.upper()}"
        )
        if ex.motivo:
            linea += f" — Motivo: {ex.motivo}"
        if ex.aula_nueva:
            linea += f" — Nueva aula: {ex.aula_nueva}"
        if ex.horario_nuevo:
            linea += f" — Nuevo horario: {ex.horario_nuevo}"
        lineas.append(linea)
    return "\n".join(lineas)
    """
    Busca eventos de calendario cuyo título, tipo o motivo coincida
    con palabras clave de la pregunta. Retorna contexto formateado o None.
    """
    kw = _palabras_clave(pregunta)
    hoy = date.today()

    # Palabras que disparan búsqueda de eventos
    PALABRAS_EVENTO = {
        "paro", "asueto", "feriado", "examen", "examenes", "final", "finales",
        "parcial", "parciales", "evento", "cultural", "suspension", "suspendido",
        "cancelado", "clases", "actividad", "calendario", "fecha", "hoy",
    }
    if not any(k in PALABRAS_EVENTO for k in kw):
        return None

    # Buscar eventos vigentes o futuros que coincidan con las palabras
    eventos = db.query(EventoCalendario).all()
    encontrados = []
    for ev in eventos:
        texto = _norm(f"{ev.titulo} {ev.tipo} {ev.motivo or ''} {ev.origen or ''}")
        if any(k in texto for k in kw):
            encontrados.append(ev)

    # También incluir eventos vigentes HOY aunque no coincidan por texto
    vigentes_hoy = db.query(EventoCalendario).filter(
        EventoCalendario.fecha_inicio <= hoy,
        EventoCalendario.fecha_fin >= hoy,
    ).all()
    for ev in vigentes_hoy:
        if ev not in encontrados:
            encontrados.append(ev)

    if not encontrados:
        return None

    lineas = ["Eventos de calendario relevantes:"]
    for ev in encontrados[:10]:
        vigente = ev.fecha_inicio <= hoy <= ev.fecha_fin
        estado = "VIGENTE HOY" if vigente else (
            f"desde {ev.fecha_inicio}" if ev.fecha_inicio > hoy else f"hasta {ev.fecha_fin}"
        )
        linea = (
            f"  - {ev.titulo} [{ev.tipo.value}]"
            f" | {ev.fecha_inicio}"
            + (f" → {ev.fecha_fin}" if ev.fecha_fin != ev.fecha_inicio else "")
            + (f" | {ev.hora_inicio}" if ev.hora_inicio else "")
            + f" | {estado}"
            + (f" | {ev.motivo}" if ev.motivo else "")
            + f" | Cargado por: {ev.origen or 'sistema'}"
        )
        lineas.append(linea)
    return "\n".join(lineas)


def _buscar_eventos(pregunta: str, db: Session) -> str | None:
    """
    Busca eventos de calendario cuyo título, tipo o motivo coincida
    con palabras clave de la pregunta. Retorna contexto formateado o None.
    """
    kw = _palabras_clave(pregunta)
    hoy = date.today()

    PALABRAS_EVENTO = {
        "paro", "asueto", "feriado", "examen", "examenes", "final", "finales",
        "parcial", "parciales", "evento", "cultural", "suspension", "suspendido",
        "cancelado", "clases", "actividad", "calendario", "fecha", "hoy",
    }
    if not any(k in PALABRAS_EVENTO for k in kw):
        return None

    eventos = db.query(EventoCalendario).all()
    encontrados = []
    for ev in eventos:
        texto = _norm(f"{ev.titulo} {ev.tipo} {ev.motivo or ''} {ev.origen or ''}")
        if any(k in texto for k in kw):
            encontrados.append(ev)

    # También incluir eventos vigentes HOY aunque no coincidan por texto
    vigentes_hoy = db.query(EventoCalendario).filter(
        EventoCalendario.fecha_inicio <= hoy,
        EventoCalendario.fecha_fin >= hoy,
    ).all()
    for ev in vigentes_hoy:
        if ev not in encontrados:
            encontrados.append(ev)

    if not encontrados:
        return None

    lineas = ["Eventos de calendario relevantes:"]
    for ev in encontrados[:10]:
        vigente = ev.fecha_inicio <= hoy <= ev.fecha_fin
        estado = "VIGENTE HOY" if vigente else (
            f"desde {ev.fecha_inicio}" if ev.fecha_inicio > hoy else f"hasta {ev.fecha_fin}"
        )
        linea = (
            f"  - {ev.titulo} [{ev.tipo.value}]"
            f" | {ev.fecha_inicio}"
            + (f" → {ev.fecha_fin}" if ev.fecha_fin != ev.fecha_inicio else "")
            + (f" | {ev.hora_inicio}" if ev.hora_inicio else "")
            + f" | {estado}"
            + (f" | {ev.motivo}" if ev.motivo else "")
            + f" | Cargado por: {ev.origen or 'sistema'}"
        )
        lineas.append(linea)
    return "\n".join(lineas)


def _buscar_en_db(pregunta: str, db: Session) -> str:
    """
    Busca en paralelo en comisiones, materias, profesores y alumnos.
    Combina todos los resultados relevantes en un contexto compacto.
    Límite total: ~4000 tokens aprox.
    """
    kw = _palabras_clave(pregunta)
    pregunta_upper = pregunta.upper()
    secciones = []

    # ── 1. Comisión exacta tipo 1K01 ──────────────────────────────────────────
    match_com = re.search(r"\b([1-4]K\d{2})\b", pregunta_upper)
    if match_com:
        nombre_com = match_com.group(1)
        comision = db.query(Comision).filter(Comision.nombre == nombre_com).first()
        if comision:
            lineas = [f"Comisión {comision.nombre}:"]
            cursadas = db.query(Cursada).filter(Cursada.comision_id == comision.id).all()
            for c in cursadas:
                lineas.append("  - " + _formato_cursada(c, db, mostrar_comision=False))
            secciones.append("\n".join(lineas))

    # ── 2. Materias ───────────────────────────────────────────────────────────
    if kw:
        materias = db.query(Materia).all()
        encontradas = []
        for m in materias:
            nombre_n = _norm(m.nombre)
            codigo_n = _norm(m.codigo)
            if any(k in nombre_n or k in codigo_n for k in kw):
                encontradas.append(m)

        for mat in encontradas[:3]:
            lineas = [f"Materia: {mat.nombre} ({mat.codigo})"]
            cursadas = db.query(Cursada).filter(Cursada.materia_id == mat.id).all()
            for c in cursadas[:12]:
                lineas.append("  - " + _formato_cursada(c, db))
            secciones.append("\n".join(lineas))

    # ── 3. Profesores ─────────────────────────────────────────────────────────
    if kw:
        profs = db.query(Usuario).filter(Usuario.rol == RolEnum.profesor_directivo).all()
        encontrados = []
        for p in profs:
            nombre_n = _norm(p.nombre)
            if any(k in nombre_n for k in kw):
                encontrados.append(p)

        for prof in encontrados[:3]:
            lineas = [f"Profesor: {prof.nombre}"]
            asigs = db.query(CursadaProfesor).filter(CursadaProfesor.profesor_id == prof.id).all()
            if asigs:
                for a in asigs:
                    c = a.cursada
                    lineas.append(
                        f"  - {c.materia.nombre} ({c.materia.codigo})"
                        f" | Comisión: {c.comision.nombre}"
                        f" | Aula: {c.aula or 'sin asignar'}"
                        f" | Horario: {c.horario or 'A confirmar'}"
                    )
            else:
                lineas.append("  Sin cursadas asignadas.")
            secciones.append("\n".join(lineas))

    # ── 4. Alumnos ────────────────────────────────────────────────────────────
    if kw:
        alumnos = db.query(Usuario).filter(Usuario.rol == RolEnum.alumno).all()
        encontrados = []
        for a in alumnos:
            nombre_n = _norm(a.nombre)
            if any(k in nombre_n for k in kw):
                encontrados.append(a)

        for alumno in encontrados[:3]:
            lineas = [f"Alumno: {alumno.nombre} ({alumno.email})"]
            inscripciones = db.query(UsuarioComision).filter(
                UsuarioComision.usuario_id == alumno.id
            ).all()
            for insc in inscripciones:
                lineas.append(f"  - Comisión: {insc.comision.nombre}")
            secciones.append("\n".join(lineas))

    # ── 5. Nada encontrado: resumen numérico ──────────────────────────────────
    if not secciones:
        total_alumnos = db.query(Usuario).filter(Usuario.rol == RolEnum.alumno).count()
        total_prof = db.query(Usuario).filter(Usuario.rol == RolEnum.profesor_directivo).count()
        total_materias = db.query(Materia).count()
        total_cursadas = db.query(Cursada).count()
        periodos = db.query(PeriodoAcademico).all()
        lineas = [
            "Resumen del sistema:",
            f"  Alumnos: {total_alumnos}",
            f"  Profesores: {total_prof}",
            f"  Materias: {total_materias}",
            f"  Cursadas: {total_cursadas}",
            "  Períodos:",
        ]
        for p in periodos:
            lineas.append(f"    - {p.nombre} ({p.fecha_inicio} → {p.fecha_fin})")
        lineas.append("Para ver detalles mencioná comisión (ej: 1K01), materia, profesor o alumno.")
        secciones.append("\n".join(lineas))

    # ── 6. Eventos de calendario (siempre se busca, para cualquier pregunta) ──
    ctx_eventos = _buscar_eventos(pregunta, db)
    if ctx_eventos:
        secciones.append(ctx_eventos)

    return "\n\n".join(secciones)

# ─────────────────────────────────────────────────────────────────────────────
# Contextos por rol
# ─────────────────────────────────────────────────────────────────────────────

def _contexto_alumno(usuario: Usuario, db: Session) -> str:
    inscripciones = (
        db.query(UsuarioComision)
        .filter(UsuarioComision.usuario_id == usuario.id)
        .all()
    )
    if not inscripciones:
        return "No estás inscripto en ninguna comisión."

    lineas = [f"Alumno: {usuario.nombre}"]
    for insc in inscripciones:
        comision = insc.comision
        lineas.append(f"\nComisión: {comision.nombre}")
        cursadas = db.query(Cursada).filter(Cursada.comision_id == comision.id).all()
        for c in cursadas:
            lineas.append("  - " + _formato_cursada(c, db, mostrar_comision=False))
    return "\n".join(lineas)


def _contexto_profesor(usuario: Usuario, db: Session) -> str:
    asignaciones = (
        db.query(CursadaProfesor)
        .filter(CursadaProfesor.profesor_id == usuario.id)
        .all()
    )
    if not asignaciones:
        return f"El profesor {usuario.nombre} no tiene cursadas asignadas."

    lineas = [f"Profesor: {usuario.nombre}"]
    for asig in asignaciones:
        c = asig.cursada
        lineas.append(
            f"  - {c.materia.nombre} ({c.materia.codigo})"
            f" | Comisión: {c.comision.nombre}"
            f" | Aula: {c.aula or 'sin asignar'}"
            f" | Horario: {c.horario or 'A confirmar'}"
        )
    return "\n".join(lineas)


# ─────────────────────────────────────────────────────────────────────────────
# Función principal
# ─────────────────────────────────────────────────────────────────────────────

def responder_consulta(
    pregunta: str,
    usuario: Usuario,
    db: Session,
    conversacion_id: Optional[str] = None,
) -> dict:
    conv_id = conversacion_id or str(uuid.uuid4())

    # Contexto según rol
    if usuario.rol == RolEnum.alumno:
        contexto = _contexto_alumno(usuario, db)
        ctx_ev = _buscar_eventos(pregunta, db)
        if ctx_ev:
            contexto += "\n\n" + ctx_ev
    elif usuario.es_profesor:
        contexto = _contexto_profesor(usuario, db)
        ctx_ev = _buscar_eventos(pregunta, db)
        if ctx_ev:
            contexto += "\n\n" + ctx_ev
    else:
        # Admin/administrativo/jefe: búsqueda universal (ya incluye eventos dentro)
        contexto = _buscar_en_db(pregunta, db)

    # Excepciones vigentes (hoy en adelante) — siempre presentes en todos los roles
    ctx_exc = _excepciones_vigentes(db)
    if ctx_exc:
        contexto += "\n\n" + ctx_exc

    system_prompt = f"""Sos un asistente universitario de la Facultad Regional Tucumán - UTN.
Respondé SIEMPRE en español, de forma clara y concisa.
Usá lenguaje informal pero respetuoso (tuteo).
NO uses tablas Markdown. Usá listas simples con guiones si tenés que enumerar.
Si no tenés la información en el contexto, decí "No tengo ese dato en el sistema" sin inventar nada.

DATOS DEL SISTEMA:
{contexto}

Usuario: {usuario.nombre} (rol: {usuario.rol.value})"""

    historial = _historial.get(conv_id, [])
    historial.append({"role": "user", "content": pregunta})

    # Máximo 10 turnos de historial
    if len(historial) > 20:
        historial = historial[-20:]

    client = Groq(api_key=settings.GROQ_API_KEY)
    response = client.chat.completions.create(
        model=settings.GROQ_MODEL,
        messages=[{"role": "system", "content": system_prompt}] + historial,
        temperature=0.3,
        max_tokens=1024,
    )

    respuesta = response.choices[0].message.content.strip()
    historial.append({"role": "assistant", "content": respuesta})
    _historial[conv_id] = historial

    return {
        "respuesta": respuesta,
        "conversacion_id": conv_id,
        "fuentes": [],
    }
