"""
Modelo Usuario — representa a cualquier persona del sistema.
Roles:
  - administrador       → acceso completo, gestión de cuentas
  - administrativo      → carga eventos de calendario generales
  - jefe_departamento   → gestiona materias/comisiones de su carrera, hace anuncios
  - profesor            → gestiona sus propias cursadas (suspensiones, material, info)
  - alumno              → solo lectura de su comisión
"""
import enum
from datetime import datetime

from sqlalchemy import Boolean, DateTime, Enum, String, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base


class RolEnum(str, enum.Enum):
    administrador     = "administrador"
    administrativo    = "administrativo"
    jefe_departamento = "jefe_departamento"
    profesor          = "profesor"
    alumno            = "alumno"
    # alias legacy — se mantiene para no romper datos existentes en la DB
    profesor_directivo = "profesor_directivo"


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

    # Comisiones en las que participa (como alumno)
    comisiones: Mapped[list["UsuarioComision"]] = relationship(
        "UsuarioComision", back_populates="usuario", cascade="all, delete-orphan"
    )
    # Cursadas en las que participa (como profesor)
    cursadas_como_profesor: Mapped[list["CursadaProfesor"]] = relationship(
        "CursadaProfesor", back_populates="profesor", cascade="all, delete-orphan"
    )

    @property
    def es_profesor(self) -> bool:
        return self.rol in (RolEnum.profesor, RolEnum.profesor_directivo)

    @property
    def es_staff(self) -> bool:
        """Puede cargar datos (no alumno)."""
        return self.rol != RolEnum.alumno

    def __repr__(self) -> str:
        return f"<Usuario id={self.id} email={self.email} rol={self.rol}>"
