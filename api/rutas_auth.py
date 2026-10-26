"""Rutas de autenticación: registro, inicio y cierre de sesión, renovación,
perfil, cambio de contraseña y solicitud de acceso como investigador."""

import uuid
from datetime import timedelta

from fastapi import APIRouter, Depends, HTTPException, Request, Response
from pydantic import BaseModel, EmailStr, Field, field_validator
from pymongo.errors import DuplicateKeyError

from api import auditoria, config, db
from api.deps import (
    proteger_csrf,
    requerir_sesion,
    requerir_sesion_permitiendo_cambio,
    usuario_opcional,
    usuario_publico,
)
from api.limites import verificar_limite
from api.seguridad import (
    a_utc,
    ahora,
    borrar_cookies_sesion,
    crear_access_token,
    generar_refresh_token,
    hash_password,
    hash_token,
    poner_cookies_sesion,
    validar_politica_password,
    verificar_password,
    verificar_tiempo_constante,
)

router = APIRouter(prefix="/auth", tags=["autenticación"], dependencies=[Depends(proteger_csrf)])

MENSAJE_CREDENCIALES = "Correo o contraseña incorrectos."


# ------------------------------------------------------------
# Modelos de entrada (validación estricta de datos, RS02)
# ------------------------------------------------------------

class _Base(BaseModel):
    model_config = {"extra": "forbid", "str_strip_whitespace": True}


class Registro(_Base):
    nombre: str = Field(min_length=2, max_length=80)
    email: EmailStr = Field(max_length=254)
    password: str = Field(min_length=1, max_length=256)

    @field_validator("nombre")
    @classmethod
    def nombre_valido(cls, valor):
        if any(c in valor for c in "<>{}$"):
            raise ValueError("El nombre contiene caracteres no permitidos.")
        return " ".join(valor.split())


class Login(_Base):
    email: EmailStr = Field(max_length=254)
    password: str = Field(min_length=1, max_length=256)


class CambioPassword(_Base):
    password_actual: str = Field(min_length=1, max_length=256)
    password_nueva: str = Field(min_length=1, max_length=256)


class SolicitudInvestigador(_Base):
    institucion: str = Field(min_length=2, max_length=120)
    motivo: str = Field(min_length=10, max_length=500)


# ------------------------------------------------------------
# Sesiones
# ------------------------------------------------------------

def _crear_sesion(usuario, request, familia=None):
    """Crea un refresh token (guardado como hash) y devuelve el token en claro."""
    token = generar_refresh_token()
    momento = ahora()
    db.sesiones.insert_one(
        {
            "token_hash": hash_token(token),
            "usuario_id": usuario["_id"],
            "familia": familia or uuid.uuid4().hex,
            "token_version": int(usuario.get("token_version", 0)),
            "creado_en": momento,
            "expira": momento + timedelta(days=config.REFRESH_DIAS),
            "revocado_en": None,
            "ip": auditoria.ip_cliente(request),
            "user_agent": request.headers.get("user-agent", "")[:200],
        }
    )
    return token


def _emitir_sesion(respuesta, usuario, request, familia=None):
    refresh = _crear_sesion(usuario, request, familia)
    poner_cookies_sesion(respuesta, crear_access_token(usuario), refresh)


def revocar_sesiones_usuario(usuario_id):
    db.sesiones.update_many(
        {"usuario_id": usuario_id, "revocado_en": None},
        {"$set": {"revocado_en": ahora()}},
    )


# ------------------------------------------------------------
# Rutas
# ------------------------------------------------------------

@router.post("/registro", status_code=201)
def registro(datos: Registro, request: Request, response: Response):
    ip = auditoria.ip_cliente(request)
    verificar_limite(f"registro:{ip}", maximo=5, ventana_segundos=3600)

    email = datos.email.lower()
    error = validar_politica_password(datos.password, email, datos.nombre)
    if error:
        raise HTTPException(status_code=400, detail=error)

    momento = ahora()
    usuario = {
        "nombre": datos.nombre,
        "email": email,
        "password_hash": hash_password(datos.password),
        # Registrarse NUNCA otorga acceso a los datos: el rol inicial es
        # "usuario"; el acceso de investigador lo aprueba un administrador.
        "rol": config.ROL_USUARIO,
        "activo": True,
        "debe_cambiar_password": False,
        "token_version": 0,
        "intentos_fallidos": 0,
        "bloqueado_hasta": None,
        "solicitud": None,
        "creado_en": momento,
        "ultimo_acceso": momento,
    }
    try:
        resultado = db.usuarios.insert_one(usuario)
    except DuplicateKeyError:
        auditoria.registrar("registro", request, email=email, detalle="correo ya registrado", exito=False)
        raise HTTPException(
            status_code=409,
            detail="No fue posible crear la cuenta con ese correo. Si ya tiene una cuenta, inicie sesión.",
        )
    usuario["_id"] = resultado.inserted_id
    auditoria.registrar("registro", request, usuario)
    _emitir_sesion(response, usuario, request)
    return {"usuario": usuario_publico(usuario)}


@router.post("/login")
def login(datos: Login, request: Request, response: Response):
    ip = auditoria.ip_cliente(request)
    verificar_limite(f"login:{ip}", maximo=10, ventana_segundos=300)

    email = datos.email.lower()
    usuario = db.usuarios.find_one({"email": email})

    if usuario is None:
        verificar_tiempo_constante(datos.password)
        auditoria.registrar("login", request, email=email, detalle="correo no registrado", exito=False)
        raise HTTPException(status_code=401, detail=MENSAJE_CREDENCIALES)

    bloqueado_hasta = a_utc(usuario.get("bloqueado_hasta"))
    if bloqueado_hasta and bloqueado_hasta > ahora():
        verificar_tiempo_constante(datos.password)
        auditoria.registrar("login", request, usuario, detalle="cuenta bloqueada temporalmente", exito=False)
        raise HTTPException(
            status_code=423,
            detail=f"Cuenta bloqueada temporalmente por intentos fallidos. Intente en {config.MINUTOS_BLOQUEO} minutos.",
        )

    valida, necesita_rehash = verificar_password(datos.password, usuario.get("password_hash"))
    if not valida:
        intentos = int(usuario.get("intentos_fallidos", 0)) + 1
        cambios = {"intentos_fallidos": intentos}
        if intentos >= config.MAX_INTENTOS_FALLIDOS:
            cambios = {"intentos_fallidos": 0, "bloqueado_hasta": ahora() + timedelta(minutes=config.MINUTOS_BLOQUEO)}
            auditoria.registrar("cuenta_bloqueada", request, usuario, detalle=f"{intentos} intentos fallidos", exito=False)
        db.usuarios.update_one({"_id": usuario["_id"]}, {"$set": cambios})
        auditoria.registrar("login", request, usuario, detalle="contraseña incorrecta", exito=False)
        raise HTTPException(status_code=401, detail=MENSAJE_CREDENCIALES)

    if not usuario.get("activo", False):
        auditoria.registrar("login", request, usuario, detalle="cuenta desactivada", exito=False)
        raise HTTPException(status_code=403, detail="Su cuenta está desactivada. Contacte al administrador.")

    cambios = {"intentos_fallidos": 0, "bloqueado_hasta": None, "ultimo_acceso": ahora()}
    if necesita_rehash:
        cambios["password_hash"] = hash_password(datos.password)
    db.usuarios.update_one({"_id": usuario["_id"]}, {"$set": cambios})
    usuario.update(cambios)

    auditoria.registrar("login", request, usuario)
    _emitir_sesion(response, usuario, request)
    return {"usuario": usuario_publico(usuario)}


@router.post("/refresh")
def refresh(request: Request, response: Response):
    """Renueva la sesión rotando el refresh token.

    Si se presenta un refresh token que ya fue usado (posible robo), se
    revoca toda la familia de sesiones derivadas de él.
    """
    ip = auditoria.ip_cliente(request)
    verificar_limite(f"refresh:{ip}", maximo=60, ventana_segundos=300)

    token = request.cookies.get(config.COOKIE_REFRESH)
    if not token:
        raise HTTPException(status_code=401, detail="Sesión no válida.")

    sesion = db.sesiones.find_one({"token_hash": hash_token(token)})
    if sesion is None or a_utc(sesion["expira"]) <= ahora():
        borrar_cookies_sesion(response)
        raise HTTPException(status_code=401, detail="Sesión vencida. Inicie sesión de nuevo.")

    usuario = db.usuarios.find_one({"_id": sesion["usuario_id"]})

    if sesion.get("revocado_en") is not None:
        db.sesiones.update_many(
            {"familia": sesion["familia"], "revocado_en": None},
            {"$set": {"revocado_en": ahora()}},
        )
        auditoria.registrar("refresh_reutilizado", request, usuario, detalle="se revocó la familia de sesiones", exito=False)
        borrar_cookies_sesion(response)
        raise HTTPException(status_code=401, detail="Sesión no válida. Inicie sesión de nuevo.")

    if (
        usuario is None
        or not usuario.get("activo", False)
        or int(usuario.get("token_version", 0)) != int(sesion.get("token_version", -1))
    ):
        db.sesiones.update_one({"_id": sesion["_id"]}, {"$set": {"revocado_en": ahora()}})
        borrar_cookies_sesion(response)
        raise HTTPException(status_code=401, detail="Sesión no válida. Inicie sesión de nuevo.")

    # Marcado atómico: si dos peticiones usan el mismo token a la vez, solo una gana.
    marcado = db.sesiones.update_one(
        {"_id": sesion["_id"], "revocado_en": None},
        {"$set": {"revocado_en": ahora()}},
    )
    if marcado.modified_count != 1:
        borrar_cookies_sesion(response)
        raise HTTPException(status_code=401, detail="Sesión no válida. Inicie sesión de nuevo.")

    _emitir_sesion(response, usuario, request, familia=sesion["familia"])
    return {"usuario": usuario_publico(usuario)}


@router.post("/logout")
def logout(request: Request, response: Response, usuario=Depends(usuario_opcional)):
    token = request.cookies.get(config.COOKIE_REFRESH)
    if token:
        db.sesiones.update_one(
            {"token_hash": hash_token(token), "revocado_en": None},
            {"$set": {"revocado_en": ahora()}},
        )
    if usuario:
        auditoria.registrar("logout", request, usuario)
    borrar_cookies_sesion(response)
    return {"ok": True}


@router.get("/me")
def me(usuario=Depends(usuario_opcional)):
    """Devuelve el usuario actual o null si es un visitante (no es un error)."""
    return {"usuario": usuario_publico(usuario) if usuario else None}


@router.post("/cambiar-password")
def cambiar_password(
    datos: CambioPassword,
    request: Request,
    response: Response,
    usuario=Depends(requerir_sesion_permitiendo_cambio),
):
    verificar_limite(f"cambio:{usuario['_id']}", maximo=5, ventana_segundos=900)

    valida, _ = verificar_password(datos.password_actual, usuario.get("password_hash"))
    if not valida:
        auditoria.registrar("cambio_password", request, usuario, detalle="contraseña actual incorrecta", exito=False)
        raise HTTPException(status_code=400, detail="La contraseña actual no es correcta.")

    if datos.password_nueva == datos.password_actual:
        raise HTTPException(status_code=400, detail="La nueva contraseña debe ser distinta de la actual.")

    error = validar_politica_password(datos.password_nueva, usuario.get("email"), usuario.get("nombre"))
    if error:
        raise HTTPException(status_code=400, detail=error)

    nueva_version = int(usuario.get("token_version", 0)) + 1
    db.usuarios.update_one(
        {"_id": usuario["_id"]},
        {
            "$set": {
                "password_hash": hash_password(datos.password_nueva),
                "debe_cambiar_password": False,
                "token_version": nueva_version,
            }
        },
    )
    # Cierra todas las demás sesiones abiertas con la contraseña anterior.
    revocar_sesiones_usuario(usuario["_id"])
    usuario.update({"token_version": nueva_version, "debe_cambiar_password": False})
    auditoria.registrar("cambio_password", request, usuario)
    _emitir_sesion(response, usuario, request)
    return {"usuario": usuario_publico(usuario)}


@router.post("/solicitar-investigador")
def solicitar_investigador(datos: SolicitudInvestigador, request: Request, usuario=Depends(requerir_sesion)):
    if usuario.get("rol") != config.ROL_USUARIO:
        raise HTTPException(status_code=400, detail="Su cuenta ya tiene acceso a la información de investigación.")
    solicitud_actual = usuario.get("solicitud") or {}
    if solicitud_actual.get("estado") == "pendiente":
        raise HTTPException(status_code=409, detail="Ya tiene una solicitud pendiente de revisión.")

    solicitud = {
        "estado": "pendiente",
        "institucion": datos.institucion,
        "motivo": datos.motivo,
        "fecha": ahora(),
        "comentario_admin": None,
    }
    db.usuarios.update_one({"_id": usuario["_id"]}, {"$set": {"solicitud": solicitud}})
    usuario["solicitud"] = solicitud
    auditoria.registrar("solicitud_investigador", request, usuario, detalle={"institucion": datos.institucion})
    return {"usuario": usuario_publico(usuario)}
