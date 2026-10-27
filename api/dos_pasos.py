"""Verificación en dos pasos con códigos TOTP (RFC 6238).

Compatible con Google Authenticator, Microsoft Authenticator, Authy, etc.

- El secreto TOTP se guarda CIFRADO (AES con Fernet); la clave se deriva
  de JWT_SECRET, así que una copia de la base de datos sola no basta para
  generar códigos.
- Se impide reutilizar un mismo código (protección contra repetición).
- Se entregan 8 códigos de recuperación de un solo uso, guardados como hash.
"""

import base64
import hashlib
import hmac
import io
import secrets
from datetime import timedelta

import jwt
import pyotp
import qrcode
import qrcode.image.svg
from cryptography.fernet import Fernet, InvalidToken

from api import config
from api.seguridad import ahora

# Clave de cifrado derivada (separada de la firma de JWT por el contexto).
_clave = hashlib.sha256(b"coraleum-totp-v1|" + config.JWT_SECRET.encode("utf-8")).digest()
_fernet = Fernet(base64.urlsafe_b64encode(_clave))

PERIODO = 30  # segundos por código
CANTIDAD_CODIGOS_RECUPERACION = 8


# --- Secreto ------------------------------------------------------

def nuevo_secreto():
    return pyotp.random_base32()


def cifrar(secreto):
    return _fernet.encrypt(secreto.encode("utf-8")).decode("ascii")


def descifrar(cifrado):
    try:
        return _fernet.decrypt(cifrado.encode("ascii")).decode("utf-8")
    except (InvalidToken, AttributeError, ValueError):
        return None


def uri_configuracion(secreto, email):
    return pyotp.TOTP(secreto, interval=PERIODO).provisioning_uri(name=email, issuer_name=config.TOTP_EMISOR)


def qr_svg_data_uri(texto):
    """Código QR como imagen SVG en data URI (sin servicios externos)."""
    imagen = qrcode.make(texto, image_factory=qrcode.image.svg.SvgPathImage, border=2)
    buffer = io.BytesIO()
    imagen.save(buffer)
    return "data:image/svg+xml;base64," + base64.b64encode(buffer.getvalue()).decode("ascii")


# --- Verificación -------------------------------------------------

def normalizar_codigo(codigo):
    return "".join(c for c in (codigo or "") if c.isalnum()).upper()


def verificar_totp(secreto, codigo, ultimo_paso_usado=None):
    """Devuelve el paso de tiempo usado si el código es válido, o None.

    Acepta el código actual y el de ±30 s (relojes desfasados), pero nunca
    un paso igual o anterior al último usado (evita reutilizar códigos).
    """
    codigo = normalizar_codigo(codigo)
    if len(codigo) != 6 or not codigo.isdigit():
        return None
    totp = pyotp.TOTP(secreto, interval=PERIODO)
    paso_actual = int(ahora().timestamp()) // PERIODO
    for desfase in (0, -1, 1):
        paso = paso_actual + desfase
        if ultimo_paso_usado is not None and paso <= int(ultimo_paso_usado):
            continue
        esperado = totp.generate_otp(paso)
        if hmac.compare_digest(esperado, codigo):
            return paso
    return None


# --- Códigos de recuperación --------------------------------------

def _hash_recuperacion(codigo):
    return hashlib.sha256(("coraleum-rec|" + normalizar_codigo(codigo)).encode("utf-8")).hexdigest()


def generar_codigos_recuperacion():
    """Devuelve (códigos en claro para mostrar UNA vez, hashes para guardar)."""
    alfabeto = "ABCDEFGHJKLMNPQRSTUVWXYZ23456789"  # sin 0/O ni 1/I
    codigos = []
    for _ in range(CANTIDAD_CODIGOS_RECUPERACION):
        bruto = "".join(secrets.choice(alfabeto) for _ in range(10))
        codigos.append(f"{bruto[:5]}-{bruto[5:]}")
    return codigos, [_hash_recuperacion(c) for c in codigos]


def usar_codigo_recuperacion(hashes, codigo):
    """Si el código coincide, devuelve la lista de hashes sin él; si no, None."""
    objetivo = _hash_recuperacion(codigo)
    for h in hashes or []:
        if hmac.compare_digest(h, objetivo):
            return [x for x in hashes if x != h]
    return None


# --- Desafío entre el primer y el segundo paso -------------------

def crear_desafio(usuario):
    """Token de corta duración que prueba que la contraseña ya fue correcta."""
    momento = ahora()
    carga = {
        "sub": str(usuario["_id"]),
        "ver": int(usuario.get("token_version", 0)),
        "tipo": "2fa",
        "iss": config.JWT_EMISOR,
        "iat": momento,
        "exp": momento + timedelta(minutes=config.MINUTOS_DESAFIO_2FA),
        "jti": secrets.token_hex(16),
    }
    return jwt.encode(carga, config.JWT_SECRET, algorithm=config.JWT_ALGORITMO)


def leer_desafio(token):
    try:
        carga = jwt.decode(
            token,
            config.JWT_SECRET,
            algorithms=[config.JWT_ALGORITMO],
            issuer=config.JWT_EMISOR,
            options={"require": ["exp", "iat", "sub", "iss"]},
        )
    except jwt.PyJWTError:
        return None
    return carga if carga.get("tipo") == "2fa" else None
