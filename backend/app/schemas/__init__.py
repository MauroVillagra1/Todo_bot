from app.schemas.usuario import UsuarioCreate, UsuarioRead, UsuarioUpdate
from app.schemas.academico import (
    MateriaCreate, MateriaRead,
    PeriodoAcademicoCreate, PeriodoAcademicoRead,
    ComisionCreate, ComisionRead,
    UsuarioComisionCreate, UsuarioComisionRead,
)
from app.schemas.cursada import (
    CursadaCreate, CursadaRead,
    CursadaProfesorCreate, CursadaProfesorRead,
    CursadaExcepcionCreate, CursadaExcepcionRead,
)
from app.schemas.eventos import EventoCalendarioCreate, EventoCalendarioRead
from app.schemas.material import MaterialApoyoCreate, MaterialApoyoRead
from app.schemas.auth import TokenResponse, LoginRequest
