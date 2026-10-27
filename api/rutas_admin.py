"""Rutas de administración: usuarios, roles y permisos, solicitudes,
contraseñas, configuración de sesión y auditoría.

Cada ruta exige un permiso concreto y verificación en dos pasos activa.
"""

import re
from typing import Literal

from bson import ObjectId
from bson.errors import InvalidId
from fastapi import APIRouter, Depends, HTTPException, Query, Request, Response
from pydantic import BaseModel, Field, field_validator

from api import auditoria, cifrado, db, errores, permisos, sesion_config
from api.deps import proteger_csrf, requerir_permiso_admin, usuario_publico
from api.rutas_auth import revocar_sesiones_usuario
from api.seguridad import ahora, generar_password_temporal, hash_password, validar_politica_password

router = APIRouter(prefix="/admin", tags=["administración"], dependencies=[Depends(proteger_csrf)])

GESTIONAR_USUARIOS = requerir_permiso_admin("usuarios.gestionar")
VER_USUARIOS = requerir_permiso_admin("usuarios.gestionar", "solicitudes.aprobar")
APROBAR_SOLICITUDES = requerir_permiso_admin("solicitudes.aprobar")
GESTIONAR_ROLES = requerir_permiso_admin("roles.gestionar")
VER_ROLES = requerir_permiso_admin("roles.gestionar", "usuarios.gestionar")
VER_AUDITORIA = requerir_permiso_admin("auditoria.ver")
CONFIGURAR = requerir_permiso_admin("configuracion.gestionar")


# ------------------------------------------------------------
# Modelos de entrada
# ------------------------------------------------------------

class _Base(BaseModel):
    model_config = {"extra": "forbid", "str_strip_whitespace": True}


class CambioUsuario(_Base):
    roles: list[str] | None = Field(default=None, min_length=1, max_length=10)
    activo: bool | None = None


class DecisionSolicitud(_Base):
    decision: Literal["aprobar", "rechazar"]
    comentario: str | None = Field(default=None, max_length=300)


class NuevaPassword(_Base):
    password: str = Field(min_length=1, max_length=256)


class DatosRol(_Base):
    nombre: str = Field(min_length=2, max_length=60)
    descripcion: str | None = Field(default=None, max_length=200)
    permisos: list[str] = Field(default_factory=list, max_length=len(permisos.PERMISOS))

    @field_validator("nombre")
    @classmethod
    def nombre_valido(cls, valor):
        if any(c in valor for c in "<>{}$"):
            raise ValueError("El nombre contiene caracteres no permitidos.")
        return " ".join(valor.split())


class CambioRol(_Base):
    nombre: str | None = Field(default=None, min_length=2, max_length=60)
    descripcion: str | None = Field(default=None, max_length=200)
    permisos: list[str] | None = Field(default=None, max_length=len(permisos.PERMISOS))


class ConfiguracionSesion(_Base):
    token_minutos: int | None = None
    inactividad_minutos: int | None = None
    maxima_horas: int | None = None
    sesiones_simultaneas: int | None = None


# ------------------------------------------------------------
# Utilidades
# ------------------------------------------------------------

def _obtener_usuario(usuario_id):
    try:
        oid = ObjectId(usuario_id)
    except (InvalidId, TypeError):
        raise HTTPException(status_code=404, detail="Usuario no encontrado.")
    usuario = db.usuarios.find_one({"_id": oid})
    if usuario is None:
        raise HTTPException(status_code=404, detail="Usuario no encontrado.")
    return usuario


def _obtener_rol(clave):
    rol = db.roles.find_one({"clave": clave})
    if rol is None:
        raise HTTPException(status_code=404, detail="Rol no encontrado.")
    return rol


def _validar_permisos(lista, admin):
    """Permisos existentes y que el administrador mismo posee (anti-escalamiento)."""
    desconocidos = [p for p in lista if p not in permisos.PERMISOS]
    if desconocidos:
        raise HTTPException(status_code=400, detail=f"Permisos desconocidos: {', '.join(desconocidos)}.")
    ajenos = sorted(set(lista) - admin["_permisos"])
    if ajenos:
        raise HTTPException(
            status_code=403,
            detail=f"No puede conceder permisos que usted no tiene: {', '.join(ajenos)}.",
        )
    return sorted(set(lista))


def _rol_publico(rol, usuarios_por_rol=None):
    return {
        "clave": rol["clave"],
        "nombre": rol["nombre"],
        "descripcion": rol.get("descripcion"),
        "permisos": sorted(rol.get("permisos", [])),
        "sistema": bool(rol.get("sistema")),
        "editable": rol["clave"] != permisos.ROL_ADMIN,
        "usuarios": (usuarios_por_rol or {}).get(rol["clave"], 0),
    }


def _forzar_nueva_password(usuario, password, request, admin, evento, detalle_extra=None):
    """Asigna una contraseña que la persona deberá cambiar al entrar."""
    db.usuarios.update_one(
        {"_id": usuario["_id"]},
        {
            "$set": {
                "password_hash": hash_password(password),
                "debe_cambiar_password": True,
                "token_version": int(usuario.get("token_version", 0)) + 1,
                "intentos_fallidos": 0,
                "bloqueado_hasta": None,
            },
            "$unset": {"recuperacion_solicitada": ""},
        },
    )
    revocar_sesiones_usuario(usuario["_id"])
    auditoria.registrar(evento, request, admin, detalle={"usuario": usuario.get("email"), **(detalle_extra or {})})


# ------------------------------------------------------------
# Catálogo
# ------------------------------------------------------------

@router.get("/permisos")
def catalogo_permisos(admin=Depends(VER_ROLES)):
    return {"permisos": [{"clave": k, "descripcion": v} for k, v in permisos.PERMISOS.items()]}


# ------------------------------------------------------------
# Usuarios
# ------------------------------------------------------------

@router.get("/usuarios")
def listar_usuarios(
    q: str | None = Query(default=None, max_length=100),
    solicitud: Literal["pendiente", "aprobada", "rechazada"] | None = None,
    admin=Depends(VER_USUARIOS),
):
    filtro = {}
    if solicitud:
        filtro["solicitud.estado"] = solicitud
    roles_por_clave = permisos.mapa_roles()
    usuarios = db.usuarios.find(filtro).sort("creado_en", -1).limit(2000)
    lista = [usuario_publico(u, roles_por_clave) for u in usuarios]
    if q:
        # El correo y el nombre están cifrados en la base de datos: la búsqueda
        # se hace sobre los datos ya descifrados (texto literal, sin regex).
        termino = q.strip().lower()
        lista = [u for u in lista if termino in (u["email"] or "").lower() or termino in (u["nombre"] or "").lower()]
    lista = lista[:500]
    return {
        "total": len(lista),
        "pendientes": db.usuarios.count_documents({"solicitud.estado": "pendiente"}),
        "recuperaciones": db.usuarios.count_documents({"recuperacion_solicitada": {"$exists": True}}),
        "usuarios": lista,
    }


@router.patch("/usuarios/{usuario_id}")
def actualizar_usuario(usuario_id: str, cambios: CambioUsuario, request: Request, admin=Depends(GESTIONAR_USUARIOS)):
    usuario = _obtener_usuario(usuario_id)
    es_el_mismo = usuario["_id"] == admin["_id"]
    actualizacion = {}
    roles_por_clave = permisos.mapa_roles()
    antes = permisos.claves_de(usuario)

    if cambios.roles is not None:
        nuevos = list(dict.fromkeys(cambios.roles))
        if sorted(nuevos) != sorted(antes):
            if es_el_mismo:
                raise HTTPException(status_code=400, detail="No puede cambiar sus propios roles.")
            desconocidos = [c for c in nuevos if c not in roles_por_clave]
            if desconocidos:
                raise HTTPException(status_code=400, detail=f"Roles desconocidos: {', '.join(desconocidos)}.")
            # Solo puede asignar o quitar roles cuyos permisos él mismo tiene.
            for clave in set(nuevos) ^ set(antes):
                ajenos = set(roles_por_clave.get(clave, {}).get("permisos", [])) - admin["_permisos"]
                if ajenos:
                    raise HTTPException(
                        status_code=403,
                        detail=f"No puede asignar ni quitar el rol '{roles_por_clave[clave]['nombre']}': incluye permisos que usted no tiene.",
                    )
            if permisos.ROL_ADMIN in antes and permisos.ROL_ADMIN not in nuevos and permisos.admins_activos(excluir_id=usuario["_id"]) == 0:
                raise HTTPException(status_code=400, detail="Debe existir al menos un administrador activo.")
            actualizacion["roles"] = nuevos
            solicitud = usuario.get("solicitud") or {}
            nuevos_permisos = permisos.permisos_de({"roles": nuevos}, roles_por_clave)
            if "datos.consultar" in nuevos_permisos and solicitud.get("estado") == "pendiente":
                actualizacion["solicitud.estado"] = "aprobada"

    if cambios.activo is not None and cambios.activo != usuario.get("activo"):
        if es_el_mismo:
            raise HTTPException(status_code=400, detail="No puede desactivar su propia cuenta.")
        if not cambios.activo and permisos.es_admin(usuario) and permisos.admins_activos(excluir_id=usuario["_id"]) == 0:
            raise HTTPException(status_code=400, detail="Debe existir al menos un administrador activo.")
        actualizacion["activo"] = cambios.activo
        if not cambios.activo:
            # Expulsa de inmediato todas sus sesiones.
            actualizacion["token_version"] = int(usuario.get("token_version", 0)) + 1
        else:
            actualizacion["intentos_fallidos"] = 0
            actualizacion["bloqueado_hasta"] = None

    if not actualizacion:
        return {"usuario": usuario_publico(usuario, roles_por_clave)}

    db.usuarios.update_one({"_id": usuario["_id"]}, {"$set": actualizacion})
    if actualizacion.get("activo") is False:
        revocar_sesiones_usuario(usuario["_id"])

    actualizado = db.usuarios.find_one({"_id": usuario["_id"]})
    detalle = {"usuario": usuario.get("email")}
    if "roles" in actualizacion:
        detalle["roles"] = [", ".join(antes), ", ".join(actualizacion["roles"])]
        detalle["permisos"] = [
            ", ".join(sorted(permisos.permisos_de(usuario, roles_por_clave))) or "ninguno",
            ", ".join(sorted(permisos.permisos_de(actualizado, roles_por_clave))) or "ninguno",
        ]
    if "activo" in actualizacion:
        detalle["activo"] = [usuario.get("activo"), actualizado.get("activo")]
    auditoria.registrar("usuario_actualizado", request, admin, detalle=detalle)
    return {"usuario": usuario_publico(actualizado, roles_por_clave)}


@router.post("/usuarios/{usuario_id}/solicitud")
def decidir_solicitud(usuario_id: str, datos: DecisionSolicitud, request: Request, admin=Depends(APROBAR_SOLICITUDES)):
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
    if datos.decision == "aprobar":
        roles = [c for c in permisos.claves_de(usuario) if c != permisos.ROL_USUARIO]
        actualizacion["roles"] = list(dict.fromkeys(roles + [permisos.ROL_INVESTIGADOR]))

    db.usuarios.update_one({"_id": usuario["_id"]}, {"$set": actualizacion})
    auditoria.registrar(
        "solicitud_" + ("aprobada" if datos.decision == "aprobar" else "rechazada"),
        request,
        admin,
        detalle={"usuario": usuario.get("email")},
    )
    return {"usuario": usuario_publico(db.usuarios.find_one({"_id": usuario["_id"]}))}


@router.get("/usuarios/{usuario_id}/soporte")
def descargar_soporte(usuario_id: str, request: Request, admin=Depends(APROBAR_SOLICITUDES)):
    """Descarga el PDF de soporte de la solicitud (siempre como archivo adjunto)."""
    usuario = _obtener_usuario(usuario_id)
    soporte = (usuario.get("solicitud") or {}).get("soporte") or {}
    try:
        documento = db.documentos.find_one({"_id": ObjectId(soporte.get("id")), "usuario_id": usuario["_id"]})
    except (InvalidId, TypeError):
        documento = None
    if documento is None:
        raise HTTPException(status_code=404, detail="La solicitud no tiene documento de soporte.")
    contenido = cifrado.descifrar_bytes(documento["contenido"])
    auditoria.registrar("soporte_descargado", request, admin, detalle={"usuario": usuario.get("email")})
    return Response(
        content=contenido,
        media_type="application/pdf",
        headers={
            # Nunca se abre dentro de la aplicación: se descarga.
            "Content-Disposition": f'attachment; filename="soporte-{usuario_id}.pdf"',
            "Content-Security-Policy": "sandbox",
            "X-Content-Type-Options": "nosniff",
        },
    )


@router.post("/usuarios/{usuario_id}/restablecer-password")
def restablecer_password(usuario_id: str, request: Request, admin=Depends(GESTIONAR_USUARIOS)):
    """Genera una contraseña temporal aleatoria que se muestra UNA sola vez."""
    usuario = _obtener_usuario(usuario_id)
    if usuario["_id"] == admin["_id"]:
        raise HTTPException(status_code=400, detail="Use 'Cambiar contraseña' en su cuenta para su propia contraseña.")
    temporal = generar_password_temporal()
    _forzar_nueva_password(usuario, temporal, request, admin, "password_restablecida", {"metodo": "generada"})
    return {"password_temporal": temporal, "usuario": usuario_publico(db.usuarios.find_one({"_id": usuario["_id"]}))}


@router.post("/usuarios/{usuario_id}/establecer-password")
def establecer_password(usuario_id: str, datos: NuevaPassword, request: Request, admin=Depends(GESTIONAR_USUARIOS)):
    """El administrador escribe una contraseña para otra cuenta.

    Se aplica la MISMA política que a cualquier usuario (un administrador no
    puede asignar contraseñas débiles) y la persona deberá cambiarla al entrar.
    """
    usuario = _obtener_usuario(usuario_id)
    if usuario["_id"] == admin["_id"]:
        raise HTTPException(status_code=400, detail="Use 'Cambiar contraseña' en su cuenta para su propia contraseña.")
    error = validar_politica_password(datos.password, usuario.get("email"), usuario.get("nombre"))
    if error:
        auditoria.registrar(
            "password_restablecida", request, admin,
            detalle={"usuario": usuario.get("email"), "rechazada": error}, exito=False,
        )
        raise HTTPException(status_code=400, detail=error)
    _forzar_nueva_password(usuario, datos.password, request, admin, "password_restablecida", {"metodo": "escrita por el administrador"})
    return {"usuario": usuario_publico(db.usuarios.find_one({"_id": usuario["_id"]}))}


@router.post("/usuarios/{usuario_id}/descartar-recuperacion")
def descartar_recuperacion(usuario_id: str, request: Request, admin=Depends(GESTIONAR_USUARIOS)):
    usuario = _obtener_usuario(usuario_id)
    db.usuarios.update_one({"_id": usuario["_id"]}, {"$unset": {"recuperacion_solicitada": ""}})
    auditoria.registrar("recuperacion_descartada", request, admin, detalle={"usuario": usuario.get("email")})
    return {"usuario": usuario_publico(db.usuarios.find_one({"_id": usuario["_id"]}))}


@router.post("/usuarios/{usuario_id}/restablecer-2fa")
def restablecer_2fa(usuario_id: str, request: Request, admin=Depends(GESTIONAR_USUARIOS)):
    """Desactiva la verificación en dos pasos de otra cuenta (p. ej., perdió el celular)."""
    usuario = _obtener_usuario(usuario_id)
    if usuario["_id"] == admin["_id"]:
        raise HTTPException(status_code=400, detail="No puede restablecer su propia verificación en dos pasos.")
    if not (usuario.get("dos_pasos") or {}).get("activo"):
        raise HTTPException(status_code=400, detail="Esta cuenta no tiene activa la verificación en dos pasos.")
    db.usuarios.update_one(
        {"_id": usuario["_id"]},
        {"$unset": {"dos_pasos": ""}, "$set": {"token_version": int(usuario.get("token_version", 0)) + 1}},
    )
    revocar_sesiones_usuario(usuario["_id"])
    auditoria.registrar("2fa_restablecido", request, admin, detalle={"usuario": usuario.get("email")})
    return {"usuario": usuario_publico(db.usuarios.find_one({"_id": usuario["_id"]}))}


# ------------------------------------------------------------
# Roles y permisos
# ------------------------------------------------------------

@router.get("/roles")
def listar_roles(admin=Depends(VER_ROLES)):
    conteo = {}
    for u in db.usuarios.find({}, {"roles": 1, "rol": 1}):
        for clave in permisos.claves_de(u):
            conteo[clave] = conteo.get(clave, 0) + 1
    roles = sorted(db.roles.find({}), key=lambda r: (not r.get("sistema"), r["nombre"].lower()))
    return {"roles": [_rol_publico(r, conteo) for r in roles]}


@router.post("/roles", status_code=201)
def crear_rol(datos: DatosRol, request: Request, admin=Depends(GESTIONAR_ROLES)):
    if db.roles.find_one({"nombre": {"$regex": f"^{re.escape(datos.nombre)}$", "$options": "i"}}):
        raise HTTPException(status_code=409, detail="Ya existe un rol con ese nombre.")
    lista = _validar_permisos(datos.permisos, admin)
    rol = {
        "clave": permisos.generar_clave(datos.nombre),
        "nombre": datos.nombre,
        "descripcion": datos.descripcion,
        "permisos": lista,
        "sistema": False,
        "creado_en": ahora(),
        "creado_por": admin["_id"],
    }
    db.roles.insert_one(rol)
    auditoria.registrar("rol_creado", request, admin, detalle={"rol": rol["nombre"], "permisos": ", ".join(lista) or "ninguno"})
    return {"rol": _rol_publico(rol)}


@router.patch("/roles/{clave}")
def actualizar_rol(clave: str, cambios: CambioRol, request: Request, admin=Depends(GESTIONAR_ROLES)):
    rol = _obtener_rol(clave)
    if clave == permisos.ROL_ADMIN:
        raise HTTPException(status_code=400, detail="El rol Administrador tiene siempre todos los permisos y no se puede modificar.")
    actualizacion = {}
    if cambios.nombre is not None and cambios.nombre != rol["nombre"]:
        if rol.get("sistema"):
            raise HTTPException(status_code=400, detail="No se puede cambiar el nombre de un rol del sistema.")
        actualizacion["nombre"] = " ".join(cambios.nombre.split())
    if cambios.descripcion is not None:
        actualizacion["descripcion"] = cambios.descripcion
    if cambios.permisos is not None:
        lista = sorted(set(cambios.permisos))
        quitados_o_agregados = set(lista) ^ set(rol.get("permisos", []))
        _validar_permisos(list(quitados_o_agregados), admin)
        if clave in (permisos.ROL_USUARIO, permisos.ROL_INVESTIGADOR) and set(lista) - permisos.PERMISOS_DATOS:
            raise HTTPException(
                status_code=400,
                detail="Los roles Usuario e Investigador solo pueden tener permisos de consulta de datos.",
            )
        actualizacion["permisos"] = lista
    if not actualizacion:
        return {"rol": _rol_publico(rol)}
    db.roles.update_one({"clave": clave}, {"$set": actualizacion})
    nuevo = db.roles.find_one({"clave": clave})
    detalle = {"rol": nuevo["nombre"]}
    if "permisos" in actualizacion:
        detalle["permisos"] = [", ".join(sorted(rol.get("permisos", []))) or "ninguno", ", ".join(nuevo["permisos"]) or "ninguno"]
    auditoria.registrar("rol_actualizado", request, admin, detalle=detalle)
    return {"rol": _rol_publico(nuevo)}


@router.delete("/roles/{clave}")
def eliminar_rol(clave: str, request: Request, admin=Depends(GESTIONAR_ROLES)):
    rol = _obtener_rol(clave)
    if rol.get("sistema"):
        raise HTTPException(status_code=400, detail="Los roles del sistema no se pueden eliminar.")
    _validar_permisos(rol.get("permisos", []), admin)
    afectados = db.usuarios.update_many({"roles": clave}, {"$pull": {"roles": clave}}).modified_count
    # Una cuenta que se quede sin roles vuelve a "usuario".
    db.usuarios.update_many({"roles": {"$size": 0}}, {"$set": {"roles": [permisos.ROL_USUARIO]}})
    db.roles.delete_one({"clave": clave})
    auditoria.registrar("rol_eliminado", request, admin, detalle={"rol": rol["nombre"], "usuarios_afectados": afectados})
    return {"ok": True}


# ------------------------------------------------------------
# Configuración de sesión
# ------------------------------------------------------------

@router.get("/configuracion/sesion")
def ver_configuracion(admin=Depends(CONFIGURAR)):
    return {"valores": sesion_config.obtener(), "limites": sesion_config.limites()}


@router.patch("/configuracion/sesion")
def cambiar_configuracion(datos: ConfiguracionSesion, request: Request, admin=Depends(CONFIGURAR)):
    cambios = {k: v for k, v in datos.model_dump().items() if v is not None}
    for campo, valor in cambios.items():
        regla = sesion_config.CAMPOS[campo]
        if not regla["minimo"] <= valor <= regla["maximo"]:
            raise HTTPException(
                status_code=400,
                detail=f"{regla['descripcion']}: debe estar entre {regla['minimo']} y {regla['maximo']}.",
            )
    antes = sesion_config.obtener()
    despues = sesion_config.guardar(cambios) if cambios else antes
    diferencias = {c: [antes[c], despues[c]] for c in cambios if antes[c] != despues[c]}
    if diferencias:
        auditoria.registrar("configuracion_actualizada", request, admin, detalle=diferencias)
    return {"valores": despues, "limites": sesion_config.limites()}


# ------------------------------------------------------------
# Auditoría
# ------------------------------------------------------------

@router.get("/auditoria")
def ver_auditoria(
    limite: int = Query(default=100, ge=1, le=500),
    evento: str | None = Query(default=None, max_length=50, pattern=r"^[a-z0-9_]+$"),
    solo_fallidos: bool = False,
    admin=Depends(VER_AUDITORIA),
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
def ver_integridad(limite: int = Query(default=20, ge=1, le=100), admin=Depends(VER_AUDITORIA)):
    """Últimos registros de verificación SHA-256 del histórico."""
    registros = db.auditoria_integridad.find({}, {"_id": 0}).sort("_id", -1).limit(limite)
    return {"registros": [{k: (v.isoformat() if hasattr(v, "isoformat") else v) for k, v in r.items()} for r in registros]}


# ------------------------------------------------------------
# Registro de errores
# ------------------------------------------------------------

@router.get("/errores")
def ver_errores(limite: int = Query(default=50, ge=1, le=200), admin=Depends(VER_AUDITORIA)):
    errores.vaciar_pendientes()
    registros = db.registro_errores.find({}).sort("fecha", -1).limit(limite)
    return {
        "errores": [
            {
                "fecha": r["fecha"].strftime("%Y-%m-%dT%H:%M:%SZ"),
                "referencia": r.get("referencia"),
                "estado": r.get("estado"),
                "metodo": r.get("metodo"),
                "ruta": r.get("ruta"),
                "tipo": r.get("tipo"),
                "mensaje": r.get("mensaje"),
                "traza": r.get("traza"),
                "usuario_id": r.get("usuario_id"),
                "ip": r.get("ip"),
                "registrado_tarde": r.get("pendiente_desde") is not None,
            }
            for r in registros
        ]
    }


@router.post("/errores/simular")
def simular_error(request: Request, admin=Depends(CONFIGURAR)):
    """Provoca un fallo controlado para comprobar que el registro de errores funciona."""
    auditoria.registrar("fallo_simulado", request, admin)
    raise RuntimeError("Fallo simulado desde el panel de administración para verificar el registro de errores.")
