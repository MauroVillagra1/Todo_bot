"""Fechas en las respuestas armadas con SQL (mesas, calendario): hoy en Argentina, meses y días."""
import re
from datetime import date, datetime, timedelta, timezone

from app.ingest.horarios import normalizar

ARGENTINA = timezone(timedelta(hours=-3))
DIAS_SEMANA = ["lunes", "martes", "miércoles", "jueves", "viernes", "sábado", "domingo"]
_DIAS_NORM = {"lunes": 0, "martes": 1, "miercoles": 2, "jueves": 3, "viernes": 4, "sabado": 5, "domingo": 6}
MESES = ["enero", "febrero", "marzo", "abril", "mayo", "junio", "julio", "agosto", "septiembre",
         "octubre", "noviembre", "diciembre"]
_MESES_NORM = {**{m: i for i, m in enumerate(MESES, 1)}, "setiembre": 9}


def hoy_argentina() -> date:
    return datetime.now(ARGENTINA).date()


def dia(d: date, con_anio: bool = True) -> str:
    """'lunes 23/11/2026'."""
    return f"{DIAS_SEMANA[d.weekday()]} {d:%d/%m/%Y}" if con_anio else f"{DIAS_SEMANA[d.weekday()]} {d:%d/%m}"


def rango(desde: date, hasta: date | None) -> str:
    if not hasta or hasta == desde:
        return dia(desde)
    return f"del {dia(desde)} al {dia(hasta)}"


def mes_mencionado(texto: str) -> int | None:
    n = normalizar(texto)
    return next((num for nombre, num in _MESES_NORM.items() if re.search(rf"\b{nombre}\b", n)), None)


def anio_del_mes(mes: int, hoy: date, disponibles: set[tuple[int, int]]) -> int:
    """Para "diciembre": el próximo diciembre con datos (o el de este año si ya pasó y no hay otro)."""
    candidatos = sorted(a for a, m in disponibles if m == mes)
    futuros = [a for a in candidatos if (a, mes) >= (hoy.year, hoy.month)]
    return futuros[0] if futuros else (candidatos[-1] if candidatos else hoy.year)


def fecha_mencionada(texto: str, hoy: date) -> date | None:
    """hoy, mañana, pasado mañana, un día de la semana (el próximo) o dd/mm."""
    n = normalizar(texto)
    if re.search(r"\bpasado manana\b", n):
        return hoy + timedelta(days=2)
    if re.search(r"\bmanana\b", n) and not re.search(r"\b(la|de la|por la|a la) manana\b", n):
        return hoy + timedelta(days=1)
    if re.search(r"\bhoy\b", n):
        return hoy
    if m := re.search(r"\b(\d{1,2})[/\-](\d{1,2})(?:[/\-](\d{2,4}))?\b", n):
        anio = int(m.group(3)) if m.group(3) else hoy.year
        anio += 2000 if anio < 100 else 0
        try:
            return date(anio, int(m.group(2)), int(m.group(1)))
        except ValueError:
            return None
    for nombre, num in _DIAS_NORM.items():
        if re.search(rf"\b{nombre}\b", n):
            return hoy + timedelta(days=(num - hoy.weekday()) % 7)
    return None
