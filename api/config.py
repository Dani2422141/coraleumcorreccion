"""Configuración de la API leída desde variables de entorno (.env).

Ningún secreto se escribe en el código (RS03).
"""

import os
from urllib.parse import quote_plus

from dotenv import load_dotenv

load_dotenv()


def _bool(nombre, defecto=False):
    valor = os.getenv(nombre)
    if valor is None:
        return defecto
    return valor.strip().lower() in {"1", "true", "yes", "si", "sí"}


def _int(nombre, defecto):
    try:
        return int(os.getenv(nombre, defecto))
    except (TypeError, ValueError):
        return defecto


# --- MongoDB -------------------------------------------------
MONGO_HOST = os.getenv("MONGO_HOST", "mongodb")
MONGO_PORT = os.getenv("MONGO_PORT", "27017")
MONGO_DATABASE = os.getenv("MONGO_DATABASE", "proyecto_noaa")
MONGO_COLLECTION = os.getenv("MONGO_COLLECTION", "observaciones_noaa")


def construir_mongo_uri():
    """Cadena de conexión sin credenciales en el código.

    Orden de preferencia:
    1. MONGO_URI completa.
    2. Usuario de aplicación (MONGO_APP_*), con permisos solo sobre la BD.
    3. Usuario administrador (MONGO_INITDB_ROOT_*), solo como respaldo local.
    """
    uri = os.getenv("MONGO_URI")
    if uri:
        return uri

    candidatos = [
        (os.getenv("MONGO_APP_USERNAME"), os.getenv("MONGO_APP_PASSWORD"), MONGO_DATABASE),
        (os.getenv("MONGO_INITDB_ROOT_USERNAME"), os.getenv("MONGO_INITDB_ROOT_PASSWORD"), "admin"),
    ]
    for usuario, clave, auth_source in candidatos:
        if usuario and clave:
            return (
                f"mongodb://{quote_plus(usuario)}:{quote_plus(clave)}"
                f"@{MONGO_HOST}:{MONGO_PORT}/{MONGO_DATABASE}?authSource={auth_source}"
            )

    raise RuntimeError(
        "Configure MONGO_URI, o MONGO_APP_USERNAME/MONGO_APP_PASSWORD, en el entorno (.env)."
    )


# --- API -----------------------------------------------------
DOCS_HABILITADA = _bool("ENABLE_DOCS", False)

ORIGENES_PERMITIDOS = [
    origen.strip().rstrip("/")
    for origen in os.getenv("CORS_ORIGINS", "http://localhost:3000,http://localhost:5173").split(",")
    if origen.strip() and origen.strip() != "*"
]

# --- Autenticación -------------------------------------------
JWT_SECRET = os.getenv("JWT_SECRET", "")
if len(JWT_SECRET) < 32:
    raise RuntimeError(
        "JWT_SECRET no está definido o es muy corto (mínimo 32 caracteres). "
        "Genere uno con: python -c \"import secrets; print(secrets.token_urlsafe(48))\""
    )

JWT_ALGORITMO = "HS256"
JWT_EMISOR = "coraleum-api"

ACCESS_MINUTOS = _int("ACCESS_TOKEN_MINUTOS", 15)
REFRESH_DIAS = _int("REFRESH_TOKEN_DIAS", 7)

# Con HTTPS en producción debe ser true; en localhost (http) debe ser false.
COOKIE_SECURE = _bool("COOKIE_SECURE", False)
# Prefijo con el que Nginx/Vite exponen la API al navegador.
COOKIE_PREFIJO_RUTA = os.getenv("COOKIE_PATH_PREFIX", "/api").rstrip("/") or "/"

COOKIE_ACCESS = "coraleum_access"
COOKIE_REFRESH = "coraleum_refresh"

# Encabezado exigido en peticiones que modifican datos (protección CSRF).
CSRF_HEADER = "X-Requested-With"
CSRF_VALOR = "Coraleum"

# Bloqueo de cuenta tras intentos fallidos.
MAX_INTENTOS_FALLIDOS = _int("MAX_INTENTOS_FALLIDOS", 5)
MINUTOS_BLOQUEO = _int("MINUTOS_BLOQUEO", 15)

# Conservación del registro de auditoría de accesos.
DIAS_AUDITORIA = _int("DIAS_AUDITORIA", 180)

# --- Roles ---------------------------------------------------
ROL_USUARIO = "usuario"
ROL_INVESTIGADOR = "investigador"
ROL_ADMIN = "admin"
ROLES = (ROL_USUARIO, ROL_INVESTIGADOR, ROL_ADMIN)
ROLES_DATOS = (ROL_INVESTIGADOR, ROL_ADMIN)
