"""Conexión a MongoDB y creación de índices."""

import logging

from pymongo import ASCENDING, DESCENDING, MongoClient
from pymongo.errors import PyMongoError

from api import config

logger = logging.getLogger("coraleum.db")

cliente = MongoClient(config.construir_mongo_uri(), serverSelectionTimeoutMS=5000, tz_aware=False)
db = cliente[config.MONGO_DATABASE]

observaciones = db[config.MONGO_COLLECTION]
usuarios = db["usuarios"]
sesiones = db["sesiones"]
auditoria_accesos = db["auditoria_accesos"]
auditoria_integridad = db["auditoria_integridad"]


def crear_indices():
    """Crea los índices necesarios. Es idempotente."""
    try:
        # Un correo = una cuenta.
        usuarios.create_index([("email", ASCENDING)], unique=True, name="email_unico")
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
        logger.info("Índices de autenticación verificados.")
    except PyMongoError as error:
        logger.error("No fue posible crear los índices: %s", error)
