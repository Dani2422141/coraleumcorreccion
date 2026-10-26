"""Registro de eventos de seguridad en la colección auditoria_accesos."""

import logging

from pymongo.errors import PyMongoError

from api import db
from api.seguridad import ahora

logger = logging.getLogger("coraleum.auditoria")


def ip_cliente(request):
    """IP real del cliente.

    El backend solo es accesible a través de Nginx, que fija X-Real-IP;
    por eso ese encabezado es confiable aquí.
    """
    ip = request.headers.get("x-real-ip")
    if ip:
        return ip.strip()[:64]
    return request.client.host if request.client else "desconocida"


def registrar(evento, request=None, usuario=None, email=None, detalle=None, exito=True):
    documento = {
        "fecha": ahora(),
        "evento": evento,
        "exito": exito,
        "usuario_id": usuario.get("_id") if usuario else None,
        "email": (usuario or {}).get("email") or email,
        "ip": ip_cliente(request) if request is not None else None,
        "user_agent": (request.headers.get("user-agent", "")[:200] if request is not None else None),
        "detalle": detalle,
    }
    try:
        db.auditoria_accesos.insert_one(documento)
    except PyMongoError as error:
        # La auditoría nunca debe tumbar la operación principal.
        logger.error("No se pudo registrar el evento %s: %s", evento, error)
