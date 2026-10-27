"""Control de acceso basado en roles (RBAC) con permisos configurables.

- Los PERMISOS son un catálogo fijo definido en el código: cada ruta del
  backend exige uno o más.
- Los ROLES se guardan en la colección `roles`: agrupan permisos y el
  administrador puede crear, editar y eliminar roles propios.
- Un usuario puede tener VARIOS roles; sus permisos efectivos son la unión
  de los permisos de todos ellos.

Reglas de seguridad:
- Tres roles del sistema: `usuario` (sin permisos), `investigador` (datos)
  y `admin` (todos los permisos, no editable).
- Nadie puede cambiar sus propios roles.
- Solo se pueden asignar roles o conceder permisos que uno mismo tiene
  (evita el escalamiento de privilegios).
- Siempre debe quedar al menos un administrador activo.
"""

import re
import unicodedata

from api import db
from api.seguridad import ahora

# ------------------------------------------------------------
# Catálogo de permisos
# ------------------------------------------------------------

PERMISOS = {
    "datos.consultar": "Consultar el Explorador Térmico, el detalle por área y el Resumen",
    "datos.historico": "Ver el registro histórico de indicadores por área",
    "solicitudes.aprobar": "Aprobar o rechazar solicitudes de acceso de investigador",
    "usuarios.gestionar": "Gestionar usuarios: roles, activación y contraseñas",
    "roles.gestionar": "Crear, editar y eliminar roles y sus permisos",
    "auditoria.ver": "Ver el registro de auditoría de accesos",
    "configuracion.gestionar": "Configurar la duración y la inactividad de las sesiones",
}

PERMISOS_DATOS = {"datos.consultar", "datos.historico"}
PERMISOS_ADMIN = set(PERMISOS) - PERMISOS_DATOS

ROL_USUARIO = "usuario"
ROL_INVESTIGADOR = "investigador"
ROL_ADMIN = "admin"

ROLES_SISTEMA = {
    ROL_USUARIO: {
        "nombre": "Usuario",
        "descripcion": "Cuenta registrada: contenido educativo y solicitud de acceso.",
        "permisos": [],
    },
    ROL_INVESTIGADOR: {
        "nombre": "Investigador",
        "descripcion": "Consulta del Explorador Térmico y del histórico.",
        "permisos": ["datos.consultar", "datos.historico"],
    },
    ROL_ADMIN: {
        "nombre": "Administrador",
        "descripcion": "Todos los permisos. No se puede modificar.",
        "permisos": sorted(PERMISOS),
    },
}


# ------------------------------------------------------------
# Inicialización y migración
# ------------------------------------------------------------

def sembrar_roles():
    """Crea los roles del sistema y migra usuarios del modelo de rol único."""
    db.roles.create_index("clave", unique=True, name="clave_unica")
    momento = ahora()
    for clave, datos in ROLES_SISTEMA.items():
        db.roles.update_one(
            {"clave": clave},
            {
                "$setOnInsert": {
                    "clave": clave,
                    "nombre": datos["nombre"],
                    "descripcion": datos["descripcion"],
                    "permisos": datos["permisos"],
                    "creado_en": momento,
                },
                "$set": {"sistema": True},
            },
            upsert=True,
        )
    # El administrador SIEMPRE tiene todos los permisos.
    db.roles.update_one({"clave": ROL_ADMIN}, {"$set": {"permisos": sorted(PERMISOS)}})
    # Los roles de usuario e investigador solo pueden tener permisos de datos.
    for clave in (ROL_USUARIO, ROL_INVESTIGADOR):
        rol = db.roles.find_one({"clave": clave}) or {}
        limpios = [p for p in rol.get("permisos", []) if p in PERMISOS_DATOS]
        db.roles.update_one({"clave": clave}, {"$set": {"permisos": limpios}})

    # Migración: cuentas anteriores con un solo campo "rol".
    for usuario in db.usuarios.find({"roles": {"$exists": False}}, {"rol": 1}):
        db.usuarios.update_one(
            {"_id": usuario["_id"]},
            {"$set": {"roles": [usuario.get("rol") or ROL_USUARIO]}, "$unset": {"rol": ""}},
        )


# ------------------------------------------------------------
# Consulta de roles y permisos
# ------------------------------------------------------------

def claves_de(usuario):
    """Roles del usuario (compatible con cuentas que aún tienen 'rol')."""
    roles = usuario.get("roles")
    if roles is None:
        roles = [usuario.get("rol") or ROL_USUARIO]
    return list(dict.fromkeys(roles))


def mapa_roles():
    return {r["clave"]: r for r in db.roles.find({})}


def permisos_de(usuario, roles_por_clave=None):
    roles_por_clave = roles_por_clave if roles_por_clave is not None else mapa_roles()
    permisos = set()
    for clave in claves_de(usuario):
        permisos.update(roles_por_clave.get(clave, {}).get("permisos", []))
    return permisos & set(PERMISOS)


def rol_principal(claves):
    """Rol que se muestra como principal (compatibilidad con la interfaz)."""
    for clave in (ROL_ADMIN, ROL_INVESTIGADOR):
        if clave in claves:
            return clave
    otros = [c for c in claves if c != ROL_USUARIO]
    return otros[0] if otros else ROL_USUARIO


def es_admin(usuario):
    return ROL_ADMIN in claves_de(usuario)


def tiene_permisos_administrativos(permisos):
    return bool(set(permisos) & PERMISOS_ADMIN)


def admins_activos(excluir_id=None):
    filtro = {"roles": ROL_ADMIN, "activo": True}
    if excluir_id is not None:
        filtro["_id"] = {"$ne": excluir_id}
    return db.usuarios.count_documents(filtro)


def generar_clave(nombre):
    """'Analista de datos' → 'analista-de-datos' (única)."""
    base = unicodedata.normalize("NFKD", nombre).encode("ascii", "ignore").decode("ascii").lower()
    base = re.sub(r"[^a-z0-9]+", "-", base).strip("-")[:40] or "rol"
    clave, n = base, 2
    while db.roles.find_one({"clave": clave}) or clave in ROLES_SISTEMA:
        clave = f"{base}-{n}"
        n += 1
    return clave
