"""Conexión a MongoDB y creación de índices."""

import logging

from pymongo import ASCENDING, DESCENDING, MongoClient
from pymongo.errors import PyMongoError

from api import cifrado, config

logger = logging.getLogger("coraleum.db")

cliente = MongoClient(config.construir_mongo_uri(), serverSelectionTimeoutMS=5000, tz_aware=False)
db = cliente[config.MONGO_DATABASE]

observaciones = db[config.MONGO_COLLECTION]

# Colecciones con datos personales: se cifran por campo (api/cifrado.py).
usuarios = cifrado.ColeccionCifrada(
    db["usuarios"],
    campos=(
        "email",
        "nombre",
        "consentimiento.ip",
        "recuperacion_solicitada.ip",
        "solicitud.institucion",
        "solicitud.motivo",
        "solicitud.comentario_admin",
        "solicitud.soporte",
    ),
    indices={"email": "email_hmac"},
)
sesiones = cifrado.ColeccionCifrada(db["sesiones"], campos=("ip", "user_agent"))
auditoria_accesos = cifrado.ColeccionCifrada(
    db["auditoria_accesos"],
    campos=("email", "ip", "user_agent", "detalle"),
    indices={"email": "email_hmac"},
)
registro_errores = cifrado.ColeccionCifrada(db["registro_errores"], campos=("ip", "usuario_email"))
# Archivos cargados (soporte de la solicitud de investigador). El contenido se cifra aparte.
documentos = cifrado.ColeccionCifrada(db["documentos"], campos=("nombre_original",))

auditoria_integridad = db["auditoria_integridad"]
roles = db["roles"]
configuracion = db["configuracion"]

DIAS_REGISTRO_ERRORES = 90


def _migrar_cifrado():
    """Cifra los datos personales guardados por versiones anteriores."""
    if "email_unico" in usuarios.index_information():
        # El índice antiguo era sobre el correo en claro; ahora es sobre su HMAC.
        usuarios.drop_index("email_unico")
    for nombre, coleccion in (
        ("usuarios", usuarios),
        ("sesiones", sesiones),
        ("auditoria_accesos", auditoria_accesos),
    ):
        migrados = coleccion.migrar()
        if migrados:
            logger.info("Cifrado: %s documentos de %s protegidos.", migrados, nombre)


def crear_indices():
    """Crea los índices necesarios. Es idempotente."""
    try:
        _migrar_cifrado()
        # Un correo = una cuenta (se compara el HMAC del correo, que no revela el correo).
        usuarios.create_index([("email_hmac", ASCENDING)], unique=True, name="email_hmac_unico")
        usuarios.create_index([("solicitud.estado", ASCENDING)], name="solicitud_estado")

        # El refresh token se guarda como hash; se busca por él.
        sesiones.create_index([("token_hash", ASCENDING)], unique=True, name="token_hash_unico")
        sesiones.create_index([("usuario_id", ASCENDING)], name="sesiones_usuario")
        sesiones.create_index([("familia", ASCENDING)], name="sesiones_familia")
        # MongoDB borra automáticamente las sesiones vencidas.
        sesiones.create_index([("expira", ASCENDING)], expireAfterSeconds=0, name="sesiones_ttl")

        # Auditoría con caducidad automática.
        auditoria_accesos.create_index(
            [("fecha", DESCENDING)],
            expireAfterSeconds=config.DIAS_AUDITORIA * 24 * 3600,
            name="auditoria_ttl",
        )
        auditoria_accesos.create_index([("usuario_id", ASCENDING)], name="auditoria_usuario")
        sesiones.create_index([("ultima_actividad", ASCENDING)], name="sesiones_actividad")
        auditoria_accesos.create_index([("evento", ASCENDING)], name="auditoria_evento")
        registro_errores.create_index(
            [("fecha", DESCENDING)],
            expireAfterSeconds=DIAS_REGISTRO_ERRORES * 24 * 3600,
            name="errores_ttl",
        )
        registro_errores.create_index([("referencia", ASCENDING)], name="errores_referencia")
        documentos.create_index([("usuario_id", ASCENDING)], name="documentos_usuario")
        # Roles del sistema y migración de cuentas antiguas (un solo rol).
        from api.permisos import sembrar_roles

        sembrar_roles()
        logger.info("Índices de autenticación verificados.")
    except PyMongoError as error:
        logger.error("No fue posible crear los índices: %s", error)
