"""
Clasificación por reglas y extracción de fechas (PRO-02). Sin LLM.

El LLM solo se usa cuando ninguna regla coincide (ambigüedad real) y
hasta un tope por corrida (CLASIFICACION_LLM_MAX_POR_CORRIDA, 0 = nunca).
"""
import re
import unicodedata
from datetime import date

from app.models.informacion import TipoInformacionEnum as T

# Palabras clave sin tildes y en minúsculas. Si hay empate gana la que
# aparece primero en este orden (de lo más específico a lo más general).
REGLAS: dict[T, list[str]] = {
    T.BECA: ["beca", "becas", "stipendium", "ayuda economica"],
    T.EXAMEN: ["examen", "examenes", "mesa de examen", "mesas de examen", "final", "finales",
               "parcial", "parciales", "recuperatorio", "recuperatorios", "recuperacion"],
    T.INSCRIPCION: ["inscripcion", "inscripciones", "inscribite", "inscribirse",
                    "preinscripcion", "reinscripcion"],
    T.CALENDARIO: ["calendario academico", "cronograma", "horario", "horarios", "receso",
                   "feriado", "asueto", "inicio de clases", "cuatrimestre"],
    T.CONVOCATORIA: ["pasantia", "pasantias", "convocatoria", "convocatorias", "oferta laboral",
                     "busqueda laboral", "empleo", "concurso", "postulacion", "postulate", "vacante"],
    T.TRAMITE: ["tramite", "tramites", "certificado", "constancia", "equivalencia",
                "equivalencias", "legajo", "analitico"],
    T.EVENTO: ["charla", "congreso", "jornada", "jornadas", "seminario", "taller", "curso",
               "conferencia", "encuentro", "hackathon", "torneo", "competencia", "webinar",
               "capacitacion", "visita", "conaiisi", "feria"],
    T.AVISO: ["atencion estudiantes", "informacion importante", "aviso", "comunicado",
              "se informa", "suspension", "suspende", "se suspenden"],
    T.NOTICIA: ["entrevista", "historias que inspiran", "egresado", "egresada", "premio",
                "reconocimiento", "acreditacion", "felicitamos"],
}
PESO_TITULO = 3
LARGO_CUERPO = 1500  # solo el comienzo del cuerpo: el final suele ser firma/contacto

MESES = {
    "enero": 1, "febrero": 2, "marzo": 3, "abril": 4, "mayo": 5, "junio": 6, "julio": 7,
    "agosto": 8, "septiembre": 9, "setiembre": 9, "octubre": 10, "noviembre": 11, "diciembre": 12,
}
_MES = "|".join(MESES)
# Sin "." como separador: "18.30" (hora) o "2.0" generarían fechas falsas
_RE_NUMERICA = re.compile(r"\b(\d{1,2})[/\-](\d{1,2})(?:[/\-](\d{2,4}))?\b")
_RE_TEXTO = re.compile(rf"\b(\d{{1,2}})\s+(?:al\s+(\d{{1,2}})\s+)?de\s+({_MES})(?:\s+(?:de\s+|del\s+)?(\d{{4}}))?\b")
_RE_ANIO = re.compile(r"\b(20\d{2})\b")


def normalizar(texto: str) -> str:
    sin_tildes = "".join(
        c for c in unicodedata.normalize("NFD", texto.lower()) if unicodedata.category(c) != "Mn"
    )
    return re.sub(r"\s+", " ", sin_tildes)


def _contar(texto: str, palabra: str) -> int:
    return len(re.findall(rf"\b{re.escape(palabra)}\b", texto))


def clasificar(titulo: str, texto: str) -> tuple[T, bool]:
    """Devuelve (tipo, ambiguo). Ambiguo = ninguna regla coincidió."""
    t, cuerpo = normalizar(titulo), normalizar(texto[:LARGO_CUERPO])
    puntajes = {
        tipo: sum(PESO_TITULO * _contar(t, p) + _contar(cuerpo, p) for p in palabras)
        for tipo, palabras in REGLAS.items()
    }
    mejor = max(puntajes.values())
    if mejor == 0:
        return T.OTRO, True
    # max() conserva el primero en caso de empate → respeta el orden de REGLAS
    return max(puntajes, key=lambda tipo: puntajes[tipo]), False


def _fecha_valida(anio: int, mes: int, dia: int) -> date | None:
    try:
        return date(anio, mes, dia)
    except ValueError:
        return None


def _anio(valor: str | None, referencia: date) -> int:
    if not valor:
        return referencia.year
    anio = int(valor)
    return anio + 2000 if anio < 100 else anio


def extraer_fechas(texto: str, referencia: date) -> tuple[date | None, date | None]:
    """
    Fechas mencionadas en el texto (12/10/2026, 15 de octubre, del 10 al 15 de octubre).
    Sin año se asume el de `referencia` (fecha de publicación). Se descartan fechas
    implausibles (más de 60 días antes o 400 después de la publicación).
    Devuelve (la más temprana, la más tardía).
    """
    t = normalizar(texto)
    fechas: list[date] = []

    for dia, mes, anio in _RE_NUMERICA.findall(t):
        if 1 <= int(mes) <= 12:
            fechas.append(_fecha_valida(_anio(anio, referencia), int(mes), int(dia)))
    for dia, dia_fin, mes, anio in _RE_TEXTO.findall(t):
        a, m = _anio(anio, referencia), MESES[mes]
        fechas.append(_fecha_valida(a, m, int(dia)))
        if dia_fin:
            fechas.append(_fecha_valida(a, m, int(dia_fin)))

    validas = sorted(
        f for f in fechas
        if f and -60 <= (f - referencia).days <= 400
    )
    return (validas[0], validas[-1]) if validas else (None, None)


_RE_PLAN = re.compile(r"\bplan(?:\s+de\s+estudios?)?\s+20\d{2}\b")


def anio_mencionado(texto: str) -> int | None:
    """
    Año más reciente nombrado ("Calendario Académico 2025" → 2025).
    Ignora "Plan 2023": es el plan de estudios, no el período al que se refiere.
    """
    anios = [int(a) for a in _RE_ANIO.findall(_RE_PLAN.sub(" ", normalizar(texto)))]
    return max(anios) if anios else None


TIPOS_VALIDOS = [t.value for t in T]
