"""Cifrado de datos personales a nivel de campo (Ley 1581 de 2012, art. 4 lit. g).

Los datos personales se guardan CIFRADOS en MongoDB (AES-128-CBC + HMAC-SHA256,
formato Fernet). Quien obtenga una copia de la base de datos —o mire las
colecciones con mongosh o Compass— solo ve textos como `enc1:gAAAAAB…`.

- La clave sale de la variable CLAVE_CIFRADO_DATOS (.env) y nunca se guarda
  en la base de datos.
- Para poder buscar por correo sin descifrar todo, se guarda además un
  índice ciego: HMAC-SHA256 del correo normalizado (`email_hmac`). No se
  puede revertir para obtener el correo.
- La contraseña NO se cifra: se guarda como hash Argon2id (irreversible),
  que es lo correcto para contraseñas.

`ColeccionCifrada` envuelve una colección de PyMongo: cifra al escribir y
descifra al leer, de forma transparente para el resto del código.
"""

import base64
import copy
import hashlib
import hmac
import json
import logging

from cryptography.fernet import Fernet, InvalidToken

from api import config

logger = logging.getLogger("coraleum.cifrado")

PREFIJO = "enc1:"

_maestra = config.CLAVE_CIFRADO_DATOS.encode("utf-8")
_fernet = Fernet(base64.urlsafe_b64encode(hashlib.sha256(b"coraleum-datos-v1|" + _maestra).digest()))
_clave_indice = hashlib.sha256(b"coraleum-indice-v1|" + _maestra).digest()


# ------------------------------------------------------------
# Primitivas
# ------------------------------------------------------------

def esta_cifrado(valor):
    return isinstance(valor, str) and valor.startswith(PREFIJO)


def cifrar(valor):
    """Cifra cualquier valor serializable en JSON. None se deja como None."""
    if valor is None or esta_cifrado(valor):
        return valor
    texto = json.dumps(valor, ensure_ascii=False, default=str)
    return PREFIJO + _fernet.encrypt(texto.encode("utf-8")).decode("ascii")


def descifrar(valor):
    """Devuelve el valor original. Los valores antiguos sin cifrar se devuelven tal cual."""
    if not esta_cifrado(valor):
        return valor
    try:
        return json.loads(_fernet.decrypt(valor[len(PREFIJO):].encode("ascii")).decode("utf-8"))
    except (InvalidToken, ValueError):
        logger.error("No fue posible descifrar un campo (¿cambió CLAVE_CIFRADO_DATOS?).")
        return None


def cifrar_bytes(contenido):
    return _fernet.encrypt(contenido)


def descifrar_bytes(contenido):
    return _fernet.decrypt(bytes(contenido))


def indice(valor):
    """Índice ciego (HMAC-SHA256) para búsquedas exactas sobre un campo cifrado."""
    if valor is None:
        return None
    normalizado = str(valor).strip().lower()
    return hmac.new(_clave_indice, normalizado.encode("utf-8"), hashlib.sha256).hexdigest()


def enmascarar_email(email):
    """ana.perez@ejemplo.org → an•••••••@ejemplo.org"""
    if not email or "@" not in email:
        return email
    local, dominio = email.split("@", 1)
    return f"{local[:2]}{'•' * max(len(local) - 2, 3)}@{dominio}"


# ------------------------------------------------------------
# Utilidades sobre documentos con rutas "a.b"
# ------------------------------------------------------------

def _obtener(doc, ruta):
    actual = doc
    for parte in ruta.split("."):
        if not isinstance(actual, dict) or parte not in actual:
            return False, None
        actual = actual[parte]
    return True, actual


def _poner(doc, ruta, valor):
    partes = ruta.split(".")
    actual = doc
    for parte in partes[:-1]:
        actual = actual[parte]
    actual[partes[-1]] = valor


class _Cursor:
    """Cursor que descifra cada documento al iterar."""

    def __init__(self, cursor, coleccion):
        self._cursor = cursor
        self._coleccion = coleccion

    def sort(self, *args, **kwargs):
        self._cursor = self._cursor.sort(*args, **kwargs)
        return self

    def limit(self, *args, **kwargs):
        self._cursor = self._cursor.limit(*args, **kwargs)
        return self

    def skip(self, *args, **kwargs):
        self._cursor = self._cursor.skip(*args, **kwargs)
        return self

    def __iter__(self):
        for documento in self._cursor:
            yield self._coleccion.descifrar_documento(documento)


class ColeccionCifrada:
    """Envoltura de una colección de PyMongo con cifrado por campo.

    campos: rutas que se guardan cifradas ("email", "consentimiento.ip"…).
    indices: {campo: campo_hmac} para los campos que se buscan por igualdad.
    """

    def __init__(self, coleccion, campos, indices=None):
        self._c = coleccion
        self.campos = tuple(campos)
        self.indices = dict(indices or {})

    def __getattr__(self, nombre):
        # create_index, delete_many, drop_index, index_information, etc.
        return getattr(self._c, nombre)

    @property
    def cruda(self):
        """La colección sin envoltura (para ver lo que realmente se guarda)."""
        return self._c

    # --- Conversión ------------------------------------------------

    def _cifrar_en(self, destino, ruta_base, valor):
        """Cifra `valor` (que se guardará en `ruta_base`) y agrega índices.

        Devuelve el valor cifrado y un dict de campos extra (índices) a poner.
        """
        extra = {}
        prefijo = ruta_base + "." if ruta_base else ""
        if ruta_base in self.campos:
            if ruta_base in self.indices:
                extra[self.indices[ruta_base]] = indice(valor)
            return cifrar(valor), extra
        if isinstance(valor, dict):
            valor = copy.deepcopy(valor)
            for campo in self.campos:
                if campo.startswith(prefijo):
                    relativo = campo[len(prefijo):]
                    existe, original = _obtener(valor, relativo)
                    if existe:
                        _poner(valor, relativo, cifrar(original))
                        if campo in self.indices:
                            extra[self.indices[campo]] = indice(original)
        return valor, extra

    def cifrar_documento(self, documento):
        cifrado, extra = self._cifrar_en(None, "", documento)
        cifrado.update(extra)
        return cifrado

    def descifrar_documento(self, documento):
        if documento is None:
            return None
        for campo in self.campos:
            existe, valor = _obtener(documento, campo)
            if existe:
                _poner(documento, campo, descifrar(valor))
        for campo_hmac in self.indices.values():
            documento.pop(campo_hmac, None)
        return documento

    def _filtro(self, filtro):
        """{"email": "x"} → {"email_hmac": HMAC("x")}. No admite regex sobre campos cifrados."""
        if not isinstance(filtro, dict):
            return filtro
        resultado = {}
        for clave, valor in filtro.items():
            if clave in ("$or", "$and", "$nor") and isinstance(valor, list):
                resultado[clave] = [self._filtro(f) for f in valor]
            elif clave in self.indices:
                if isinstance(valor, dict):
                    raise ValueError(f"El campo cifrado '{clave}' solo admite búsquedas exactas.")
                resultado[self.indices[clave]] = indice(valor)
            elif clave in self.campos:
                raise ValueError(f"El campo cifrado '{clave}' no admite búsquedas.")
            else:
                resultado[clave] = valor
        return resultado

    def _actualizacion(self, actualizacion):
        if not isinstance(actualizacion, dict) or "$set" not in actualizacion:
            return actualizacion
        nuevo_set = {}
        for ruta, valor in actualizacion["$set"].items():
            cifrado, extra = self._cifrar_en(None, ruta, valor)
            nuevo_set[ruta] = cifrado
            nuevo_set.update(extra)
        return {**actualizacion, "$set": nuevo_set}

    # --- Operaciones -----------------------------------------------

    def find_one(self, filtro=None, *args, **kwargs):
        return self.descifrar_documento(self._c.find_one(self._filtro(filtro or {}), *args, **kwargs))

    def find(self, filtro=None, *args, **kwargs):
        return _Cursor(self._c.find(self._filtro(filtro or {}), *args, **kwargs), self)

    def count_documents(self, filtro, *args, **kwargs):
        return self._c.count_documents(self._filtro(filtro), *args, **kwargs)

    def insert_one(self, documento, *args, **kwargs):
        cifrado = self.cifrar_documento(documento)
        resultado = self._c.insert_one(cifrado, *args, **kwargs)
        documento["_id"] = resultado.inserted_id
        return resultado

    def update_one(self, filtro, actualizacion, *args, **kwargs):
        return self._c.update_one(self._filtro(filtro), self._actualizacion(actualizacion), *args, **kwargs)

    def update_many(self, filtro, actualizacion, *args, **kwargs):
        return self._c.update_many(self._filtro(filtro), self._actualizacion(actualizacion), *args, **kwargs)

    def delete_one(self, filtro, *args, **kwargs):
        return self._c.delete_one(self._filtro(filtro), *args, **kwargs)

    def delete_many(self, filtro, *args, **kwargs):
        return self._c.delete_many(self._filtro(filtro), *args, **kwargs)

    # --- Migración -------------------------------------------------

    def migrar(self):
        """Cifra los documentos guardados antes de activar el cifrado. Idempotente."""
        migrados = 0
        for documento in self._c.find({}):
            cambios = {}
            for campo in self.campos:
                existe, valor = _obtener(documento, campo)
                if existe and valor is not None and not esta_cifrado(valor):
                    cambios[campo] = cifrar(valor)
                if campo in self.indices and existe:
                    original = descifrar(valor)
                    esperado = indice(original)
                    if documento.get(self.indices[campo]) != esperado:
                        cambios[self.indices[campo]] = esperado
            if cambios:
                self._c.update_one({"_id": documento["_id"]}, {"$set": cambios})
                migrados += 1
        return migrados
