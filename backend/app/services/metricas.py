"""
Registro de métricas diarias con un upsert atómico (seguro con varias
invocaciones serverless o el worker escribiendo a la vez).
"""
from datetime import date

from sqlalchemy.orm import Session

from app.models.metrica import MetricaDiaria


def incrementar(db: Session, metrica: str, cantidad: int = 1, dia: date | None = None) -> None:
    """Suma `cantidad` a la métrica del día. No hace commit: lo hace quien llama."""
    if cantidad == 0:
        return
    if db.bind.dialect.name == "postgresql":
        from sqlalchemy.dialects.postgresql import insert
    else:
        from sqlalchemy.dialects.sqlite import insert

    stmt = insert(MetricaDiaria).values(dia=dia or date.today(), metrica=metrica, valor=cantidad)
    stmt = stmt.on_conflict_do_update(
        index_elements=["dia", "metrica"],
        set_={"valor": MetricaDiaria.valor + stmt.excluded.valor},
    )
    db.execute(stmt)
