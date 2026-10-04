"""
Crea una cuenta ADMIN, o actualiza la contraseña si ya existe.

Uso (desde backend/):
    python create_admin.py                      # usa el email por defecto
    python create_admin.py otro@alu.frt.utn.edu.ar

La contraseña se pide por consola sin mostrarla. Para uso no interactivo
se puede pasar en la variable de entorno ADMIN_PASSWORD.
"""
import getpass
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from pydantic import ValidationError

from app.core.database import SessionLocal
from app.core.security import hash_password
from app.models.usuario import RolEnum, Usuario
from app.schemas.usuario import UsuarioCreate

EMAIL_POR_DEFECTO = "mauro.villagra1@alu.frt.utn.edu.ar"


def _nombre_desde_email(email: str) -> str:
    """'mauro.villagra1@...' → 'Mauro Villagra'."""
    local = email.split("@")[0].replace(".", " ").replace("_", " ")
    return " ".join(p.rstrip("0123456789").capitalize() for p in local.split()) or "Administrador"


def main() -> None:
    email = sys.argv[1] if len(sys.argv) > 1 else EMAIL_POR_DEFECTO
    password = os.environ.get("ADMIN_PASSWORD") or getpass.getpass("Contraseña (mín. 8, con un número): ")

    try:
        datos = UsuarioCreate(
            nombre=_nombre_desde_email(email), email=email, rol=RolEnum.ADMIN, password=password
        )
    except ValidationError as e:
        for err in e.errors():
            print(f"[ERROR] {err['loc'][-1]}: {err['msg']}")
        sys.exit(1)

    db = SessionLocal()
    try:
        admin = db.query(Usuario).filter(Usuario.email == datos.email).first()
        if admin:
            admin.password_hash = hash_password(datos.password)
            admin.rol = RolEnum.ADMIN
            admin.activo = True
            print(f"[OK] ADMIN actualizado: {datos.email}")
        else:
            db.add(Usuario(
                nombre=datos.nombre,
                email=datos.email,
                rol=RolEnum.ADMIN,
                password_hash=hash_password(datos.password),
                activo=True,
            ))
            print(f"[OK] ADMIN creado: {datos.email}")
        db.commit()
    finally:
        db.close()


if __name__ == "__main__":
    main()
