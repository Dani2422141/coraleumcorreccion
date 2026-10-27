"""Dependencias de FastAPI para sesión, roles y protección CSRF.

La autorización se decide SIEMPRE en el backend, con el rol leído de la
base de datos en cada petición: si el administrador cambia un rol o
desactiva una cuenta, el cambio se aplica de inmediato.
"""

from bson import ObjectId
from bson.errors import InvalidId
from fastapi import Depends, HTTPException, Request

from api import auditoria, config, db
from api.seguridad import decodificar_access_token

METODOS_SEGUROS = {"GET", "HEAD", "OPTIONS"}


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


def _cargar_usuario(request: Request):
    token = request.cookies.get(config.COOKIE_ACCESS)
    if not token:
        return None
    carga = decodificar_access_token(token)
    if not carga:
        return None
    try:
        usuario_id = ObjectId(carga["sub"])
    except (InvalidId, TypeError):
        return None
    usuario = db.usuarios.find_one({"_id": usuario_id})
    if not usuario or not usuario.get("activo", False):
        return None
    # token_version cambia al cerrar todas las sesiones (cambio de contraseña,
    # desactivación, restablecimiento): invalida tokens emitidos antes.
    if int(usuario.get("token_version", 0)) != int(carga.get("ver", -1)):
        return None
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


def requerir_roles(*roles):
    def dependencia(request: Request, usuario=Depends(requerir_sesion)):
        if usuario.get("rol") not in roles:
            auditoria.registrar(
                "acceso_denegado",
                request,
                usuario,
                detalle={"ruta": request.url.path, "rol": usuario.get("rol")},
                exito=False,
            )
            if usuario.get("rol") == config.ROL_USUARIO and config.ROL_INVESTIGADOR in roles:
                mensaje = "Esta sección requiere una cuenta de investigador aprobada."
            else:
                mensaje = "No tiene permisos para esta acción."
            raise HTTPException(status_code=403, detail=mensaje)
        return usuario

    return dependencia


def requerir_admin_con_2fa(request: Request, usuario=Depends(requerir_roles(config.ROL_ADMIN))):
    """Administrador que además tiene activa la verificación en dos pasos."""
    if config.EXIGIR_2FA_ADMIN and not (usuario.get("dos_pasos") or {}).get("activo"):
        raise HTTPException(
            status_code=403,
            detail="Por seguridad, los administradores deben activar la verificación en dos pasos.",
            headers={"X-Coraleum-Accion": "configurar-2fa"},
        )
    return usuario


def usuario_publico(usuario):
    """Representación segura de un usuario (sin hash ni datos internos)."""
    solicitud = usuario.get("solicitud") or None
    if solicitud:
        solicitud = {
            "estado": solicitud.get("estado"),
            "institucion": solicitud.get("institucion"),
            "motivo": solicitud.get("motivo"),
            "fecha": _iso(solicitud.get("fecha")),
            "comentario_admin": solicitud.get("comentario_admin"),
        }
    return {
        "id": str(usuario["_id"]),
        "nombre": usuario.get("nombre"),
        "email": usuario.get("email"),
        "rol": usuario.get("rol"),
        "activo": bool(usuario.get("activo", False)),
        "debe_cambiar_password": bool(usuario.get("debe_cambiar_password", False)),
        "solicitud": solicitud,
        "creado_en": _iso(usuario.get("creado_en")),
        "ultimo_acceso": _iso(usuario.get("ultimo_acceso")),
        "dos_pasos": bool((usuario.get("dos_pasos") or {}).get("activo")),
        "codigos_recuperacion_restantes": len((usuario.get("dos_pasos") or {}).get("recuperacion") or [])
        if (usuario.get("dos_pasos") or {}).get("activo") else None,
        "politica_version": (usuario.get("consentimiento") or {}).get("version"),
        # True si la persona no ha aceptado la versión vigente de la política.
        "politica_pendiente": (usuario.get("consentimiento") or {}).get("version") != config.POLITICA_VERSION,
    }


def _iso(fecha):
    if fecha is None:
        return None
    return fecha.strftime("%Y-%m-%dT%H:%M:%SZ")
