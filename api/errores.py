"""Registro de errores de la aplicación.

Cada fallo no controlado (500) o caída de la base de datos (503) queda
registrado en tres lugares:

1. La colección `registro_errores` de MongoDB, visible en
   Administración → Errores (se conserva 90 días).
2. El archivo logs/errores.log del backend (rotativo, 5 × 1 MB).
3. La salida estándar del contenedor (docker compose logs backend).

A la persona solo se le muestra un mensaje genérico con un CÓDIGO DE
REFERENCIA (p. ej. 7F3A91C2); el detalle técnico (tipo, traza) solo lo ve
el administrador. Así no se filtran detalles internos (OWASP A09/A05).

Si la base de datos está caída, el error se guarda en memoria y se escribe
en MongoDB en cuanto vuelva a estar disponible.
"""

import logging
import os
import secrets
import traceback
from collections import deque
from logging.handlers import RotatingFileHandler

from pymongo.errors import ConnectionFailure, PyMongoError

from api import config, db
from api.auditoria import ip_cliente
from api.seguridad import ahora, decodificar_access_token

logger = logging.getLogger("coraleum.errores")

CARPETA_LOGS = os.getenv("CARPETA_LOGS", os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "logs"))
_pendientes = deque(maxlen=500)


def _configurar_archivo():
    try:
        os.makedirs(CARPETA_LOGS, exist_ok=True)
        manejador = RotatingFileHandler(
            os.path.join(CARPETA_LOGS, "errores.log"), maxBytes=1_000_000, backupCount=5, encoding="utf-8"
        )
    except OSError as error:
        logger.warning("No se pudo abrir el archivo de errores en %s: %s", CARPETA_LOGS, error)
        return
    manejador.setFormatter(logging.Formatter("%(asctime)s %(levelname)s %(message)s"))
    logger.addHandler(manejador)


_configurar_archivo()


def _usuario_de(request):
    """Id del usuario a partir del token, sin consultar la base de datos."""
    carga = decodificar_access_token(request.cookies.get(config.COOKIE_ACCESS) or "")
    return carga.get("sub") if carga else None


def vaciar_pendientes():
    """Escribe en MongoDB los errores que ocurrieron con la base de datos caída."""
    while _pendientes:
        documento = _pendientes[0]
        try:
            db.registro_errores.insert_one(dict(documento))
        except PyMongoError:
            return
        _pendientes.popleft()


def registrar(request, exc, estado):
    """Registra el error y devuelve su código de referencia."""
    referencia = secrets.token_hex(4).upper()
    traza = "".join(traceback.format_exception(type(exc), exc, exc.__traceback__))
    documento = {
        "fecha": ahora(),
        "referencia": referencia,
        "estado": estado,
        "metodo": request.method,
        "ruta": request.url.path,
        "tipo": type(exc).__name__,
        "mensaje": str(exc)[:500],
        "traza": traza[-6000:],
        "usuario_id": _usuario_de(request),
        "ip": ip_cliente(request),
        "pendiente_desde": None,
    }
    logger.error(
        "[ref %s] %s %s → %s %s: %s\n%s",
        referencia, request.method, request.url.path, estado, documento["tipo"], documento["mensaje"], traza,
    )
    if isinstance(exc, ConnectionFailure):
        # Sin base de datos no tiene sentido esperar otro tiempo de espera.
        _pendientes.append({**documento, "pendiente_desde": documento["fecha"]})
        return referencia
    try:
        vaciar_pendientes()
        db.registro_errores.insert_one(documento)
    except PyMongoError:
        _pendientes.append({**documento, "pendiente_desde": documento["fecha"]})
    return referencia
