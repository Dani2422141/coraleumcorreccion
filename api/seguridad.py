"""Contraseñas, tokens y cookies de sesión.

- Contraseñas: Argon2id (algoritmo recomendado por OWASP).
- Sesión: token de acceso JWT de corta duración + refresh token opaco
  y rotativo. Ambos viajan en cookies HttpOnly (JavaScript no puede
  leerlos, lo que mitiga el robo de sesión por XSS).
- Los refresh tokens se guardan en la BD solo como hash SHA-256.
"""

import hashlib
import secrets
import uuid
from datetime import datetime, timedelta, timezone

import jwt
from argon2 import PasswordHasher
from argon2.exceptions import InvalidHashError, VerificationError, VerifyMismatchError

from api import config

_hasher = PasswordHasher()  # argon2id, parámetros por defecto de la librería

# Hash ficticio: se verifica contra él cuando el correo no existe, para que
# el tiempo de respuesta no revele si una cuenta está registrada.
_HASH_FICTICIO = _hasher.hash(secrets.token_urlsafe(16))

LONGITUD_MINIMA = 10
LONGITUD_MAXIMA = 128

# Contraseñas muy comunes (lista reducida). NIST SP 800-63B recomienda
# rechazar contraseñas conocidas en lugar de exigir símbolos obligatorios.
_COMUNES = {
    "1234567890", "12345678910", "0123456789", "1111111111", "0000000000",
    "qwertyuiop", "contraseña", "contrasena", "contrasena1", "contraseña1",
    "password12", "password123", "password1234", "passw0rd123", "iloveyou12",
    "abcdefghij", "abc1234567", "qwerty1234", "qwerty12345", "asdfghjkl1",
    "colombia123", "colombia2026", "bogota1234", "coraleum123", "corales123",
    "administrador", "admin12345", "usuario123", "bienvenido1", "1q2w3e4r5t",
}


def hash_password(password):
    return _hasher.hash(password)


def verificar_password(password, password_hash):
    """Devuelve (es_valida, necesita_rehash)."""
    try:
        _hasher.verify(password_hash or _HASH_FICTICIO, password)
    except (VerifyMismatchError, VerificationError, InvalidHashError):
        return False, False
    if not password_hash:
        return False, False
    return True, _hasher.check_needs_rehash(password_hash)


def verificar_tiempo_constante(password):
    """Consume el mismo tiempo que una verificación real (usuario inexistente)."""
    verificar_password(password, None)


# Secuencias que la gente usa para "completar" una contraseña larga.
_SECUENCIAS = (
    "abcdefghijklmnñopqrstuvwxyz",
    "0123456789",
    "qwertyuiop",
    "asdfghjklñ",
    "zxcvbnm",
    "1qaz2wsx3edc4rfv5tgb",
    "!@#$%^&*()",
)
_LONGITUD_TRAMO = 4  # un tramo secuencial cuenta desde 4 caracteres seguidos
_PROPORCION_MAXIMA_SECUENCIAL = 0.6


def _proporcion_secuencial(texto):
    """Fracción de caracteres que forman parte de tramos secuenciales.

    Cuenta tramos de 4 o más caracteres seguidos de una secuencia conocida
    (abecedario, dígitos, filas del teclado), en orden directo o inverso.
    Ej.: "qwertyuiop12" → 10 de 12 caracteres; "123456789101112131415" →
    los 9 primeros, más la regla de "solo números".
    """
    cubiertos = [False] * len(texto)
    for secuencia in _SECUENCIAS:
        for patron in (secuencia, secuencia[::-1]):
            i = 0
            while i < len(texto):
                largo = 0
                inicio = patron.find(texto[i]) if texto[i] in patron else -1
                if inicio >= 0:
                    while (
                        i + largo < len(texto)
                        and inicio + largo < len(patron)
                        and texto[i + largo] == patron[inicio + largo]
                    ):
                        largo += 1
                if largo >= _LONGITUD_TRAMO:
                    for j in range(i, i + largo):
                        cubiertos[j] = True
                    i += largo
                else:
                    i += 1
    return sum(cubiertos) / len(texto) if texto else 0


def _es_concatenacion_de_numeros(digitos):
    """True si es una cuenta seguida: "123456789101112", "20212223"…"""
    for inicio_largo in range(1, 4):
        n = int(digitos[:inicio_largo])
        armado = ""
        while len(armado) < len(digitos):
            armado += str(n)
            n += 1
        if armado[: len(digitos)] == digitos:
            return True
    return False


def validar_politica_password(password, email="", nombre=""):
    """Devuelve un mensaje de error o None si la contraseña es aceptable."""
    if not isinstance(password, str):
        return "Contraseña inválida."
    if len(password) < LONGITUD_MINIMA:
        return f"La contraseña debe tener al menos {LONGITUD_MINIMA} caracteres."
    if len(password) > LONGITUD_MAXIMA:
        return f"La contraseña no puede superar {LONGITUD_MAXIMA} caracteres."
    minuscula = password.lower()
    if minuscula in _COMUNES or len(set(password)) <= 3:
        return "Esa contraseña es demasiado común o predecible. Elija otra."
    sin_separadores = "".join(c for c in minuscula if not c.isspace() and c not in "-_.")
    if sin_separadores.isdigit():
        if _es_concatenacion_de_numeros(sin_separadores):
            return "La contraseña no puede ser una secuencia de números (por ejemplo, 123456789101112). Elija otra."
        return "La contraseña no puede contener solo números. Use palabras o una frase."
    if _proporcion_secuencial(sin_separadores) >= _PROPORCION_MAXIMA_SECUENCIAL:
        return "La contraseña está formada por secuencias predecibles (como abcd, 1234 o qwerty). Elija otra."
    local = (email or "").split("@")[0].lower()
    if len(local) >= 4 and local in minuscula:
        return "La contraseña no debe contener su correo."
    for parte in (nombre or "").lower().split():
        if len(parte) >= 4 and parte in minuscula:
            return "La contraseña no debe contener su nombre."
    return None


def generar_password_temporal():
    """Contraseña temporal para restablecimientos hechos por el administrador."""
    return secrets.token_urlsafe(12)


# --- Tokens -----------------------------------------------------

def ahora():
    return datetime.now(timezone.utc)


def a_utc(fecha):
    """MongoDB devuelve fechas sin zona horaria (en UTC); las normaliza."""
    if fecha is None:
        return None
    if fecha.tzinfo is None:
        return fecha.replace(tzinfo=timezone.utc)
    return fecha.astimezone(timezone.utc)


def crear_access_token(usuario, sid, minutos):
    """Token de acceso firmado, ligado a una sesión del servidor (`sid`).

    Aunque el token siga vigente, el servidor rechaza la petición si la
    sesión fue cerrada, venció por inactividad o superó su duración máxima.
    """
    momento = ahora()
    carga = {
        "sub": str(usuario["_id"]),
        "ver": int(usuario.get("token_version", 0)),
        "sid": str(sid),
        "tipo": "access",
        "iss": config.JWT_EMISOR,
        "iat": momento,
        "exp": momento + timedelta(minutes=minutos),
        "jti": uuid.uuid4().hex,
    }
    return jwt.encode(carga, config.JWT_SECRET, algorithm=config.JWT_ALGORITMO)


def decodificar_access_token(token):
    """Devuelve la carga del token o None si es inválido o venció."""
    try:
        carga = jwt.decode(
            token,
            config.JWT_SECRET,
            algorithms=[config.JWT_ALGORITMO],  # algoritmo fijo: evita "alg=none"
            issuer=config.JWT_EMISOR,
            options={"require": ["exp", "iat", "sub", "iss"]},
        )
    except jwt.PyJWTError:
        return None
    if carga.get("tipo") != "access":
        return None
    return carga


def generar_refresh_token():
    return secrets.token_urlsafe(48)


def hash_token(token):
    return hashlib.sha256(token.encode("utf-8")).hexdigest()


# --- Cookies ----------------------------------------------------

def _ruta_refresh():
    return f"{config.COOKIE_PREFIJO_RUTA.rstrip('/')}/auth"


def poner_cookies_sesion(respuesta, access_token, refresh_token, access_segundos, refresh_segundos):
    comunes = {"httponly": True, "secure": config.COOKIE_SECURE, "samesite": "strict"}
    respuesta.set_cookie(
        config.COOKIE_ACCESS,
        access_token,
        max_age=access_segundos,
        path=config.COOKIE_PREFIJO_RUTA,
        **comunes,
    )
    # El refresh token solo se envía a /api/auth: no viaja en cada petición.
    respuesta.set_cookie(
        config.COOKIE_REFRESH,
        refresh_token,
        max_age=refresh_segundos,
        path=_ruta_refresh(),
        **comunes,
    )


def borrar_cookies_sesion(respuesta):
    comunes = {"httponly": True, "secure": config.COOKIE_SECURE, "samesite": "strict"}
    respuesta.delete_cookie(config.COOKIE_ACCESS, path=config.COOKIE_PREFIJO_RUTA, **comunes)
    respuesta.delete_cookie(config.COOKIE_REFRESH, path=_ruta_refresh(), **comunes)
