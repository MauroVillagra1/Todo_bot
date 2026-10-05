"""Cupo de Neon: avisos desde el 80 % y sin romper nada si la API no está configurada."""
from app.core.config import get_settings
from app.services import uso_neon

PROYECTO = {
    "consumption_period_start": "2026-10-01T00:00:00Z",
    "consumption_period_end": "2026-11-01T00:00:00Z",
    "data_transfer_bytes": int(4.2 * 1024 ** 3),  # 84 % de 5 GB
    "compute_time_seconds": 3600 * 10,
    "synthetic_storage_size": 40 * 1024 ** 2,
}


def _con_api(monkeypatch, proyecto):
    monkeypatch.setattr(get_settings(), "NEON_API_KEY", "clave")
    monkeypatch.setattr(uso_neon, "_proyecto", lambda cliente: proyecto)
    monkeypatch.setitem(uso_neon._cache, "hasta", 0.0)


def test_sin_api_key_no_hay_datos(monkeypatch):
    monkeypatch.setattr(get_settings(), "NEON_API_KEY", "")
    assert uso_neon.consumo() is None


def test_avisa_desde_el_80(monkeypatch):
    _con_api(monkeypatch, PROYECTO)
    c = uso_neon.consumo()
    transfer, computo, _ = c["metricas"]
    assert transfer["porcentaje"] == 84.0 and transfer["alerta"] and c["alerta"]
    assert computo["porcentaje"] == 10.0 and not computo["alerta"]
    assert "Transferencia 4.20/5 GB (84%)" in uso_neon.texto_aviso(c)


def test_api_caida_no_rompe(monkeypatch):
    def falla(cliente):
        raise RuntimeError("sin red")
    _con_api(monkeypatch, None)
    monkeypatch.setattr(uso_neon, "_proyecto", falla)
    assert uso_neon.consumo() is None


def test_detecta_endpoint_del_host(monkeypatch):
    monkeypatch.setattr(get_settings(), "DATABASE_URL",
                        "postgresql://u:p@ep-divine-fire-b4ialik9-pooler.c-6.us-east-2.aws.neon.tech/neondb")
    assert uso_neon._endpoint() == "ep-divine-fire-b4ialik9"
