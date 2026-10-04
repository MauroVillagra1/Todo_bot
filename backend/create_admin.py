"""Crea el usuario admin si no existe."""
import sys, os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from app.core.database import SessionLocal
from app.core.security import hash_password
from app.models.usuario import RolEnum, Usuario

db = SessionLocal()
try:
    admin = db.query(Usuario).filter(Usuario.email == "admin@admin.frt.utn.edu.ar").first()
    if admin:
        admin.password_hash = hash_password("123456")
        admin.activo = True
        print("✏️  Admin actualizado")
    else:
        admin = Usuario(
            nombre="Administrador Sistema",
            email="admin@admin.frt.utn.edu.ar",
            rol=RolEnum.administrador,
            password_hash=hash_password("123456"),
            activo=True,
        )
        db.add(admin)
        print("✅ Admin creado")
    db.commit()
    print(f"   email: admin@admin.frt.utn.edu.ar")
    print(f"   pass:  123456")
finally:
    db.close()
