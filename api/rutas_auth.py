"""Rutas de autenticación: registro, inicio y cierre de sesión, renovación,
perfil, cambio de contraseña y solicitud de acceso como investigador."""

import uuid
from datetime import timedelta
from typing import Literal

from fastapi import APIRouter, Depends, HTTPException, Request, Response
from pydantic import BaseModel, EmailStr, Field, field_validator
from pymongo.errors import DuplicateKeyError

from api import auditoria, config, db, dos_pasos
from api.deps import (
    proteger_csrf,
    requerir_sesion,
    requerir_sesion_permitiendo_cambio,
    usuario_opcional,
    usuario_publico,
)
from api.limites import verificar_limite
from bson import ObjectId
from bson.errors import InvalidId
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
    # Autorización expresa para el tratamiento de datos (Ley 1581 de 2012).
    acepta_politica: bool

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


class Verificacion2FA(_Base):
    desafio: str = Field(min_length=10, max_length=2000)
    codigo: str = Field(min_length=6, max_length=20)


class Codigo2FA(_Base):
    codigo: str = Field(min_length=6, max_length=20)


class Password(_Base):
    password: str = Field(min_length=1, max_length=256)


class PasswordYCodigo(_Base):
    password: str = Field(min_length=1, max_length=256)
    codigo: str = Field(min_length=6, max_length=20)


class EliminarCuenta(_Base):
    password: str = Field(min_length=1, max_length=256)
    confirmacion: Literal["ELIMINAR"]
    codigo: str | None = Field(default=None, min_length=6, max_length=20)


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


def _registro_consentimiento(request, momento):
    return {
        "version": config.POLITICA_VERSION,
        "fecha": momento,
        "ip": auditoria.ip_cliente(request),
        "medio": "formulario web",
    }


def _registrar_fallo(usuario, request, motivo):
    """Cuenta un intento fallido y bloquea la cuenta si se alcanza el máximo."""
    intentos = int(usuario.get("intentos_fallidos", 0)) + 1
    cambios = {"intentos_fallidos": intentos}
    if intentos >= config.MAX_INTENTOS_FALLIDOS:
        cambios = {"intentos_fallidos": 0, "bloqueado_hasta": ahora() + timedelta(minutes=config.MINUTOS_BLOQUEO)}
        auditoria.registrar("cuenta_bloqueada", request, usuario, detalle=f"{intentos} intentos fallidos", exito=False)
    db.usuarios.update_one({"_id": usuario["_id"]}, {"$set": cambios})
    auditoria.registrar("login", request, usuario, detalle=motivo, exito=False)


def _esta_bloqueado(usuario):
    bloqueado_hasta = a_utc(usuario.get("bloqueado_hasta"))
    return bool(bloqueado_hasta and bloqueado_hasta > ahora())


def _completar_login(usuario, request, response, metodo):
    cambios = {"intentos_fallidos": 0, "bloqueado_hasta": None, "ultimo_acceso": ahora()}
    db.usuarios.update_one({"_id": usuario["_id"]}, {"$set": cambios})
    usuario.update(cambios)
    auditoria.registrar("login", request, usuario, detalle=metodo)
    _emitir_sesion(response, usuario, request)
    return {"usuario": usuario_publico(usuario)}


def _verificar_segundo_factor(usuario, codigo):
    """Valida un código TOTP o de recuperación. Devuelve (ok, metodo).

    Si es válido, guarda el paso usado (TOTP) o elimina el código de
    recuperación consumido.
    """
    config2fa = usuario.get("dos_pasos") or {}
    secreto = dos_pasos.descifrar(config2fa.get("secreto", ""))
    if secreto:
        paso = dos_pasos.verificar_totp(secreto, codigo, config2fa.get("ultimo_paso"))
        if paso is not None:
            resultado = db.usuarios.update_one(
                # Condición atómica: el mismo código no se acepta dos veces.
                {"_id": usuario["_id"], "$or": [{"dos_pasos.ultimo_paso": None}, {"dos_pasos.ultimo_paso": {"$lt": paso}}]},
                {"$set": {"dos_pasos.ultimo_paso": paso}},
            )
            return resultado.modified_count == 1, "totp"
    restantes = dos_pasos.usar_codigo_recuperacion(config2fa.get("recuperacion"), codigo)
    if restantes is not None:
        db.usuarios.update_one({"_id": usuario["_id"]}, {"$set": {"dos_pasos.recuperacion": restantes}})
        return True, "codigo de recuperacion"
    return False, None


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

    if not datos.acepta_politica:
        raise HTTPException(
            status_code=400,
            detail="Debe aceptar la política de tratamiento de datos personales para crear una cuenta.",
        )

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
        # Prueba de la autorización (Decreto 1377 de 2013, art. 8).
        "consentimiento": _registro_consentimiento(request, momento),
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

    if _esta_bloqueado(usuario):
        verificar_tiempo_constante(datos.password)
        auditoria.registrar("login", request, usuario, detalle="cuenta bloqueada temporalmente", exito=False)
        raise HTTPException(
            status_code=423,
            detail=f"Cuenta bloqueada temporalmente por intentos fallidos. Intente en {config.MINUTOS_BLOQUEO} minutos.",
        )

    valida, necesita_rehash = verificar_password(datos.password, usuario.get("password_hash"))
    if not valida:
        _registrar_fallo(usuario, request, "contraseña incorrecta")
        raise HTTPException(status_code=401, detail=MENSAJE_CREDENCIALES)

    if not usuario.get("activo", False):
        auditoria.registrar("login", request, usuario, detalle="cuenta desactivada", exito=False)
        raise HTTPException(status_code=403, detail="Su cuenta está desactivada. Contacte al administrador.")

    if necesita_rehash:
        db.usuarios.update_one({"_id": usuario["_id"]}, {"$set": {"password_hash": hash_password(datos.password)}})

    # Con verificación en dos pasos, la contraseña sola NO abre sesión:
    # se entrega un desafío de 5 minutos para enviar el código del celular.
    if (usuario.get("dos_pasos") or {}).get("activo"):
        auditoria.registrar("login_primer_paso", request, usuario)
        return {"requiere_2fa": True, "desafio": dos_pasos.crear_desafio(usuario)}

    return _completar_login(usuario, request, response, "contraseña")


@router.post("/2fa/verificar")
def verificar_2fa(datos: Verificacion2FA, request: Request, response: Response):
    """Segundo paso del inicio de sesión."""
    ip = auditoria.ip_cliente(request)
    verificar_limite(f"2fa:{ip}", maximo=10, ventana_segundos=300)

    carga = dos_pasos.leer_desafio(datos.desafio)
    if not carga:
        raise HTTPException(status_code=401, detail="El tiempo para ingresar el código venció. Inicie sesión de nuevo.")
    try:
        usuario = db.usuarios.find_one({"_id": ObjectId(carga["sub"])})
    except (InvalidId, TypeError):
        usuario = None
    if (
        usuario is None
        or not usuario.get("activo", False)
        or int(usuario.get("token_version", 0)) != int(carga.get("ver", -1))
        or not (usuario.get("dos_pasos") or {}).get("activo")
    ):
        raise HTTPException(status_code=401, detail="Inicie sesión de nuevo.")

    if _esta_bloqueado(usuario):
        raise HTTPException(
            status_code=423,
            detail=f"Cuenta bloqueada temporalmente por intentos fallidos. Intente en {config.MINUTOS_BLOQUEO} minutos.",
        )

    ok, metodo = _verificar_segundo_factor(usuario, datos.codigo)
    if not ok:
        _registrar_fallo(usuario, request, "código de verificación incorrecto")
        raise HTTPException(status_code=401, detail="Código incorrecto o ya utilizado.")

    # Se recarga para reflejar el código de recuperación consumido.
    usuario = db.usuarios.find_one({"_id": usuario["_id"]})
    return _completar_login(usuario, request, response, f"contraseña + {metodo}")


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


# ------------------------------------------------------------
# Verificación en dos pasos: configuración
# ------------------------------------------------------------

@router.post("/2fa/iniciar")
def iniciar_2fa(datos: Password, request: Request, usuario=Depends(requerir_sesion)):
    """Genera un secreto nuevo (pendiente) y su código QR."""
    verificar_limite(f"2fa-config:{usuario['_id']}", maximo=10, ventana_segundos=900)
    valida, _ = verificar_password(datos.password, usuario.get("password_hash"))
    if not valida:
        raise HTTPException(status_code=400, detail="La contraseña no es correcta.")
    if (usuario.get("dos_pasos") or {}).get("activo"):
        raise HTTPException(status_code=400, detail="La verificación en dos pasos ya está activa.")

    secreto = dos_pasos.nuevo_secreto()
    db.usuarios.update_one(
        {"_id": usuario["_id"]},
        {"$set": {"dos_pasos_pendiente": {"secreto": dos_pasos.cifrar(secreto), "creado_en": ahora()}}},
    )
    uri = dos_pasos.uri_configuracion(secreto, usuario["email"])
    return {
        "qr": dos_pasos.qr_svg_data_uri(uri),
        # Para escribirlo a mano si no se puede escanear el QR.
        "clave_manual": " ".join(secreto[i:i + 4] for i in range(0, len(secreto), 4)),
    }


@router.post("/2fa/activar")
def activar_2fa(datos: Codigo2FA, request: Request, usuario=Depends(requerir_sesion)):
    """Confirma la configuración con un código del celular y entrega los códigos de recuperación."""
    verificar_limite(f"2fa-config:{usuario['_id']}", maximo=10, ventana_segundos=900)
    pendiente = usuario.get("dos_pasos_pendiente") or {}
    secreto = dos_pasos.descifrar(pendiente.get("secreto", ""))
    creado = a_utc(pendiente.get("creado_en"))
    if not secreto or not creado or creado < ahora() - timedelta(minutes=15):
        raise HTTPException(status_code=400, detail="La configuración venció. Empiece de nuevo.")

    paso = dos_pasos.verificar_totp(secreto, datos.codigo)
    if paso is None:
        raise HTTPException(
            status_code=400,
            detail="El código no coincide. Verifique que la hora de su celular esté en automático e intente con el código actual.",
        )

    codigos, hashes = dos_pasos.generar_codigos_recuperacion()
    db.usuarios.update_one(
        {"_id": usuario["_id"]},
        {
            "$set": {
                "dos_pasos": {
                    "activo": True,
                    "secreto": pendiente["secreto"],
                    "ultimo_paso": paso,
                    "recuperacion": hashes,
                    "activado_en": ahora(),
                }
            },
            "$unset": {"dos_pasos_pendiente": ""},
        },
    )
    auditoria.registrar("2fa_activado", request, usuario)
    actualizado = db.usuarios.find_one({"_id": usuario["_id"]})
    return {"codigos_recuperacion": codigos, "usuario": usuario_publico(actualizado)}


@router.post("/2fa/regenerar-codigos")
def regenerar_codigos(datos: PasswordYCodigo, request: Request, usuario=Depends(requerir_sesion)):
    verificar_limite(f"2fa-config:{usuario['_id']}", maximo=10, ventana_segundos=900)
    if not (usuario.get("dos_pasos") or {}).get("activo"):
        raise HTTPException(status_code=400, detail="La verificación en dos pasos no está activa.")
    valida, _ = verificar_password(datos.password, usuario.get("password_hash"))
    ok, _ = _verificar_segundo_factor(usuario, datos.codigo) if valida else (False, None)
    if not ok:
        raise HTTPException(status_code=400, detail="Contraseña o código incorrectos.")
    codigos, hashes = dos_pasos.generar_codigos_recuperacion()
    db.usuarios.update_one({"_id": usuario["_id"]}, {"$set": {"dos_pasos.recuperacion": hashes}})
    auditoria.registrar("2fa_codigos_regenerados", request, usuario)
    return {"codigos_recuperacion": codigos, "usuario": usuario_publico(db.usuarios.find_one({"_id": usuario["_id"]}))}


@router.post("/2fa/desactivar")
def desactivar_2fa(datos: PasswordYCodigo, request: Request, usuario=Depends(requerir_sesion)):
    verificar_limite(f"2fa-config:{usuario['_id']}", maximo=10, ventana_segundos=900)
    if not (usuario.get("dos_pasos") or {}).get("activo"):
        raise HTTPException(status_code=400, detail="La verificación en dos pasos no está activa.")
    if usuario.get("rol") == config.ROL_ADMIN and config.EXIGIR_2FA_ADMIN:
        raise HTTPException(status_code=400, detail="Los administradores deben mantener activa la verificación en dos pasos.")
    valida, _ = verificar_password(datos.password, usuario.get("password_hash"))
    ok, _ = _verificar_segundo_factor(usuario, datos.codigo) if valida else (False, None)
    if not ok:
        raise HTTPException(status_code=400, detail="Contraseña o código incorrectos.")
    db.usuarios.update_one({"_id": usuario["_id"]}, {"$unset": {"dos_pasos": ""}})
    auditoria.registrar("2fa_desactivado", request, usuario)
    return {"usuario": usuario_publico(db.usuarios.find_one({"_id": usuario["_id"]}))}


# ------------------------------------------------------------
# Derechos del titular (Ley 1581 de 2012): conocer, aceptar, suprimir
# ------------------------------------------------------------

@router.post("/aceptar-politica")
def aceptar_politica(request: Request, usuario=Depends(requerir_sesion_permitiendo_cambio)):
    """Para cuentas creadas antes de la política o cuando cambia su versión."""
    consentimiento = _registro_consentimiento(request, ahora())
    db.usuarios.update_one({"_id": usuario["_id"]}, {"$set": {"consentimiento": consentimiento}})
    usuario["consentimiento"] = consentimiento
    auditoria.registrar("politica_aceptada", request, usuario, detalle={"version": config.POLITICA_VERSION})
    return {"usuario": usuario_publico(usuario)}


@router.get("/mis-datos")
def mis_datos(request: Request, usuario=Depends(requerir_sesion_permitiendo_cambio)):
    """Copia de los datos personales que Coraleum guarda sobre la persona."""
    verificar_limite(f"mis-datos:{usuario['_id']}", maximo=10, ventana_segundos=3600)
    consentimiento = usuario.get("consentimiento") or {}
    eventos = db.auditoria_accesos.find({"usuario_id": usuario["_id"]}, {"_id": 0, "usuario_id": 0}).sort("fecha", -1).limit(500)
    auditoria.registrar("datos_descargados", request, usuario)
    return {
        "generado_en": ahora().strftime("%Y-%m-%dT%H:%M:%SZ"),
        "responsable": "Coraleum — ver Política de tratamiento de datos personales",
        "cuenta": usuario_publico(usuario),
        "consentimiento": {
            "version": consentimiento.get("version"),
            "fecha": consentimiento["fecha"].strftime("%Y-%m-%dT%H:%M:%SZ") if consentimiento.get("fecha") else None,
            "ip": consentimiento.get("ip"),
            "medio": consentimiento.get("medio"),
        },
        "solicitud_investigador": usuario_publico(usuario).get("solicitud"),
        "registro_de_actividad": [
            {**e, "fecha": e["fecha"].strftime("%Y-%m-%dT%H:%M:%SZ")} for e in eventos
        ],
        "datos_no_incluidos": "La contraseña y el secreto de verificación en dos pasos se guardan cifrados o como hash irreversible.",
    }


@router.post("/eliminar-cuenta")
def eliminar_cuenta(datos: EliminarCuenta, request: Request, response: Response, usuario=Depends(requerir_sesion_permitiendo_cambio)):
    """Supresión de la cuenta y sus datos personales.

    El registro de auditoría se conserva por seguridad pero se ANONIMIZA
    (se borran correo, IP y navegador asociados a la persona).
    """
    verificar_limite(f"eliminar:{usuario['_id']}", maximo=5, ventana_segundos=900)
    valida, _ = verificar_password(datos.password, usuario.get("password_hash"))
    if not valida:
        raise HTTPException(status_code=400, detail="La contraseña no es correcta.")
    if (usuario.get("dos_pasos") or {}).get("activo"):
        ok, _ = _verificar_segundo_factor(usuario, datos.codigo or "") if datos.codigo else (False, None)
        if not ok:
            raise HTTPException(status_code=400, detail="Ingrese un código válido de su aplicación de autenticación.")
    if usuario.get("rol") == config.ROL_ADMIN and db.usuarios.count_documents({"rol": config.ROL_ADMIN, "activo": True}) <= 1:
        raise HTTPException(status_code=400, detail="Es el único administrador activo. Asigne otro administrador antes de eliminar su cuenta.")

    db.sesiones.delete_many({"usuario_id": usuario["_id"]})
    db.auditoria_accesos.update_many(
        {"usuario_id": usuario["_id"]},
        {"$set": {"email": None, "ip": None, "user_agent": None, "usuario_id": None, "anonimizado": True}},
    )
    db.usuarios.delete_one({"_id": usuario["_id"]})
    auditoria.registrar("cuenta_eliminada", None, detalle="supresión solicitada por el titular")
    borrar_cookies_sesion(response)
    return {"ok": True}
