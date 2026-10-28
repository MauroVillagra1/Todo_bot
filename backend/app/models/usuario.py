"""
Modelo Usuario — representa a cualquier persona del sistema.
Las cuentas se crean por registro público con código enviado al mail
institucional (MIEMBRO; los docentes, MOD: ver rol_inicial) o por consola (create_admin.py). Roles: ver RolEnum.
Suspensión: activo=False es permanente; baneado_hasta en el futuro es temporal.
"""
import enum
from datetime import datetime, timezone

from sqlalchemy import Integer, Boolean, DateTime, Enum, String, func
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base


class RolEnum(str, enum.Enum):
    MIEMBRO = "MIEMBRO"  # consulta el chat y la información disponible
    MOD     = "MOD"      # + carga información en el chat (formulario "Cargar información")
    SMOD    = "SMOD"     # + paros, documentos, horarios, mesas, calendario, sugerencias; da o quita MOD
    ADMIN   = "ADMIN"    # + resumen, reportes, rangos y suspensiones, historial de cambios, importar archivos


DOMINIO_DOCENTES = "doc.frt.utn.edu.ar"


def rol_inicial(email: str) -> RolEnum:
    """Rol al registrarse: los docentes (nombre.apellido@doc.frt.utn.edu.ar) entran como MOD."""
    return RolEnum.MOD if email.lower().endswith("@" + DOMINIO_DOCENTES) else RolEnum.MIEMBRO


class Usuario(Base):
    __tablename__ = "usuarios"

    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    nombre: Mapped[str] = mapped_column(String(150), nullable=False)
    email: Mapped[str] = mapped_column(String(255), unique=True, nullable=False, index=True)
    password_hash: Mapped[str] = mapped_column(String(255), nullable=False)
    rol: Mapped[RolEnum] = mapped_column(Enum(RolEnum), nullable=False)
    activo: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    baneado_hasta: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    motivo_ban: Mapped[str | None] = mapped_column(String(300))
    # Va en cada JWT (claim "ver"): subirla cierra todas las sesiones (logout, contraseña nueva)
    version_sesion: Mapped[int] = mapped_column(Integer, default=0, server_default="0", nullable=False)
    # Contraseña mal varias veces seguidas: el login se bloquea un rato (fuerza bruta)
    intentos_fallidos: Mapped[int] = mapped_column(Integer, default=0, server_default="0", nullable=False)
    bloqueado_hasta: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    creado_en: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    actualizado_en: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False,
    )

    def suspendido_hasta(self) -> datetime | None:
        """Fin de la suspensión temporal vigente, o None si no hay."""
        hasta = self.baneado_hasta
        if hasta is None:
            return None
        if hasta.tzinfo is None:  # SQLite (tests) no guarda la zona
            hasta = hasta.replace(tzinfo=timezone.utc)
        return hasta if hasta > datetime.now(timezone.utc) else None

    def __repr__(self) -> str:
        return f"<Usuario id={self.id} email={self.email} rol={self.rol}>"
