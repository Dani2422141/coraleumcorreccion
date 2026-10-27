"""Dependencias de FastAPI: sesión, permisos y protección CSRF.

La autorización se decide SIEMPRE en el backend: en cada petición se lee
de la base de datos el usuario, sus roles y el estado de su sesión. Si un
administrador cambia un rol, desactiva una cuenta o reduce el tiempo de
inactividad, el cambio se aplica de inmediato.
"""

from datetime import timedelta

from bson import ObjectId
from bson.errors import InvalidId
from fastapi import Depends, HTTPException, Request

from api import auditoria, config, db, permisos, sesion_config
from api.seguridad import a_utc, ahora, decodificar_access_token

METODOS_SEGUROS = {"GET", "HEAD", "OPTIONS"}

# La última actividad se guarda como máximo cada 5 s (evita escrituras de más).
_SEGUNDOS_ENTRE_REGISTROS_DE_ACTIVIDAD = 5


def proteger_csrf(request: Request):
    """Las peticiones que modifican datos deben venir de la propia aplicación.

    1. Deben incluir el encabezado X-Requested-With: Coraleum (un formulario
       de otro sitio no puede enviarlo sin pasar por CORS).
    2. Si el navegador envía Origin, debe ser uno de los orígenes permitidos.
    Junto con las cookies SameSite=Strict, esto bloquea ataques CSRF.
    """
    if request.method in METODOS_SEGUROS:
        return
    if request.headers.get(config.CSRF_HEADER) != config.CSRF_VALOR:
        raise HTTPException(status_code=403, detail="Solicitud no permitida.")
    origen = request.headers.get("origin")
    if origen and origen.rstrip("/") not in config.ORIGENES_PERMITIDOS:
        raise HTTPException(status_code=403, detail="Origen no permitido.")


# ------------------------------------------------------------
# Sesiones del servidor
# ------------------------------------------------------------

# Motivos de cierre que se explican a la persona. Los demás ("rotada",
# "revocada", "robo"…) se muestran como "Sesión no válida".
MENSAJES_VENCIMIENTO = {
    "inactividad": "Tu sesión se cerró por inactividad. Inicia sesión de nuevo.",
    "duracion": "Tu sesión alcanzó su duración máxima. Inicia sesión de nuevo.",
    "reemplazada": (
        "Tu sesión se cerró porque se inició sesión con tu cuenta en otro navegador o dispositivo. "
        "Si no fuiste tú, cambia tu contraseña."
    ),
    "remota": "Esta sesión se cerró desde otro navegador o dispositivo.",
    "logout": "Cerraste sesión en otra pestaña o ventana.",
    "credenciales": "Tu contraseña o tu correo cambiaron. Inicia sesión de nuevo con los datos nuevos.",
    "cerrada": "Sesión no válida. Inicia sesión de nuevo.",
}


class ErrorSesion(HTTPException):
    """401 que además borra las cookies de sesión (ver manejador en main.py)."""

    borrar_cookies = True

    def __init__(self, motivo):
        motivo = motivo if motivo in MENSAJES_VENCIMIENTO else "cerrada"
        super().__init__(
            status_code=401,
            detail=MENSAJES_VENCIMIENTO[motivo],
            headers={"X-Coraleum-Accion": f"sesion-{motivo}"},
        )


def revocar_sesiones(filtro, motivo):
    """Cierra en el servidor las sesiones que cumplan el filtro, dejando el motivo."""
    filtro = {**filtro, "revocado_en": None}
    return db.sesiones.update_many(filtro, {"$set": {"revocado_en": ahora(), "motivo_cierre": motivo}}).modified_count


def motivo_sesion_vencida(sesion, conf=None):
    """None si la sesión sigue activa; si no, la clave del motivo en MENSAJES_VENCIMIENTO."""
    if sesion is None:
        return "cerrada"
    if sesion.get("revocado_en") is not None:
        motivo = sesion.get("motivo_cierre")
        return motivo if motivo in MENSAJES_VENCIMIENTO else "cerrada"
    conf = conf or sesion_config.obtener()
    momento = ahora()
    inicio = a_utc(sesion.get("inicio") or sesion.get("creado_en"))
    if inicio + timedelta(hours=conf["maxima_horas"]) <= momento:
        return "duracion"
    ultima = a_utc(sesion.get("ultima_actividad") or sesion.get("creado_en"))
    if ultima + timedelta(minutes=conf["inactividad_minutos"]) <= momento:
        return "inactividad"
    return None


def cerrar_sesion_vencida(sesion, motivo, request=None):
    """Marca la sesión como cerrada y deja constancia en la auditoría (una vez)."""
    if motivo not in ("inactividad", "duracion"):
        return
    resultado = db.sesiones.update_one(
        {"_id": sesion["_id"], "revocado_en": None},
        {"$set": {"revocado_en": ahora(), "motivo_cierre": motivo}},
    )
    if resultado.modified_count:
        usuario = db.usuarios.find_one({"_id": sesion["usuario_id"]}, {"email": 1})
        auditoria.registrar(
            "sesion_expirada",
            request,
            usuario,
            detalle="por inactividad" if motivo == "inactividad" else "duración máxima alcanzada",
        )


def registrar_actividad(sesion):
    momento = ahora()
    ultima = a_utc(sesion.get("ultima_actividad") or sesion.get("creado_en"))
    if (momento - ultima).total_seconds() >= _SEGUNDOS_ENTRE_REGISTROS_DE_ACTIVIDAD:
        db.sesiones.update_one({"_id": sesion["_id"]}, {"$set": {"ultima_actividad": momento}})


def _cargar_usuario(request: Request, registrar=True):
    token = request.cookies.get(config.COOKIE_ACCESS)
    if not token:
        return None
    carga = decodificar_access_token(token)
    if not carga:
        return None
    try:
        usuario_id = ObjectId(carga["sub"])
        sid = ObjectId(carga.get("sid"))
    except (InvalidId, TypeError):
        return None

    sesion = db.sesiones.find_one({"_id": sid, "usuario_id": usuario_id})
    motivo = motivo_sesion_vencida(sesion)
    if motivo:
        if sesion is not None:
            cerrar_sesion_vencida(sesion, motivo, request)
        return None

    usuario = db.usuarios.find_one({"_id": usuario_id})
    if not usuario or not usuario.get("activo", False):
        return None
    # token_version cambia al cerrar todas las sesiones (cambio de contraseña,
    # desactivación, restablecimiento): invalida tokens emitidos antes.
    if int(usuario.get("token_version", 0)) != int(carga.get("ver", -1)):
        return None

    if registrar:
        registrar_actividad(sesion)
    usuario["_sesion_id"] = sid
    usuario["_familia"] = sesion.get("familia")
    return usuario


def usuario_opcional(request: Request):
    """Usuario autenticado o None (visitante)."""
    return _cargar_usuario(request)


def requerir_sesion(request: Request):
    usuario = _cargar_usuario(request)
    if usuario is None:
        raise HTTPException(status_code=401, detail="Debe iniciar sesión.")
    if usuario.get("debe_cambiar_password"):
        raise HTTPException(
            status_code=403,
            detail="Debe cambiar su contraseña temporal antes de continuar.",
            headers={"X-Coraleum-Accion": "cambiar-password"},
        )
    return usuario


def requerir_sesion_permitiendo_cambio(request: Request):
    """Como requerir_sesion, pero admite cuentas con contraseña temporal."""
    usuario = _cargar_usuario(request)
    if usuario is None:
        raise HTTPException(status_code=401, detail="Debe iniciar sesión.")
    return usuario


# ------------------------------------------------------------
# Permisos
# ------------------------------------------------------------

def _denegar(request, usuario, requeridos, propios):
    auditoria.registrar(
        "acceso_denegado",
        request,
        usuario,
        detalle={"ruta": request.url.path, "requiere": " o ".join(requeridos)},
        exito=False,
    )
    if set(requeridos) <= permisos.PERMISOS_DATOS and not (propios & permisos.PERMISOS_DATOS):
        mensaje = "Esta sección requiere una cuenta de investigador aprobada."
    elif "datos.historico" in requeridos:
        mensaje = "Su rol no incluye acceso al registro histórico."
    else:
        mensaje = "No tiene permisos para esta acción."
    raise HTTPException(status_code=403, detail=mensaje)


def requerir_permiso(*requeridos):
    """Exige al menos uno de los permisos indicados."""

    def dependencia(request: Request, usuario=Depends(requerir_sesion)):
        propios = permisos.permisos_de(usuario)
        if not propios & set(requeridos):
            _denegar(request, usuario, requeridos, propios)
        usuario["_permisos"] = propios
        return usuario

    return dependencia


def requerir_permiso_admin(*requeridos):
    """Permiso administrativo + verificación en dos pasos activa."""

    def dependencia(request: Request, usuario=Depends(requerir_permiso(*requeridos))):
        if config.EXIGIR_2FA_ADMIN and not (usuario.get("dos_pasos") or {}).get("activo"):
            raise HTTPException(
                status_code=403,
                detail="Por seguridad, las cuentas con permisos de administración deben activar la verificación en dos pasos.",
                headers={"X-Coraleum-Accion": "configurar-2fa"},
            )
        return usuario

    return dependencia


# ------------------------------------------------------------
# Representación pública
# ------------------------------------------------------------

def usuario_publico(usuario, roles_por_clave=None):
    """Representación segura de un usuario (sin hash ni datos internos)."""
    roles_por_clave = roles_por_clave if roles_por_clave is not None else permisos.mapa_roles()
    claves = permisos.claves_de(usuario)
    propios = permisos.permisos_de(usuario, roles_por_clave)
    solicitud = usuario.get("solicitud") or None
    if solicitud:
        solicitud = {
            "estado": solicitud.get("estado"),
            "institucion": solicitud.get("institucion"),
            "motivo": solicitud.get("motivo"),
            "fecha": _iso(solicitud.get("fecha")),
            "comentario_admin": solicitud.get("comentario_admin"),
            "soporte": solicitud.get("soporte"),
        }
    recuperacion = usuario.get("recuperacion_solicitada") or None
    dos = usuario.get("dos_pasos") or {}
    return {
        "id": str(usuario["_id"]),
        "nombre": usuario.get("nombre"),
        "email": usuario.get("email"),
        "rol": permisos.rol_principal(claves),
        "roles": [
            {"clave": c, "nombre": roles_por_clave.get(c, {}).get("nombre", c)}
            for c in claves
            if c in roles_por_clave
        ],
        "permisos": sorted(propios),
        "activo": bool(usuario.get("activo", False)),
        "debe_cambiar_password": bool(usuario.get("debe_cambiar_password", False)),
        "solicitud": solicitud,
        "recuperacion_solicitada": _iso(recuperacion.get("fecha")) if recuperacion else None,
        "creado_en": _iso(usuario.get("creado_en")),
        "ultimo_acceso": _iso(usuario.get("ultimo_acceso")),
        "dos_pasos": bool(dos.get("activo")),
        "codigos_recuperacion_restantes": len(dos.get("recuperacion") or []) if dos.get("activo") else None,
        "politica_version": (usuario.get("consentimiento") or {}).get("version"),
        # True si la persona no ha aceptado la versión vigente de la política.
        "politica_pendiente": (usuario.get("consentimiento") or {}).get("version") != config.POLITICA_VERSION,
    }


def _iso(fecha):
    if fecha is None:
        return None
    return fecha.strftime("%Y-%m-%dT%H:%M:%SZ")
