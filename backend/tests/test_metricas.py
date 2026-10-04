from datetime import date

from app.models.metrica import MetricaDiaria
from app.services.metricas import incrementar


def test_incrementar_acumula_por_dia_y_metrica(db):
    MetricaDiaria.__table__.create(db.get_bind())
    hoy, ayer = date(2026, 10, 3), date(2026, 10, 2)

    incrementar(db, "duplicados_descartados", dia=hoy)
    incrementar(db, "duplicados_descartados", 4, dia=hoy)
    incrementar(db, "duplicados_descartados", dia=ayer)
    incrementar(db, "llamadas_llm", 0, dia=hoy)  # cero no crea fila
    db.commit()

    valores = {(m.dia, m.metrica): m.valor for m in db.query(MetricaDiaria)}
    assert valores == {
        (hoy, "duplicados_descartados"): 5,
        (ayer, "duplicados_descartados"): 1,
    }
