"""Rutas de administración: usuarios, solicitudes, contraseñas y auditoría.

Todas exigen el rol "admin".
"""

import re
from typing import Literal

from bson import ObjectId
from bson.errors import InvalidId
from fastapi import APIRouter, Depends, HTTPException, Query, Request
from pydantic import BaseModel, Field

from api import auditoria, config, db
from api.deps import proteger_csrf, requerir_roles, usuario_publico
from api.rutas_auth import revocar_sesiones_usuario
from api.seguridad import ahora, generar_password_temporal, hash_password

solo_admin = requerir_roles(config.ROL_ADMIN)

router = APIRouter(
    prefix="/admin",
    tags=["administración"],
    dependencies=[Depends(proteger_csrf), Depends(solo_admin)],
)


class CambioUsuario(BaseModel):
    model_config = {"extra": "forbid"}
    rol: Literal["usuario", "investigador", "admin"] | None = None
    activo: bool | None = None


class DecisionSolicitud(BaseModel):
    model_config = {"extra": "forbid", "str_strip_whitespace": True}
    decision: Literal["aprobar", "rechazar"]
    comentario: str | None = Field(default=None, max_length=300)


def _obtener_usuario(usuario_id):
    try:
        oid = ObjectId(usuario_id)
    except (InvalidId, TypeError):
        raise HTTPException(status_code=404, detail="Usuario no encontrado.")
    usuario = db.usuarios.find_one({"_id": oid})
    if usuario is None:
        raise HTTPException(status_code=404, detail="Usuario no encontrado.")
    return usuario


def _admins_activos():
    return db.usuarios.count_documents({"rol": config.ROL_ADMIN, "activo": True})


@router.get("/usuarios")
def listar_usuarios(
    q: str | None = Query(default=None, max_length=100),
    rol: Literal["usuario", "investigador", "admin"] | None = None,
    solicitud: Literal["pendiente", "aprobada", "rechazada"] | None = None,
):
    filtro = {}
    if q:
        # re.escape evita inyección de expresiones regulares.
        patron = {"$regex": re.escape(q.strip()), "$options": "i"}
        filtro["$or"] = [{"email": patron}, {"nombre": patron}]
    if rol:
        filtro["rol"] = rol
    if solicitud:
        filtro["solicitud.estado"] = solicitud
    usuarios = db.usuarios.find(filtro).sort("creado_en", -1).limit(500)
    lista = [usuario_publico(u) for u in usuarios]
    return {
        "total": len(lista),
        "pendientes": db.usuarios.count_documents({"solicitud.estado": "pendiente"}),
        "usuarios": lista,
    }


@router.patch("/usuarios/{usuario_id}")
def actualizar_usuario(usuario_id: str, cambios: CambioUsuario, request: Request, admin=Depends(solo_admin)):
    usuario = _obtener_usuario(usuario_id)
    es_el_mismo = usuario["_id"] == admin["_id"]
    actualizacion = {}

    if cambios.rol is not None and cambios.rol != usuario.get("rol"):
        if es_el_mismo:
            raise HTTPException(status_code=400, detail="No puede cambiar su propio rol.")
        if usuario.get("rol") == config.ROL_ADMIN and _admins_activos() <= 1:
            raise HTTPException(status_code=400, detail="Debe existir al menos un administrador activo.")
        actualizacion["rol"] = cambios.rol
        solicitud = usuario.get("solicitud") or {}
        if cambios.rol in config.ROLES_DATOS and solicitud.get("estado") == "pendiente":
            actualizacion["solicitud.estado"] = "aprobada"

    if cambios.activo is not None and cambios.activo != usuario.get("activo"):
        if es_el_mismo:
            raise HTTPException(status_code=400, detail="No puede desactivar su propia cuenta.")
        if not cambios.activo and usuario.get("rol") == config.ROL_ADMIN and _admins_activos() <= 1:
            raise HTTPException(status_code=400, detail="Debe existir al menos un administrador activo.")
        actualizacion["activo"] = cambios.activo
        if not cambios.activo:
            # Expulsa de inmediato todas sus sesiones.
            actualizacion["token_version"] = int(usuario.get("token_version", 0)) + 1
        else:
            actualizacion["intentos_fallidos"] = 0
            actualizacion["bloqueado_hasta"] = None

    if not actualizacion:
        return {"usuario": usuario_publico(usuario)}

    db.usuarios.update_one({"_id": usuario["_id"]}, {"$set": actualizacion})
    if actualizacion.get("activo") is False:
        revocar_sesiones_usuario(usuario["_id"])

    actualizado = db.usuarios.find_one({"_id": usuario["_id"]})
    auditoria.registrar(
        "usuario_actualizado",
        request,
        admin,
        detalle={
            "usuario": usuario.get("email"),
            "rol": [usuario.get("rol"), actualizado.get("rol")],
            "activo": [usuario.get("activo"), actualizado.get("activo")],
        },
    )
    return {"usuario": usuario_publico(actualizado)}


@router.post("/usuarios/{usuario_id}/solicitud")
def decidir_solicitud(usuario_id: str, datos: DecisionSolicitud, request: Request, admin=Depends(solo_admin)):
    usuario = _obtener_usuario(usuario_id)
    solicitud = usuario.get("solicitud") or {}
    if solicitud.get("estado") != "pendiente":
        raise HTTPException(status_code=400, detail="El usuario no tiene una solicitud pendiente.")

    actualizacion = {
        "solicitud.estado": "aprobada" if datos.decision == "aprobar" else "rechazada",
        "solicitud.comentario_admin": datos.comentario,
        "solicitud.revisada_por": admin["_id"],
        "solicitud.revisada_en": ahora(),
    }
    if datos.decision == "aprobar" and usuario.get("rol") == config.ROL_USUARIO:
        actualizacion["rol"] = config.ROL_INVESTIGADOR

    db.usuarios.update_one({"_id": usuario["_id"]}, {"$set": actualizacion})
    auditoria.registrar(
        "solicitud_" + ("aprobada" if datos.decision == "aprobar" else "rechazada"),
        request,
        admin,
        detalle={"usuario": usuario.get("email")},
    )
    return {"usuario": usuario_publico(db.usuarios.find_one({"_id": usuario["_id"]}))}


@router.post("/usuarios/{usuario_id}/restablecer-password")
def restablecer_password(usuario_id: str, request: Request, admin=Depends(solo_admin)):
    """Genera una contraseña temporal que se muestra UNA sola vez.

    El usuario deberá cambiarla en su próximo inicio de sesión. Todas sus
    sesiones abiertas se cierran.
    """
    usuario = _obtener_usuario(usuario_id)
    if usuario["_id"] == admin["_id"]:
        raise HTTPException(status_code=400, detail="Use 'Cambiar contraseña' en su cuenta para su propia contraseña.")

    temporal = generar_password_temporal()
    db.usuarios.update_one(
        {"_id": usuario["_id"]},
        {
            "$set": {
                "password_hash": hash_password(temporal),
                "debe_cambiar_password": True,
                "token_version": int(usuario.get("token_version", 0)) + 1,
                "intentos_fallidos": 0,
                "bloqueado_hasta": None,
            }
        },
    )
    revocar_sesiones_usuario(usuario["_id"])
    auditoria.registrar("password_restablecida", request, admin, detalle={"usuario": usuario.get("email")})
    return {"password_temporal": temporal, "usuario": usuario_publico(db.usuarios.find_one({"_id": usuario["_id"]}))}


@router.get("/auditoria")
def ver_auditoria(
    limite: int = Query(default=100, ge=1, le=500),
    evento: str | None = Query(default=None, max_length=50, pattern=r"^[a-z_]+$"),
    solo_fallidos: bool = False,
):
    filtro = {}
    if evento:
        filtro["evento"] = evento
    if solo_fallidos:
        filtro["exito"] = False
    eventos = db.auditoria_accesos.find(filtro, {"user_agent": 0}).sort("fecha", -1).limit(limite)
    return {
        "eventos": [
            {
                "fecha": e["fecha"].strftime("%Y-%m-%dT%H:%M:%SZ"),
                "evento": e.get("evento"),
                "exito": e.get("exito", True),
                "email": e.get("email"),
                "ip": e.get("ip"),
                "detalle": e.get("detalle"),
            }
            for e in eventos
        ]
    }


@router.get("/integridad")
def ver_integridad(limite: int = Query(default=20, ge=1, le=100)):
    """Últimos registros de verificación SHA-256 del histórico."""
    registros = db.auditoria_integridad.find({}, {"_id": 0}).sort("_id", -1).limit(limite)
    return {"registros": [{k: (v.isoformat() if hasattr(v, "isoformat") else v) for k, v in r.items()} for r in registros]}
