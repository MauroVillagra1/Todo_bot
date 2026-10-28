"""
Crea (o deja al día) una cuenta de prueba por rango, todas con la misma contraseña:
    usuario@alu.frt.utn.edu.ar  → USUARIO
    mod@alu.frt.utn.edu.ar      → MOD
    smod@alu.frt.utn.edu.ar     → SMOD
    admin@alu.frt.utn.edu.ar    → ADMIN
Si la cuenta ya existe le pone el rango, la reactiva y le cambia la contraseña (cierra sus sesiones).

Uso (desde backend/, con la migración 26 aplicada):
    python scripts/cuentas_prueba.py
La contraseña se pide por consola sin mostrarla; también se puede pasar en PRUEBA_PASSWORD.
"""
import getpass
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from pydantic import ValidationError  # noqa: E402

from app.core.database import SessionLocal  # noqa: E402
from app.core.security import hash_password  # noqa: E402
from app.models.usuario import RolEnum, Usuario  # noqa: E402
from app.schemas.usuario import UsuarioCreate  # noqa: E402

CUENTAS = [
    ("usuario@alu.frt.utn.edu.ar", "Usuario Prueba", RolEnum.USUARIO),
    ("mod@alu.frt.utn.edu.ar", "Mod Prueba", RolEnum.MOD),
    ("smod@alu.frt.utn.edu.ar", "Smod Prueba", RolEnum.SMOD),
    ("admin@alu.frt.utn.edu.ar", "Admin Prueba", RolEnum.ADMIN),
]


def main() -> None:
    password = os.environ.get("PRUEBA_PASSWORD") or getpass.getpass("Contraseña de prueba (mín. 8, con un número): ")
    try:
        UsuarioCreate(nombre="Prueba", email=CUENTAS[0][0], password=password)
    except ValidationError as e:
        for err in e.errors():
            print(f"[ERROR] {err['loc'][-1]}: {err['msg']}")
        sys.exit(1)

    db = SessionLocal()
    try:
        for email, nombre, rol in CUENTAS:
            u = db.query(Usuario).filter(Usuario.email == email).first()
            if u:
                u.rol, u.activo, u.baneado_hasta, u.motivo_ban = rol, True, None, None
                u.password_hash = hash_password(password)
                u.version_sesion += 1
                u.intentos_fallidos, u.bloqueado_hasta = 0, None
                print(f"[OK] {rol.value:<7} actualizada: {email}")
            else:
                db.add(Usuario(nombre=nombre, email=email, rol=rol, password_hash=hash_password(password), activo=True))
                print(f"[OK] {rol.value:<7} creada:      {email}")
        db.commit()
    finally:
        db.close()


if __name__ == "__main__":
    main()
