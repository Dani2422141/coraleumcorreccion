"""Tiempos de sesión configurables por el administrador.

Se guardan en la colección `configuracion` (documento "sesion") y se
aplican a todas las sesiones de inmediato. Los límites siguen NIST
SP 800-63B-4 para el nivel AAL2: inactividad de máximo 1 hora y
reautenticación al menos cada 24 horas.
"""

import os
import time

from api import db

# Valores por defecto (pueden ajustarse en .env) y límites permitidos.
CAMPOS = {
    "token_minutos": {
        "defecto": int(os.getenv("ACCESS_TOKEN_MINUTOS", "15")),
        "minimo": 1,
        "maximo": 60,
        "descripcion": "Vigencia del token de acceso (minutos)",
    },
    "inactividad_minutos": {
        "defecto": int(os.getenv("SESION_INACTIVIDAD_MINUTOS", "30")),
        "minimo": 1,
        "maximo": 60,
        "descripcion": "Cierre de sesión por inactividad (minutos)",
    },
    "maxima_horas": {
        "defecto": int(os.getenv("SESION_MAXIMA_HORAS", "12")),
        "minimo": 1,
        "maximo": 24,
        "descripcion": "Duración máxima de una sesión (horas)",
    },
    "sesiones_simultaneas": {
        "defecto": int(os.getenv("SESIONES_SIMULTANEAS", "1")),
        "minimo": 1,
        "maximo": 5,
        "descripcion": "Sesiones simultáneas por usuario (navegadores o dispositivos)",
    },
}

# Límite superior absoluto de una sesión (para la limpieza automática).
HORAS_LIMITE = CAMPOS["maxima_horas"]["maximo"]

_cache = {"valor": None, "hasta": 0.0}
_SEGUNDOS_CACHE = 3


def _acotar(campo, valor):
    regla = CAMPOS[campo]
    try:
        valor = int(valor)
    except (TypeError, ValueError):
        valor = regla["defecto"]
    return max(regla["minimo"], min(regla["maximo"], valor))


def obtener():
    """Configuración vigente (con caché de 3 segundos)."""
    momento = time.monotonic()
    if _cache["valor"] is not None and momento < _cache["hasta"]:
        return dict(_cache["valor"])
    guardada = db.configuracion.find_one({"_id": "sesion"}) or {}
    valor = {campo: _acotar(campo, guardada.get(campo, regla["defecto"])) for campo, regla in CAMPOS.items()}
    _cache.update(valor=valor, hasta=momento + _SEGUNDOS_CACHE)
    return dict(valor)


def guardar(cambios):
    """Guarda los campos indicados; los valores fuera de rango se rechazan antes."""
    db.configuracion.update_one({"_id": "sesion"}, {"$set": cambios}, upsert=True)
    invalidar()
    return obtener()


def invalidar():
    _cache.update(valor=None, hasta=0.0)


def limites():
    return {campo: {k: v for k, v in regla.items()} for campo, regla in CAMPOS.items()}
