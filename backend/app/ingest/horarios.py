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
    dentro = {}
    for w in palabras:
        if x0 - 1 <= (w["x0"] + w["x1"]) / 2 <= x1 + 1 and top - 1 <= (w["top"] + w["bottom"]) / 2 <= bottom + 1:
            # Algunos PDFs dibujan el mismo texto dos veces en el mismo lugar
            dentro.setdefault((w["text"], round(w["x0"] / 2), round(w["top"] / 2)), w)
    return sorted(dentro.values(), key=lambda w: (round(w["top"] / 3), w["x0"]))  # por renglón


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


@dataclass
class _Segmento:
    filas: list[_Fila]
    columnas: list[tuple[int, float, float]]
    tiene_dias: bool  # False = continuación de la grilla de la página anterior
    top: float = 0.0  # posición de la fila de días (el encabezado de la comisión está arriba)


def _segmentos(pagina, tabla, columnas_previas=None) -> list[_Segmento]:
    """
    Grillas dentro de una tabla: cada fila de días (Lunes…Viernes) abre una nueva.
    Franjas antes de cualquier fila de días = continuación de la grilla de la
    página anterior (cortada por el salto de página), con sus mismas columnas.
    """
    segmentos: list[_Segmento] = []
    actual = _Segmento([], columnas_previas or [], False)
    for fila in tabla.rows:
        celdas = fila.cells
        textos = [normalizar(pagina.crop(c).extract_text() or "") if c else "" for c in celdas]
        if sum(t in DIAS for t in textos) >= 3:
            segmentos.append(actual)
            dias = [(DIAS[t], c[0], c[2]) for t, c in zip(textos, celdas) if c and t in DIAS]
            actual = _Segmento([], dias, True, fila.bbox[1])
            continue
        etiqueta = textos[0] if textos else ""
        if actual.columnas:
            # La hora se lee de la zona a la izquierda de los días: a veces pdfplumber
            # no incluye la primera columna en una fila (ej. la primera de la página)
            etiqueta = pagina.crop((0, fila.bbox[1], actual.columnas[0][1], fila.bbox[3])).extract_text() or ""
        franjas = _RE_FRANJA.findall(etiqueta)
        if actual.columnas and franjas:
            # A veces pdfplumber junta dos filas en una: se reparte la altura entre las franjas
            alto = (fila.bbox[3] - fila.bbox[1]) / len(franjas)
            for k, (ini, fin) in enumerate(franjas):
                top = fila.bbox[1] + k * alto
                actual.filas.append(_Fila(ini.zfill(5), fin.zfill(5), top, top + alto))
    segmentos.append(actual)
    # Una fila de días sin franjas debajo (al pie de la página) también abre grilla:
    # sus franjas siguen en la página siguiente
    return [s for s in segmentos if len(s.columnas) >= 3 and (s.filas or s.tiene_dias)]


def _fuente(w: dict) -> str:
    return w.get("fontname", "")


def _fuentes_de_materia(bloques: list[list[dict]]) -> set[str]:
    """
    Fuentes usadas para nombres de materia en este PDF. La materia es el primer
    tramo del bloque con una misma fuente; el docente viene después en otra
    (negrita/cursiva, o "CIDFont+F2"/"CIDFont+F4" según cómo se exportó el PDF).
    """
    primeras: dict[str, int] = {}
    segundas: dict[str, int] = {}
    for ws in bloques:
        primeras[_fuente(ws[0])] = primeras.get(_fuente(ws[0]), 0) + 1
        otra = next((_fuente(w) for w in ws if _fuente(w) != _fuente(ws[0])), None)
        if otra:
            segundas[otra] = segundas.get(otra, 0) + 1
    return {f for f, n in primeras.items() if n > segundas.get(f, 0)}


def _separar(palabras: list[dict], fuentes_materia: set[str]) -> tuple[str, str]:
    """(materia, resto): la materia es el tramo inicial con la fuente de materias."""
    if _fuente(palabras[0]) not in fuentes_materia:
        # Empieza con la fuente de docentes: continuación de un bloque que una línea dejó partido
        return "", _unir(palabras)
    i = 0
    while i < len(palabras) and _fuente(palabras[i]) == _fuente(palabras[0]):
        i += 1
    return _unir(palabras[:i]), _unir(palabras[i:])


def _armar_bloque(dia: int, inicio: str, fin: str, materia: str, resto: str) -> Bloque:
    lugares = list(dict.fromkeys(  # sin repetidos ("Lab. 155" en la materia y en el docente)
        re.sub(r"\s+", " ", m.group(1)).replace("Lab.", "Lab. ").replace("  ", " ").replace("lab ", "Lab. ")
        for m in _RE_LUGAR.finditer(f"{materia} {resto}")
    ))
    materia = _RE_LUGAR.sub(" ", materia)
    resto = _RE_LUGAR.sub(" ", resto)
    electiva = bool(_RE_ELECTIVA.search(materia))
    materia = _RE_ELECTIVA.sub(" ", materia)
    limpiar = lambda s: re.sub(r"\s+", " ", s).strip(" -–,}")  # noqa: E731
    return Bloque(dia, inicio, fin, limpiar(materia), limpiar(resto), ", ".join(lugares), electiva)


def leer_grillas(contenido: bytes) -> list[Grilla] | None:
    """Grillas del PDF (una por comisión), o None si no tiene horarios."""
    import pdfplumber

    crudas: list[tuple[Grilla, list[tuple[int, str, str, list[dict]]]]] = []
    encabezado_pendiente = ""  # texto de comisión que quedó al pie de la página anterior
    columnas_previas = None    # para grillas cortadas por el salto de página
    with pdfplumber.open(io.BytesIO(contenido)) as pdf:
        for pagina in pdf.pages:
            palabras = pagina.extract_words(use_text_flow=True, extra_attrs=["fontname"])
            bordes = [r for r in pagina.rects if r["height"] <= _TOL and r["width"] > 10]
            rellenos = [r for r in pagina.rects if r["height"] > _TOL and r["width"] > _TOL]
            tope_anterior = 0.0
            hubo_grilla = False
            tablas = sorted(pagina.find_tables(), key=lambda t: t.bbox[1])
            for tabla in tablas:
                for seg in _segmentos(pagina, tabla, columnas_previas):
                    filas, columnas = seg.filas, seg.columnas
                    columnas_previas = columnas
                    hubo_grilla = True

                    if seg.tiene_dias or not crudas:
                        # Encabezado: lo escrito entre la grilla anterior y esta (comisión, aula, turno…)
                        fin_encabezado = seg.top if seg.tiene_dias else filas[0].top - 20
                        encabezado = _unir(_palabras_en(palabras, 0, pagina.width, tope_anterior, fin_encabezado))
                        # El pie de la página anterior completa el encabezado (año, plan,
                        # a veces la comisión), salvo que traiga otra comisión
                        if encabezado_pendiente and ("comisi" not in encabezado_pendiente.lower()
                                                     or "comisi" not in encabezado.lower()):
                            encabezado = f"{encabezado_pendiente} {encabezado}"
                        g = Grilla(encabezado=encabezado)
                        _datos_encabezado(g)
                        crudas.append((g, []))
                    encabezado_pendiente = ""
                    bloques = crudas[-1][1]  # si es continuación, se suma a la grilla anterior

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
                    # Desde la última franja (no el borde de la tabla: el encabezado de la
                    # comisión siguiente suele estar dibujado dentro de la misma tabla)
                    tope_anterior = filas[-1].bottom if filas else seg.top + 1

            if hubo_grilla:
                # Lo que quedó debajo de la última grilla suele ser el encabezado de la siguiente
                encabezado_pendiente = _unir(_palabras_en(palabras, 0, pagina.width, tope_anterior, pagina.height))

    if not crudas:
        return None

    # Catálogo de materias del PDF (bloques donde las fuentes separan bien materia y docente)
    fuentes_materia = _fuentes_de_materia([ws for _, bs in crudas for *_, ws in bs])
    separados = [_separar(ws, fuentes_materia) for _, bs in crudas for *_, ws in bs]
    catalogo = sorted({m for m, resto in separados if m and resto}, key=len, reverse=True)

    # Plan y período son los mismos en todo el PDF: completar los que no se leyeron
    for campo in ("plan", "periodo"):
        valores = [getattr(g, campo) for g, _ in crudas if getattr(g, campo)]
        if valores:
            for g, _ in crudas:
                if not getattr(g, campo):
                    setattr(g, campo, max(set(valores), key=valores.count))

    grillas = []
    for g, bloques in crudas:
        for dia, inicio, fin, ws in bloques:
            materia, resto = _separar(ws, fuentes_materia)
            if not materia:
                # Continuación de un bloque del mismo día que una línea o un salto de
                # página dejó partido (docente/aula abajo, materia arriba)
                k = next((k for k in range(len(g.bloques) - 1, -1, -1)
                          if g.bloques[k].dia == dia and g.bloques[k].fin == inicio), None)
                if k is not None:
                    previo = g.bloques[k]
                    unido = _armar_bloque(dia, previo.inicio, fin, previo.materia,
                                          " ".join(x for x in (previo.docente, previo.lugar, resto) if x))
                    unido.electiva = previo.electiva
                    g.bloques[k] = unido
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
