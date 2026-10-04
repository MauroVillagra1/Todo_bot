"""
Modelo Usuario — representa a cualquier persona del sistema.
Las cuentas se crean por registro público con código enviado al mail
institucional (siempre como MIEMBRO), o las crea un ADMIN (panel) o la consola. Roles: ver RolEnum y docs/ANALISIS_MVP.md §11.
"""
import enum
from datetime import datetime

from sqlalchemy import Boolean, DateTime, Enum, String, func
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base


class RolEnum(str, enum.Enum):
    MIEMBRO = "MIEMBRO"  # consulta el chat y la información disponible
    MOD     = "MOD"      # + revisa información, contradicciones y fuentes
    ADMIN   = "ADMIN"    # + administra fuentes, configuración y usuarios


class Usuario(Base):
    __tablename__ = "usuarios"

    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    nombre: Mapped[str] = mapped_column(String(150), nullable=False)
    email: Mapped[str] = mapped_column(String(255), unique=True, nullable=False, index=True)
    password_hash: Mapped[str] = mapped_column(String(255), nullable=False)
    rol: Mapped[RolEnum] = mapped_column(Enum(RolEnum), nullable=False)
    activo: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)

    creado_en: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    actualizado_en: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False,
    )

    def __repr__(self) -> str:
        return f"<Usuario id={self.id} email={self.email} rol={self.rol}>"
