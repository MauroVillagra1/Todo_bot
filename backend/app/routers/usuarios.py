"""
Router de usuarios (gestión de cuentas).
Solo ADMIN puede crear, listar y modificar usuarios. No hay registro público:
el email debe ser institucional (DOMINIOS_PERMITIDOS) y lo valida el schema.
"""
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.dependencies import require_admin
from app.core.security import hash_password
from app.models.usuario import RolEnum, Usuario
from app.schemas.common import MessageResponse, PaginatedResponse
from app.schemas.usuario import UsuarioCreate, UsuarioRead, UsuarioUpdate

router = APIRouter(prefix="/usuarios", tags=["Usuarios"])


@router.post("/", response_model=UsuarioRead, status_code=status.HTTP_201_CREATED)
def crear_usuario(
    data: UsuarioCreate,
    db: Session = Depends(get_db),
    _admin=Depends(require_admin),
):
    """Crea un nuevo usuario. Solo administradores."""
    if db.query(Usuario).filter(Usuario.email == data.email).first():
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Ya existe un usuario con ese email",
        )
    usuario = Usuario(
        nombre=data.nombre,
        email=data.email,
        rol=data.rol,
        password_hash=hash_password(data.password),
    )
    db.add(usuario)
    db.commit()
    db.refresh(usuario)
    return usuario


@router.get("/", response_model=PaginatedResponse[UsuarioRead])
def listar_usuarios(
    page: int = 1,
    page_size: int = 20,
    db: Session = Depends(get_db),
    _admin=Depends(require_admin),
):
    """Lista todos los usuarios con paginación. Solo administradores."""
    offset = (page - 1) * page_size
    total = db.query(Usuario).count()
    usuarios = db.query(Usuario).offset(offset).limit(page_size).all()
    return PaginatedResponse(items=usuarios, total=total, page=page, page_size=page_size)


@router.get("/{usuario_id}", response_model=UsuarioRead)
def obtener_usuario(
    usuario_id: int,
    db: Session = Depends(get_db),
    _admin=Depends(require_admin),
):
    """Obtiene un usuario por ID. Solo administradores."""
    usuario = db.get(Usuario, usuario_id)
    if not usuario:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Usuario no encontrado")
    return usuario


@router.patch("/{usuario_id}", response_model=UsuarioRead)
def actualizar_usuario(
    usuario_id: int,
    data: UsuarioUpdate,
    db: Session = Depends(get_db),
    admin: Usuario = Depends(require_admin),
):
    """Actualiza campos de un usuario (incluido el rol). Solo administradores."""
    usuario = db.get(Usuario, usuario_id)
    if not usuario:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Usuario no encontrado")

    update_data = data.model_dump(exclude_unset=True)

    # Evita que un ADMIN se deje sin acceso a sí mismo por error
    if usuario.id == admin.id and (
        update_data.get("activo") is False
        or update_data.get("rol", RolEnum.ADMIN) != RolEnum.ADMIN
    ):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="No podés desactivarte ni quitarte el rol ADMIN a vos mismo",
        )

    if "email" in update_data and update_data["email"] != usuario.email:
        if db.query(Usuario).filter(Usuario.email == update_data["email"]).first():
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="Ya existe un usuario con ese email",
            )

    if "password" in update_data:
        update_data["password_hash"] = hash_password(update_data.pop("password"))

    for field, value in update_data.items():
        setattr(usuario, field, value)

    db.commit()
    db.refresh(usuario)
    return usuario
