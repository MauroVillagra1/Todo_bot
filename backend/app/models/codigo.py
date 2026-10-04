"""
Códigos de verificación enviados por mail (registro y recuperación de contraseña).
El código se guarda hasheado; en el registro, los datos de la cuenta esperan acá
hasta que se verifica el mail (la cuenta no existe antes).
"""
import enum
from datetime import datetime

from sqlalchemy import JSON, Boolean, DateTime, Enum, Integer, String, func
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base


class PropositoCodigoEnum(str, enum.Enum):
    REGISTRO = "REGISTRO"
    RECUPERACION = "RECUPERACION"


class CodigoVerificacion(Base):
    __tablename__ = "codigos_verificacion"

    id: Mapped[int] = mapped_column(primary_key=True)
    email: Mapped[str] = mapped_column(String(255), nullable=False, index=True)
    proposito: Mapped[PropositoCodigoEnum] = mapped_column(Enum(PropositoCodigoEnum), nullable=False)
    codigo_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    datos: Mapped[dict] = mapped_column(JSON, nullable=False, default=dict)  # registro: nombre y hash
    intentos: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    usado: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    expira_en: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    creado_en: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
