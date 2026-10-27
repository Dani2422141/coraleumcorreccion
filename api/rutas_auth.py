"""Rutas de autenticación: registro, inicio y cierre de sesión, renovación,
perfil, cambio de contraseña y solicitud de acceso como investigador."""

import uuid
from datetime import timedelta
from typing import Literal

from fastapi import APIRouter, Depends, HTTPException, Path, Request, Response
from starlette.concurrency import run_in_threadpool
from pydantic import BaseModel, EmailStr, Field, field_validator
from pymongo.errors import DuplicateKeyError

from api import archivos, auditoria, cifrado, config, db, dos_pasos, permisos, sesion_config
from api.deps import (
    MENSAJES_VENCIMIENTO,
    ErrorSesion,
    _iso,
    cerrar_sesion_vencida,
    motivo_sesion_vencida,
    revocar_sesiones,
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


class CambioEmail(_Base):
    email_nuevo: EmailStr = Field(max_length=254)
    password: str = Field(min_length=1, max_length=256)
    codigo: str | None = Field(default=None, min_length=6, max_length=20)


class OlvidePassword(_Base):
    email: EmailStr = Field(max_length=254)


class SolicitudInvestigador(_Base):
    institucion: str = Field(min_length=2, max_length=120)
    motivo: str = Field(min_length=10, max_length=500)
    # Documento PDF cargado antes con /auth/solicitud/soporte (opcional).
    soporte_id: str | None = Field(default=None, pattern=r"^[0-9a-f]{24}$")


# ------------------------------------------------------------
# Sesiones
# ------------------------------------------------------------

def _crear_sesion(usuario, request, familia=None, inicio=None):
    """Crea una sesión del servidor y su refresh token (guardado como hash).

    `inicio` se hereda al renovar: la duración máxima se cuenta desde el
    inicio de sesión original, no desde la última renovación.
    """
    token = generar_refresh_token()
    momento = ahora()
    inicio = inicio or momento
    resultado = db.sesiones.insert_one(
        {
            "token_hash": hash_token(token),
            "usuario_id": usuario["_id"],
            "familia": familia or uuid.uuid4().hex,
            "token_version": int(usuario.get("token_version", 0)),
            "inicio": inicio,
            "creado_en": momento,
            "ultima_actividad": momento,
            # Límite superior absoluto: MongoDB borra la sesión después (TTL).
            "expira": inicio + timedelta(hours=sesion_config.HORAS_LIMITE),
            "revocado_en": None,
            "ip": auditoria.ip_cliente(request),
            "user_agent": request.headers.get("user-agent", "")[:200],
        }
    )
    return resultado.inserted_id, token, inicio


def describir_navegador(user_agent):
    """'Mozilla/5.0 (Windows NT 10.0…) … Chrome/…' → 'Chrome en Windows'."""
    ua = user_agent or ""
    if "Edg/" in ua:
        navegador = "Edge"
    elif "OPR/" in ua or "Opera" in ua:
        navegador = "Opera"
    elif "Firefox/" in ua:
        navegador = "Firefox"
    elif "Chrome/" in ua or "Chromium/" in ua:
        navegador = "Chrome"
    elif "Safari/" in ua:
        navegador = "Safari"
    else:
        navegador = "Navegador desconocido"
    for marca, sistema in (("Windows", "Windows"), ("Android", "Android"), ("iPhone", "iPhone"),
                           ("iPad", "iPad"), ("Mac OS", "macOS"), ("Linux", "Linux")):
        if marca in ua:
            return f"{navegador} en {sistema}"
    return navegador


def _aplicar_limite_sesiones(usuario, request, conf):
    """Si la persona ya tiene el máximo de sesiones abiertas, cierra la(s) que
    lleva(n) más tiempo sin usarse. Devuelve los navegadores cerrados."""
    activas = []
    for sesion in db.sesiones.find({"usuario_id": usuario["_id"], "revocado_en": None}):
        motivo = motivo_sesion_vencida(sesion, conf)
        if motivo:
            cerrar_sesion_vencida(sesion, motivo, request)
        else:
            activas.append(sesion)
    exceso = len(activas) - conf["sesiones_simultaneas"] + 1
    if exceso <= 0:
        return []
    activas.sort(key=lambda s: a_utc(s.get("ultima_actividad") or s["creado_en"]))
    cerradas = activas[:exceso]
    revocar_sesiones({"_id": {"$in": [s["_id"] for s in cerradas]}}, "reemplazada")
    navegadores = [describir_navegador(s.get("user_agent")) for s in cerradas]
    auditoria.registrar(
        "sesion_reemplazada",
        request,
        usuario,
        detalle={
            "limite": conf["sesiones_simultaneas"],
            "cerradas": ", ".join(navegadores),
            "nueva": describir_navegador(request.headers.get("user-agent")),
        },
    )
    return navegadores


def _emitir_sesion(respuesta, usuario, request, familia=None, inicio=None):
    """Crea la sesión y pone las cookies. Devuelve los navegadores cuya sesión
    se cerró por superar el límite de sesiones simultáneas."""
    conf = sesion_config.obtener()
    cerradas = _aplicar_limite_sesiones(usuario, request, conf) if familia is None else []
    sid, refresh, inicio = _crear_sesion(usuario, request, familia, inicio)
    restante = inicio + timedelta(hours=conf["maxima_horas"]) - ahora()
    poner_cookies_sesion(
        respuesta,
        crear_access_token(usuario, sid, conf["token_minutos"]),
        refresh,
        access_segundos=conf["token_minutos"] * 60,
        refresh_segundos=max(int(restante.total_seconds()), 60),
    )
    return cerradas


def _registro_consentimiento(request, momento):
    return {
        "version": config.POLITICA_VERSION,
        "fecha": momento,
        "ip": auditoria.ip_cliente(request),
        "medio": "formulario web",
    }


MENSAJE_BLOQUEO = (
    f"Cuenta bloqueada temporalmente por {config.MAX_INTENTOS_FALLIDOS} intentos fallidos. "
    f"Intente de nuevo en {config.MINUTOS_BLOQUEO} minutos."
)


def _registrar_fallo(usuario, request, motivo):
    """Cuenta un intento fallido; al llegar al máximo bloquea la cuenta.

    Devuelve True si este intento provocó el bloqueo.
    """
    intentos = int(usuario.get("intentos_fallidos", 0)) + 1
    cambios = {"intentos_fallidos": intentos}
    bloqueada = intentos >= config.MAX_INTENTOS_FALLIDOS
    if bloqueada:
        cambios = {"intentos_fallidos": 0, "bloqueado_hasta": ahora() + timedelta(minutes=config.MINUTOS_BLOQUEO)}
    db.usuarios.update_one({"_id": usuario["_id"]}, {"$set": cambios})
    auditoria.registrar("login", request, usuario, detalle=motivo, exito=False)
    if bloqueada:
        auditoria.registrar("cuenta_bloqueada", request, usuario, detalle=f"{intentos} intentos fallidos", exito=False)
    return bloqueada


def _esta_bloqueado(usuario):
    bloqueado_hasta = a_utc(usuario.get("bloqueado_hasta"))
    return bool(bloqueado_hasta and bloqueado_hasta > ahora())


def _completar_login(usuario, request, response, metodo):
    cambios = {"intentos_fallidos": 0, "bloqueado_hasta": None, "ultimo_acceso": ahora()}
    db.usuarios.update_one({"_id": usuario["_id"]}, {"$set": cambios})
    usuario.update(cambios)
    auditoria.registrar("login", request, usuario, detalle=metodo)
    cerradas = _emitir_sesion(response, usuario, request)
    return {"usuario": usuario_publico(usuario), "sesiones_cerradas": cerradas}


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


def revocar_sesiones_usuario(usuario_id, motivo="revocada"):
    revocar_sesiones({"usuario_id": usuario_id}, motivo)


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
        "roles": [permisos.ROL_USUARIO],
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
        raise HTTPException(status_code=423, detail=MENSAJE_BLOQUEO)

    valida, necesita_rehash = verificar_password(datos.password, usuario.get("password_hash"))
    if not valida:
        if _registrar_fallo(usuario, request, "contraseña incorrecta"):
            raise HTTPException(status_code=423, detail=MENSAJE_BLOQUEO)
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
        raise HTTPException(status_code=423, detail=MENSAJE_BLOQUEO)

    ok, metodo = _verificar_segundo_factor(usuario, datos.codigo)
    if not ok:
        if _registrar_fallo(usuario, request, "código de verificación incorrecto"):
            raise HTTPException(status_code=423, detail=MENSAJE_BLOQUEO)
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
        _sesion_terminada("cerrada")

    usuario = db.usuarios.find_one({"_id": sesion["usuario_id"]})

    if sesion.get("revocado_en") is not None:
        if sesion.get("motivo_cierre") == "rotada":
            if a_utc(sesion["revocado_en"]) > ahora() - timedelta(seconds=SEGUNDOS_GRACIA_ROTACION):
                # Otra pestaña del mismo navegador renovó la sesión hace un momento:
                # el navegador ya tiene la cookie nueva. No es un robo.
                _reintentar()
            # Un refresh token ya rotado se volvió a presentar: posible robo.
            # Se cierran todas las sesiones derivadas de él.
            revocar_sesiones({"familia": sesion["familia"]}, "robo")
            auditoria.registrar("refresh_reutilizado", request, usuario, detalle="se revocó la familia de sesiones", exito=False)
            _sesion_terminada("cerrada")
        _sesion_terminada(motivo_sesion_vencida(sesion))

    motivo = motivo_sesion_vencida(sesion)
    if motivo:
        cerrar_sesion_vencida(sesion, motivo, request)
        _sesion_terminada(motivo)

    if (
        usuario is None
        or not usuario.get("activo", False)
        or int(usuario.get("token_version", 0)) != int(sesion.get("token_version", -1))
    ):
        revocar_sesiones({"_id": sesion["_id"]}, "revocada")
        _sesion_terminada("cerrada")

    # Marcado atómico: si dos peticiones usan el mismo token a la vez, solo una gana.
    marcado = db.sesiones.update_one(
        {"_id": sesion["_id"], "revocado_en": None},
        {"$set": {"revocado_en": ahora(), "motivo_cierre": "rotada"}},
    )
    if marcado.modified_count != 1:
        # La otra petición ganó: NO se borran las cookies (borraría las nuevas).
        _reintentar()

    _emitir_sesion(response, usuario, request, familia=sesion["familia"], inicio=a_utc(sesion.get("inicio") or sesion["creado_en"]))
    return {"usuario": usuario_publico(usuario)}


SEGUNDOS_GRACIA_ROTACION = 30


def _reintentar():
    raise HTTPException(
        status_code=409,
        detail="La sesión se acaba de renovar en otra pestaña.",
        headers={"X-Coraleum-Accion": "reintentar"},
    )


def _sesion_terminada(motivo):
    """Responde 401 con el motivo y borra las cookies de sesión del navegador."""
    raise ErrorSesion(motivo)


def _sesion_del_refresh(request):
    token = request.cookies.get(config.COOKIE_REFRESH)
    if not token:
        return None
    return db.sesiones.find_one({"token_hash": hash_token(token)})


def _estado(sesion):
    conf = sesion_config.obtener()
    motivo = motivo_sesion_vencida(sesion, conf)
    if motivo:
        return {"activa": False, "motivo": motivo, "mensaje": MENSAJES_VENCIMIENTO[motivo]}, motivo
    momento = ahora()
    por_inactividad = a_utc(sesion["ultima_actividad"]) + timedelta(minutes=conf["inactividad_minutos"]) - momento
    por_duracion = a_utc(sesion.get("inicio") or sesion["creado_en"]) + timedelta(hours=conf["maxima_horas"]) - momento
    return {
        "activa": True,
        "segundos_restantes_inactividad": int(por_inactividad.total_seconds()),
        "segundos_restantes_sesion": int(por_duracion.total_seconds()),
        "inactividad_segundos": conf["inactividad_minutos"] * 60,
    }, None


@router.get("/estado")
def estado_sesion(request: Request):
    """Estado de la sesión SIN contarlo como actividad (la interfaz lo consulta
    periódicamente para cerrar la sesión en pantalla cuando vence)."""
    sesion = _sesion_del_refresh(request)
    if sesion is None:
        return {"activa": False, "motivo": "cerrada", "mensaje": MENSAJES_VENCIMIENTO["cerrada"]}
    resultado, motivo = _estado(sesion)
    if motivo in ("inactividad", "duracion"):
        cerrar_sesion_vencida(sesion, motivo, request)
    return resultado


@router.post("/actividad")
def actividad(request: Request):
    """La interfaz informa que la persona está usando la aplicación."""
    sesion = _sesion_del_refresh(request)
    if sesion is None:
        return {"activa": False, "motivo": "cerrada", "mensaje": MENSAJES_VENCIMIENTO["cerrada"]}
    resultado, motivo = _estado(sesion)
    if motivo:
        if motivo != "cerrada":
            cerrar_sesion_vencida(sesion, motivo, request)
        return resultado
    db.sesiones.update_one({"_id": sesion["_id"]}, {"$set": {"ultima_actividad": ahora()}})
    sesion["ultima_actividad"] = ahora()
    return _estado(sesion)[0]


@router.post("/olvide-password")
def olvide_password(datos: OlvidePassword, request: Request):
    """Solicitud de restablecimiento de contraseña.

    Siempre responde lo mismo, exista o no el correo (no revela qué cuentas
    existen). Si la cuenta existe, la solicitud aparece en el panel de
    administración, donde se genera una contraseña temporal.
    """
    ip = auditoria.ip_cliente(request)
    verificar_limite(f"olvide:{ip}", maximo=5, ventana_segundos=3600)
    email = datos.email.lower()
    usuario = db.usuarios.find_one({"email": email, "activo": True})
    if usuario is not None:
        db.usuarios.update_one(
            {"_id": usuario["_id"]},
            {"$set": {"recuperacion_solicitada": {"fecha": ahora(), "ip": ip}}},
        )
        auditoria.registrar("recuperacion_solicitada", request, usuario)
    else:
        verificar_tiempo_constante(email)
        auditoria.registrar("recuperacion_solicitada", request, email=email, detalle="correo no registrado", exito=False)
    return {
        "mensaje": (
            "Si el correo está registrado, un administrador recibirá la solicitud y te entregará "
            "una contraseña temporal por un canal seguro. Deberás cambiarla al iniciar sesión."
        )
    }


@router.post("/logout")
def logout(request: Request, response: Response, usuario=Depends(usuario_opcional)):
    token = request.cookies.get(config.COOKIE_REFRESH)
    if token:
        revocar_sesiones({"token_hash": hash_token(token)}, "logout")
    if usuario:
        revocar_sesiones({"_id": usuario["_sesion_id"]}, "logout")
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
    revocar_sesiones_usuario(usuario["_id"], "credenciales")
    usuario.update({"token_version": nueva_version, "debe_cambiar_password": False})
    auditoria.registrar("cambio_password", request, usuario)
    _emitir_sesion(response, usuario, request)
    return {"usuario": usuario_publico(usuario)}


@router.post("/solicitar-investigador")
def solicitar_investigador(datos: SolicitudInvestigador, request: Request, usuario=Depends(requerir_sesion)):
    if "datos.consultar" in permisos.permisos_de(usuario):
        raise HTTPException(status_code=400, detail="Su cuenta ya tiene acceso a la información de investigación.")
    solicitud_actual = usuario.get("solicitud") or {}
    if solicitud_actual.get("estado") == "pendiente":
        raise HTTPException(status_code=409, detail="Ya tiene una solicitud pendiente de revisión.")

    soporte = None
    if datos.soporte_id:
        documento = db.documentos.find_one({"_id": ObjectId(datos.soporte_id), "usuario_id": usuario["_id"]})
        if documento is None:
            raise HTTPException(status_code=400, detail="El documento de soporte no existe. Cárguelo de nuevo.")
        soporte = {
            "id": str(documento["_id"]),
            "nombre": documento.get("nombre_original"),
            "tamano": documento.get("tamano"),
            "sha256": documento.get("sha256"),
        }

    solicitud = {
        "estado": "pendiente",
        "institucion": datos.institucion,
        "motivo": datos.motivo,
        "fecha": ahora(),
        "comentario_admin": None,
        "soporte": soporte,
    }
    db.usuarios.update_one({"_id": usuario["_id"]}, {"$set": {"solicitud": solicitud}})
    if soporte:
        db.documentos.update_one({"_id": ObjectId(soporte["id"])}, {"$set": {"asociado": True}})
        # Los documentos que no quedaron en la solicitud se eliminan.
        db.documentos.delete_many({"usuario_id": usuario["_id"], "_id": {"$ne": ObjectId(soporte["id"])}})
    usuario["solicitud"] = solicitud
    auditoria.registrar(
        "solicitud_investigador",
        request,
        usuario,
        detalle={"institucion": datos.institucion, "soporte": soporte["nombre"] if soporte else "sin documento"},
    )
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
    if config.EXIGIR_2FA_ADMIN and permisos.tiene_permisos_administrativos(permisos.permisos_de(usuario)):
        raise HTTPException(status_code=400, detail="Las cuentas con permisos de administración deben mantener activa la verificación en dos pasos.")
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
    if permisos.es_admin(usuario) and permisos.admins_activos(excluir_id=usuario["_id"]) == 0:
        raise HTTPException(status_code=400, detail="Es el único administrador activo. Asigne otro administrador antes de eliminar su cuenta.")

    db.sesiones.delete_many({"usuario_id": usuario["_id"]})
    db.documentos.delete_many({"usuario_id": usuario["_id"]})
    db.auditoria_accesos.update_many(
        {"usuario_id": usuario["_id"]},
        {"$set": {"email": None, "ip": None, "user_agent": None, "usuario_id": None, "anonimizado": True}},
    )
    db.usuarios.delete_one({"_id": usuario["_id"]})
    auditoria.registrar("cuenta_eliminada", None, detalle="supresión solicitada por el titular")
    borrar_cookies_sesion(response)
    return {"ok": True}


# ------------------------------------------------------------
# Sesiones abiertas (varios navegadores o dispositivos)
# ------------------------------------------------------------

@router.get("/sesiones")
def mis_sesiones(usuario=Depends(requerir_sesion)):
    """Sesiones abiertas de la cuenta, para ver dónde está iniciada."""
    conf = sesion_config.obtener()
    lista = []
    for sesion in db.sesiones.find({"usuario_id": usuario["_id"], "revocado_en": None}):
        if motivo_sesion_vencida(sesion, conf):
            continue
        lista.append(
            {
                "id": sesion["familia"],
                "navegador": describir_navegador(sesion.get("user_agent")),
                "ip": sesion.get("ip"),
                "inicio": _iso(sesion.get("inicio") or sesion.get("creado_en")),
                "ultima_actividad": _iso(sesion.get("ultima_actividad")),
                "actual": sesion.get("familia") == usuario.get("_familia"),
            }
        )
    lista.sort(key=lambda s: (not s["actual"], s["ultima_actividad"] or ""), reverse=False)
    return {"sesiones": lista, "limite": conf["sesiones_simultaneas"]}


@router.post("/sesiones/cerrar-otras")
def cerrar_otras_sesiones(request: Request, usuario=Depends(requerir_sesion)):
    cerradas = revocar_sesiones({"usuario_id": usuario["_id"], "familia": {"$ne": usuario.get("_familia")}}, "remota")
    auditoria.registrar("sesiones_cerradas", request, usuario, detalle={"cerradas": cerradas})
    return {"cerradas": cerradas}


@router.post("/sesiones/{familia}/cerrar")
def cerrar_sesion_remota(
    request: Request,
    familia: str = Path(pattern=r"^[0-9a-f]{32}$"),
    usuario=Depends(requerir_sesion),
):
    if familia == usuario.get("_familia"):
        raise HTTPException(status_code=400, detail="Esta es la sesión actual: use «Cerrar sesión».")
    cerradas = revocar_sesiones({"usuario_id": usuario["_id"], "familia": familia}, "remota")
    if not cerradas:
        raise HTTPException(status_code=404, detail="La sesión ya no está abierta.")
    auditoria.registrar("sesiones_cerradas", request, usuario, detalle={"cerradas": cerradas})
    return {"cerradas": cerradas}


# ------------------------------------------------------------
# Cambio de correo desde el perfil
# ------------------------------------------------------------

@router.post("/cambiar-email")
def cambiar_email(datos: CambioEmail, request: Request, response: Response, usuario=Depends(requerir_sesion)):
    """Cambia el correo de la cuenta.

    Exige la contraseña actual (y el código de verificación en dos pasos si
    está activa): quien encuentre una sesión abierta no puede apropiarse de
    la cuenta cambiando el correo. Las demás sesiones se cierran.
    """
    verificar_limite(f"cambio-email:{usuario['_id']}", maximo=5, ventana_segundos=900)
    anterior = usuario.get("email")
    nuevo = datos.email_nuevo.lower()

    valida, _ = verificar_password(datos.password, usuario.get("password_hash"))
    if not valida:
        auditoria.registrar("cambio_email", request, usuario, detalle="contraseña incorrecta", exito=False)
        raise HTTPException(status_code=400, detail="La contraseña no es correcta.")
    if (usuario.get("dos_pasos") or {}).get("activo"):
        ok, _ = _verificar_segundo_factor(usuario, datos.codigo) if datos.codigo else (False, None)
        if not ok:
            auditoria.registrar("cambio_email", request, usuario, detalle="código de verificación incorrecto", exito=False)
            raise HTTPException(status_code=400, detail="Ingrese un código válido de su aplicación de autenticación.")
    if nuevo == anterior:
        raise HTTPException(status_code=400, detail="El correo nuevo es igual al actual.")
    if db.usuarios.count_documents({"email": nuevo}):
        auditoria.registrar("cambio_email", request, usuario, detalle="el correo nuevo ya pertenece a otra cuenta", exito=False)
        raise HTTPException(status_code=409, detail="No es posible usar ese correo. Verifique que no esté registrado en otra cuenta.")

    nueva_version = int(usuario.get("token_version", 0)) + 1
    try:
        db.usuarios.update_one({"_id": usuario["_id"]}, {"$set": {"email": nuevo, "token_version": nueva_version}})
    except DuplicateKeyError:
        raise HTTPException(status_code=409, detail="No es posible usar ese correo. Verifique que no esté registrado en otra cuenta.")
    revocar_sesiones_usuario(usuario["_id"], "credenciales")
    usuario.update({"email": nuevo, "token_version": nueva_version})
    auditoria.registrar(
        "cambio_email",
        request,
        usuario,
        detalle={"anterior": cifrado.enmascarar_email(anterior), "nuevo": cifrado.enmascarar_email(nuevo)},
    )
    _emitir_sesion(response, usuario, request)
    return {"usuario": usuario_publico(usuario)}


# ------------------------------------------------------------
# Carga de archivos: soporte de la solicitud de investigador (PDF)
# ------------------------------------------------------------

@router.post("/solicitud/soporte", status_code=201)
async def cargar_soporte(request: Request, usuario=Depends(requerir_sesion)):
    """Recibe un PDF como cuerpo de la petición (Content-Type: application/pdf).

    El archivo se valida por su CONTENIDO, no solo por la extensión: un .exe
    renombrado a .pdf se rechaza. Ver api/archivos.py.
    """
    await run_in_threadpool(verificar_limite, f"carga:{usuario['_id']}", 10, 3600)
    nombre = archivos.nombre_seguro(request.headers.get(archivos.ENCABEZADO_NOMBRE, ""))
    tipo = (request.headers.get("content-type") or "").split(";")[0].strip().lower()

    declarado = request.headers.get("content-length")
    if declarado and declarado.isdigit() and int(declarado) > archivos.TAMANO_MAXIMO:
        contenido = None
    else:
        contenido = await archivos.leer_cuerpo(request)

    return await run_in_threadpool(_guardar_soporte, request, usuario, nombre, tipo, contenido)


def _guardar_soporte(request, usuario, nombre, tipo, contenido):
    error = archivos.validar_pdf(contenido, nombre, tipo)
    if error:
        auditoria.registrar("archivo_rechazado", request, usuario, detalle={"archivo": nombre, **error["auditoria"]}, exito=False)
        raise HTTPException(status_code=error["estado"], detail=error["mensaje"])

    # Solo se conserva un documento sin enviar por persona.
    db.documentos.delete_many({"usuario_id": usuario["_id"], "asociado": False})
    huella = archivos.sha256(contenido)
    documento = {
        "usuario_id": usuario["_id"],
        "nombre_original": nombre,
        "tipo": "application/pdf",
        "tamano": len(contenido),
        "sha256": huella,
        # El contenido también se guarda cifrado.
        "contenido": cifrado.cifrar_bytes(contenido),
        "asociado": False,
        "fecha": ahora(),
    }
    db.documentos.insert_one(documento)
    auditoria.registrar("archivo_cargado", request, usuario, detalle={"archivo": nombre, "tamano": len(contenido), "sha256": huella[:16]})
    return {"soporte": {"id": str(documento["_id"]), "nombre": nombre, "tamano": len(contenido), "sha256": huella}}
