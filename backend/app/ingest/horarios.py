"""
Lectura de grillas de horarios (Excel exportado a PDF). Sin LLM, costo 0.

Estructura de los horarios de Sistemas: cada año tiene comisiones (1K01, 1K02…;
2K01…). Cada comisión cursa las materias de su año en sus propios días y horas;
algunas son anuales y otras cuatrimestrales. Las electivas tienen horarios aparte.

Problema: en el Excel cada materia es una celda COMBINADA que ocupa varias
franjas horarias. Al pasar el PDF a texto el bloque queda partido en renglones
de distintas horas y se pierde de qué hora a qué hora va cada materia.

Solución: reconstruir la grilla con la geometría del PDF.
  - Filas: franjas "HH:MM - HH:MM" de la primera columna.
  - Columnas: encabezado Lunes … Viernes (o Sábado).
  - Límite entre bloques: Excel dibuja el borde de la celda (un rectángulo fino)
    SOLO donde termina la celda combinada; también se corta si cambia el color.
  - Materia vs docente: la materia va en negrita y el docente en cursiva. Si un
    docente también está en negrita, se separa con el catálogo de materias que
    se arma con el resto de los bloques del mismo PDF.
"""
import io
import logging
import re
import unicodedata
from dataclasses import dataclass, field

logging.getLogger("pdfminer").setLevel(logging.ERROR)

DIAS = {"lunes": 1, "martes": 2, "miercoles": 3, "jueves": 4, "viernes": 5, "sabado": 6}
NOMBRE_DIA = {1: "Lunes", 2: "Martes", 3: "Miércoles", 4: "Jueves", 5: "Viernes", 6: "Sábado"}
_RE_FRANJA = re.compile(r"(\d{1,2}:\d{2})\s*-\s*(\d{1,2}:\d{2})")
_RE_COMISION = re.compile(r"\b([1-6])\s*[kK]\s*0?(\d{1,2})\b")
_RE_LUGAR = re.compile(r"\(?\s*((?:lab(?:oratorio)?\.?\s*\d+)|(?:aula\s*\d+))\s*\)?", re.IGNORECASE)
_RE_ELECTIVA = re.compile(r"\(\s*elec[a-z.]*\s*\)", re.IGNORECASE)
_TOL = 3.5  # tolerancia en puntos para comparar coordenadas


def normalizar(texto: str) -> str:
    sin_tildes = "".join(c for c in unicodedata.normalize("NFD", texto.lower()) if unicodedata.category(c) != "Mn")
    return re.sub(r"\s+", " ", sin_tildes).strip()


def normalizar_materia(texto: str) -> str:
    """'Algorit. y Est. De Datos' → 'algorit y est de datos' (para buscar por palabras)."""
    return re.sub(r"\s+", " ", re.sub(r"[^a-z0-9 ]", " ", normalizar(texto))).strip()


def normalizar_comision(texto: str) -> str | None:
    """'1k1', '1K01', '1 k 01' → '1K01'."""
    m = _RE_COMISION.search(texto)
    return f"{m.group(1)}K{int(m.group(2)):02d}" if m else None


@dataclass
class Bloque:
    dia: int
    inicio: str
    fin: str
    materia: str
    docente: str = ""
    lugar: str = ""
    electiva: bool = False

    def texto(self) -> str:
        partes = [f"{NOMBRE_DIA[self.dia]} {self.inicio} a {self.fin}: {self.materia}"]
        if self.electiva:
            partes.append("(electiva)")
        if self.docente:
            partes.append(f"— Docente: {self.docente}")
        if self.lugar:
            partes.append(f"— {self.lugar}")
        return " ".join(partes)


@dataclass
class Grilla:
    encabezado: str
    comision: str | None = None
    anio: int | None = None
    plan: str | None = None
    turno: str | None = None
    periodo: str | None = None
    aula: str | None = None
    bloques: list[Bloque] = field(default_factory=list)

    def texto(self) -> str:
        datos = [f"Comisión {self.comision}" if self.comision else None,
                 f"{self.anio}º año" if self.anio else None,
                 f"Plan {self.plan}" if self.plan else None,
                 self.periodo, f"Turno {self.turno}" if self.turno else None,
                 f"Aula {self.aula}" if self.aula else None]
        cabecera = " · ".join(d for d in datos if d) or self.encabezado
        return "\n".join([f"Horario — {cabecera}", f"({self.encabezado})", *(b.texto() for b in self.bloques)])


def _datos_encabezado(g: Grilla) -> None:
    t = g.encabezado
    n = normalizar(t)
    g.comision = normalizar_comision(re.sub(r"plan\s*20\d\d", "", t, flags=re.IGNORECASE))
    g.anio = int(g.comision[0]) if g.comision else None
    if m := re.search(r"plan\s*(20\d\d)", n):
        g.plan = m.group(1)
    turnos = [x for x in ("mañana", "tarde", "noche") if x in t.lower()]
    g.turno = " / ".join(turnos).capitalize() if turnos else None
    if "segundo cuatrimestre" in n or "2do cuatrimestre" in n:
        g.periodo = "Segundo cuatrimestre"
    elif "primer cuatrimestre" in n or "1er cuatrimestre" in n:
        g.periodo = "Primer cuatrimestre"
    elif "anual" in n:
        g.periodo = "Anual"
    m = re.search(r"aula\s*:?\s*((?:sub\s*\d+\s*/\s*sub\s*\d+)|(?:lab\s*\d+)|(?:s\d\b)|(?:\d{3}(?:\s*/\s*\d{3})?))", n)
    if not m:  # a veces el número quedó antes de "Aula:" al leer el encabezado
        m = re.search(r"\b(\d{3}(?:\s*/\s*\d{3})?)\b", re.sub(r"\b20\d\d\b", "", n))
    g.aula = m.group(1).replace(" ", "").title() if m else None


@dataclass
class _Fila:
    inicio: str
    fin: str
    top: float
    bottom: float


def _solapa(a0: float, a1: float, b0: float, b1: float) -> float:
    return max(0.0, min(a1, b1) - max(a0, b0))


def _palabras_en(palabras: list[dict], x0: float, x1: float, top: float, bottom: float) -> list[dict]:
    dentro = [
        w for w in palabras
        if x0 - 1 <= (w["x0"] + w["x1"]) / 2 <= x1 + 1 and top - 1 <= (w["top"] + w["bottom"]) / 2 <= bottom + 1
    ]
    return sorted(dentro, key=lambda w: (round(w["top"] / 3), w["x0"]))  # por renglón


def _unir(palabras: list[dict]) -> str:
    return re.sub(r"\s+", " ", " ".join(w["text"] for w in palabras)).strip()


def _color(rects: list[dict], x0: float, x1: float, top: float, bottom: float):
    """Color de relleno de la celda (para cortar bloques si cambia)."""
    for r in rects:
        if r["x0"] <= x0 + _TOL and r["x1"] >= x1 - _TOL and r["top"] <= top + _TOL and r["bottom"] >= bottom - _TOL:
            return r.get("non_stroking_color")
    return None


def _hay_borde(bordes: list[dict], y: float, x0: float, x1: float) -> bool:
    ancho = x1 - x0
    return any(abs((b["top"] + b["bottom"]) / 2 - y) <= _TOL and _solapa(b["x0"], b["x1"], x0, x1) >= ancho * 0.5
               for b in bordes)


def _grilla(pagina, tabla) -> tuple[list[_Fila], list[tuple[int, float, float]]] | None:
    """Filas (franjas horarias) y columnas (días) de una tabla, o None si no es un horario."""
    filas: list[_Fila] = []
    columnas: list[tuple[int, float, float]] = []
    for fila in tabla.rows:
        celdas = fila.cells
        textos = [normalizar(pagina.crop(c).extract_text() or "") if c else "" for c in celdas]
        if not columnas and sum(t in DIAS for t in textos) >= 3:
            columnas = [(DIAS[t], c[0], c[2]) for t, c in zip(textos, celdas) if c and t in DIAS]
            continue
        franjas = _RE_FRANJA.findall(textos[0]) if textos else []
        if columnas and franjas and celdas[0]:
            # A veces pdfplumber junta dos filas en una: se reparte la altura entre las franjas
            alto = (fila.bbox[3] - fila.bbox[1]) / len(franjas)
            for k, (ini, fin) in enumerate(franjas):
                top = fila.bbox[1] + k * alto
                filas.append(_Fila(ini.zfill(5), fin.zfill(5), top, top + alto))
    return (filas, columnas) if filas and len(columnas) >= 3 else None


def _es_materia(w: dict) -> bool:
    nombre = w.get("fontname", "")
    return "Bold" in nombre and "Italic" not in nombre


def _separar(palabras: list[dict]) -> tuple[str, str]:
    """(materia, resto): la materia es el tramo inicial en negrita (sin cursiva)."""
    i = 0
    while i < len(palabras) and _es_materia(palabras[i]):
        i += 1
    if i == 0:
        # Empieza en cursiva: es el docente de un bloque que una línea dejó partido
        if any("Italic" in w.get("fontname", "") for w in palabras):
            return "", _unir(palabras)
        return _unir(palabras), ""  # PDF sin negritas: todo como materia
    return _unir(palabras[:i]), _unir(palabras[i:])


def _armar_bloque(dia: int, inicio: str, fin: str, materia: str, resto: str) -> Bloque:
    lugares = [m.group(1) for m in _RE_LUGAR.finditer(f"{materia} {resto}")]
    resto = _RE_LUGAR.sub(" ", resto)
    electiva = bool(_RE_ELECTIVA.search(materia))
    materia = _RE_ELECTIVA.sub(" ", materia)
    limpiar = lambda s: re.sub(r"\s+", " ", s).strip(" -–,}")  # noqa: E731
    return Bloque(dia, inicio, fin, limpiar(materia), limpiar(resto),
                  ", ".join(re.sub(r"\s+", " ", l).replace("Lab.", "Lab. ").replace("  ", " ") for l in lugares),
                  electiva)


def leer_grillas(contenido: bytes) -> list[Grilla] | None:
    """Grillas del PDF (una por comisión), o None si no tiene horarios."""
    import pdfplumber

    crudas: list[tuple[Grilla, list[tuple[int, str, str, list[dict]]]]] = []
    encabezado_pendiente = ""  # texto de comisión que quedó al pie de la página anterior
    with pdfplumber.open(io.BytesIO(contenido)) as pdf:
        for pagina in pdf.pages:
            palabras = pagina.extract_words(use_text_flow=True, extra_attrs=["fontname"])
            bordes = [r for r in pagina.rects if r["height"] <= _TOL and r["width"] > 10]
            rellenos = [r for r in pagina.rects if r["height"] > _TOL and r["width"] > _TOL]
            tope_anterior = 0.0
            tablas = sorted(pagina.find_tables(), key=lambda t: t.bbox[1])
            for tabla in tablas:
                grilla = _grilla(pagina, tabla)
                if not grilla:
                    continue
                filas, columnas = grilla

                # Encabezado: lo escrito entre la grilla anterior y esta (comisión, aula, turno…)
                encabezado = _unir(_palabras_en(palabras, 0, pagina.width, tope_anterior, filas[0].top - 20))
                if "comisi" not in encabezado.lower() and encabezado_pendiente:
                    encabezado = f"{encabezado_pendiente} {encabezado}"
                encabezado_pendiente = ""

                bloques = []
                for dia, x0, x1 in columnas:
                    i = 0
                    while i < len(filas):
                        j = i
                        color = _color(rellenos, x0, x1, filas[i].top, filas[i].bottom)
                        # Extender el bloque mientras no haya borde ni cambio de color
                        while j + 1 < len(filas) \
                                and not _hay_borde(bordes, filas[j].bottom, x0, x1) \
                                and _color(rellenos, x0, x1, filas[j + 1].top, filas[j + 1].bottom) == color:
                            j += 1
                        ws = _palabras_en(palabras, x0, x1, filas[i].top, filas[j].bottom)
                        if ws:
                            bloques.append((dia, filas[i].inicio, filas[j].fin, ws))
                        i = j + 1
                g = Grilla(encabezado=encabezado)
                _datos_encabezado(g)
                crudas.append((g, bloques))
                tope_anterior = tabla.bbox[3]

            if tablas:
                # Lo que quedó debajo de la última grilla suele ser el encabezado de la siguiente
                encabezado_pendiente = _unir(_palabras_en(palabras, 0, pagina.width, tope_anterior, pagina.height))

    if not crudas:
        return None

    # Catálogo de materias del PDF (bloques donde negrita y cursiva separan bien)
    separados = [_separar(ws) for _, bs in crudas for *_, ws in bs]
    catalogo = sorted({m for m, resto in separados if m and resto}, key=len, reverse=True)

    grillas = []
    for g, bloques in crudas:
        for dia, inicio, fin, ws in bloques:
            materia, resto = _separar(ws)
            previo = g.bloques[-1] if g.bloques else None
            if not materia:
                # Continuación del bloque anterior del mismo día (docente/aula partidos por una línea)
                if previo and previo.dia == dia and previo.fin == inicio:
                    unido = _armar_bloque(dia, previo.inicio, fin, previo.materia,
                                          " ".join(x for x in (previo.docente, previo.lugar, resto) if x))
                    unido.electiva = previo.electiva
                    g.bloques[-1] = unido
                continue
            if not resto:
                # Todo en negrita (docente también): cortar por una materia conocida
                conocida = next((c for c in catalogo if normalizar(materia).startswith(normalizar(c))
                                 and len(materia) > len(c)), None)
                if conocida:
                    materia, resto = materia[:len(conocida)], materia[len(conocida):]
            g.bloques.append(_armar_bloque(dia, inicio, fin, materia, resto))
        grillas.append(g)
    return grillas


def leer_horarios(contenido: bytes) -> list[str] | None:
    """Texto de cada grilla (para chunks de búsqueda), o None si el PDF no es un horario."""
    grillas = leer_grillas(contenido)
    return [g.texto() for g in grillas] if grillas else None
