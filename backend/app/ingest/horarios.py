"""
Lectura de grillas de horarios (Excel exportado a PDF). Sin LLM, costo 0.

Problema: en el Excel cada materia es una celda COMBINADA que ocupa varias
franjas horarias. Al pasar el PDF a texto, el bloque queda partido en renglones
sueltos repartidos en filas de distintas horas, y se pierde de qué hora a qué
hora va cada materia.

Solución: reconstruir la grilla con la geometría del PDF.
  - Filas: franjas "HH:MM - HH:MM" de la primera columna.
  - Columnas: encabezado Lunes … Viernes (o Sábado).
  - Límite entre bloques: Excel dibuja el borde de la celda (un rectángulo fino)
    SOLO donde termina la celda combinada; también se corta si cambia el color.
  - Texto del bloque: las palabras que caen dentro de su recuadro.

Resultado: una línea por bloque ("Lunes 14:00 a 16:15: Materia — Docente"),
que la IA lee sin ambigüedad.
"""
import io
import logging
import re
from dataclasses import dataclass

logging.getLogger("pdfminer").setLevel(logging.ERROR)

DIAS = ["lunes", "martes", "miércoles", "miercoles", "jueves", "viernes", "sábado", "sabado"]
_RE_FRANJA = re.compile(r"(\d{1,2}:\d{2})\s*-\s*(\d{1,2}:\d{2})")
_TOL = 3.5  # tolerancia en puntos para comparar coordenadas


@dataclass
class _Fila:
    inicio: str
    fin: str
    top: float
    bottom: float


def _solapa(a0: float, a1: float, b0: float, b1: float) -> float:
    return max(0.0, min(a1, b1) - max(a0, b0))


def _palabras_en(palabras: list[dict], x0: float, x1: float, top: float, bottom: float) -> str:
    dentro = [
        w for w in palabras
        if x0 - 1 <= (w["x0"] + w["x1"]) / 2 <= x1 + 1 and top - 1 <= (w["top"] + w["bottom"]) / 2 <= bottom + 1
    ]
    dentro.sort(key=lambda w: (round(w["top"] / 3), w["x0"]))  # por renglón, de izquierda a derecha
    return " ".join(w["text"] for w in dentro).strip()


def _color(rects: list[dict], x0: float, x1: float, top: float, bottom: float):
    """Color de relleno de la celda (para cortar bloques si cambia)."""
    for r in rects:
        if r["height"] > _TOL and r["width"] > _TOL and r["x0"] <= x0 + _TOL and r["x1"] >= x1 - _TOL \
                and r["top"] <= top + _TOL and r["bottom"] >= bottom - _TOL:
            return r.get("non_stroking_color")
    return None


def _hay_borde(bordes: list[dict], y: float, x0: float, x1: float) -> bool:
    ancho = x1 - x0
    return any(abs((b["top"] + b["bottom"]) / 2 - y) <= _TOL and _solapa(b["x0"], b["x1"], x0, x1) >= ancho * 0.5
               for b in bordes)


def _grilla(pagina, tabla) -> tuple[list[_Fila], list[tuple[str, float, float]]] | None:
    """Filas (franjas horarias) y columnas (días) de una tabla, o None si no es un horario."""
    filas: list[_Fila] = []
    columnas: list[tuple[str, float, float]] = []
    for fila in tabla.rows:
        celdas = fila.cells
        textos = [
            (pagina.crop(c).extract_text() or "").strip() if c else "" for c in celdas
        ]
        if not columnas and sum(t.lower() in DIAS for t in textos) >= 3:
            columnas = [(t, c[0], c[2]) for t, c in zip(textos, celdas) if c and t.lower() in DIAS]
            continue
        m = _RE_FRANJA.search(textos[0]) if textos else None
        if columnas and m and celdas[0]:
            filas.append(_Fila(m.group(1), m.group(2), fila.bbox[1], fila.bbox[3]))
    return (filas, columnas) if filas and len(columnas) >= 3 else None


def leer_horarios(contenido: bytes) -> list[str] | None:
    """
    Una entrada por grilla (comisión): encabezado + una línea por bloque de clase.
    Devuelve None si el PDF no tiene grillas de horario (se usa la extracción común).
    """
    import pdfplumber

    salida: list[str] = []
    encabezado_pendiente = ""  # texto de comisión que quedó al pie de la página anterior
    with pdfplumber.open(io.BytesIO(contenido)) as pdf:
        for pagina in pdf.pages:
            palabras = pagina.extract_words(use_text_flow=True)
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
                encabezado = _palabras_en(palabras, 0, pagina.width, tope_anterior, filas[0].top - 20)
                if "comisi" not in encabezado.lower() and encabezado_pendiente:
                    encabezado = f"{encabezado_pendiente} {encabezado}"
                encabezado_pendiente = ""

                lineas = [encabezado]
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
                        texto = _palabras_en(palabras, x0, x1, filas[i].top, filas[j].bottom)
                        if texto:
                            lineas.append(f"{dia} {filas[i].inicio} a {filas[j].fin}: {texto}")
                        i = j + 1
                salida.append("\n".join(lineas))
                tope_anterior = tabla.bbox[3]

            if tablas:
                # Lo que quedó debajo de la última grilla suele ser el encabezado de la siguiente
                encabezado_pendiente = _palabras_en(palabras, 0, pagina.width, tope_anterior, pagina.height)
    return salida or None
