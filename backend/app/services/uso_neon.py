"""
Consumo del proyecto de Neon en el período actual, desde su API oficial
(los mismos números de Neon → Usage). El plan gratis corta todo al pasarse
de cualquiera de los cupos, así que se avisa desde NEON_AVISO_PORCENTAJE.

El proyecto se detecta solo a partir del host de DATABASE_URL
("ep-xxx-pooler.….neon.tech" → endpoint "ep-xxx").
"""
import logging
import time
from urllib.parse import urlparse

import httpx

from app.core.config import get_settings

logger = logging.getLogger(__name__)

API = "https://console.neon.tech/api/v2"
_CACHE_SEGUNDOS = 600  # la API de Neon actualiza cada varios minutos
_cache: dict = {"hasta": 0.0, "valor": None}
_GB = 1024 ** 3


def _endpoint() -> str:
    host = urlparse(get_settings().DATABASE_URL).hostname or ""
    return host.split(".")[0].removesuffix("-pooler")


def _proyecto(cliente: httpx.Client) -> dict | None:
    endpoint = _endpoint()
    for p in cliente.get(f"{API}/projects").raise_for_status().json().get("projects", []):
        endpoints = cliente.get(f"{API}/projects/{p['id']}/endpoints").raise_for_status().json()
        if any(e.get("id") == endpoint for e in endpoints.get("endpoints", [])):
            return cliente.get(f"{API}/projects/{p['id']}").raise_for_status().json()["project"]
    return None


def _metrica(nombre: str, usado: float, limite: float, unidad: str, aviso: int) -> dict:
    porcentaje = round(100 * usado / limite, 1) if limite else 0.0
    return {"nombre": nombre, "usado": round(usado, 3), "limite": limite, "unidad": unidad,
            "porcentaje": porcentaje, "alerta": porcentaje >= aviso}


def consumo() -> dict | None:
    """None si no hay NEON_API_KEY o la API no responde (no debe romper el panel)."""
    s = get_settings()
    if not s.NEON_API_KEY.strip():
        return None
    if time.time() < _cache["hasta"]:
        return _cache["valor"]
    try:
        with httpx.Client(headers={"Authorization": f"Bearer {s.NEON_API_KEY.strip()}",
                                   "Accept": "application/json"}, timeout=15) as cliente:
            p = _proyecto(cliente)
    except Exception as e:
        logger.warning("No se pudo consultar el consumo de Neon: %s", str(e)[:200])
        return None
    if not p:
        return None
    aviso = s.NEON_AVISO_PORCENTAJE
    metricas = [
        _metrica("Transferencia", p.get("data_transfer_bytes", 0) / _GB, s.NEON_LIMITE_TRANSFER_GB, "GB", aviso),
        _metrica("Cómputo", p.get("compute_time_seconds", 0) / 3600, s.NEON_LIMITE_CU_HORAS, "CU-h", aviso),
        _metrica("Almacenamiento", p.get("synthetic_storage_size", 0) / _GB, s.NEON_LIMITE_STORAGE_GB, "GB", aviso),
    ]
    valor = {
        "desde": p.get("consumption_period_start"),
        "hasta": p.get("consumption_period_end"),
        "metricas": metricas,
        "alerta": any(m["alerta"] for m in metricas),
    }
    _cache.update(hasta=time.time() + _CACHE_SEGUNDOS, valor=valor)
    return valor


def texto_aviso(c: dict) -> str | None:
    altas = [m for m in c["metricas"] if m["alerta"]]
    if not altas:
        return None
    return "Neon cerca del límite del plan gratis: " + ", ".join(
        f"{m['nombre']} {m['usado']:.2f}/{m['limite']:g} {m['unidad']} ({m['porcentaje']:.0f}%)" for m in altas)
