"""Configuración de pruebas: MongoDB simulado en memoria (mongomock).

Las pruebas no necesitan Docker ni una base de datos real.
Ejecutar desde la raíz del proyecto:

    pip install -r requirements-dev.txt
    pytest
"""

import csv
import os
import sys
from datetime import datetime
from pathlib import Path

import mongomock
import pymongo
import pytest

RAIZ = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(RAIZ))

os.environ.setdefault("MONGO_URI", "mongodb://pruebas/proyecto_noaa")
os.environ.setdefault("JWT_SECRET", "clave-de-pruebas-solo-para-tests-0123456789abcdef")
os.environ.setdefault("CLAVE_CIFRADO_DATOS", "clave-de-cifrado-solo-para-tests-fedcba9876543210")
os.environ.setdefault("CARPETA_LOGS", os.path.join(os.path.dirname(__file__), ".logs"))
os.environ["COOKIE_PATH_PREFIX"] = "/"  # TestClient no pasa por Nginx (/api)
os.environ["COOKIE_SECURE"] = "false"

# Sustituye el cliente real antes de importar la API.
pymongo.MongoClient = mongomock.MongoClient

from fastapi.testclient import TestClient  # noqa: E402

import pyotp  # noqa: E402

from api import db, dos_pasos, limites, sesion_config  # noqa: E402
from api.main import app  # noqa: E402
from api.seguridad import ahora, hash_password  # noqa: E402

CSRF = {"X-Requested-With": "Coraleum"}
PASSWORD_ADMIN = "Arrecife-Admin-2026!"
SECRETO_ADMIN = pyotp.random_base32()


def codigo_actual(secreto, desfase=0):
    paso = int(ahora().timestamp()) // 30 + desfase
    return pyotp.TOTP(secreto).generate_otp(paso)


def login_2fa(c, email, password, secreto, desfase=0):
    r = login(c, email, password)
    assert r.status_code == 200 and r.json().get("requiere_2fa"), r.text
    return c.post(
        "/auth/2fa/verificar",
        json={"desafio": r.json()["desafio"], "codigo": codigo_actual(secreto, desfase)},
        headers=CSRF,
    )


def _cargar_observaciones():
    if db.observaciones.count_documents({}):
        return
    ruta = RAIZ / "resultados" / "observaciones_noaa_historico.csv"
    with ruta.open(encoding="utf-8") as archivo:
        documentos = [
            {
                "pixel_id": fila["pixel_id"],
                "fecha": datetime.strptime(fila["fecha"], "%Y-%m-%dT%H:%M:%SZ"),
                "latitud": float(fila["latitud"]),
                "longitud_wgs84": float(fila["longitud_wgs84"]),
                **{k: float(fila[k]) for k in ("sst", "ssta", "hotspot", "dhw")},
            }
            for fila in csv.DictReader(archivo)
        ]
    db.observaciones.insert_many(documentos)


@pytest.fixture(autouse=True)
def base_limpia():
    db.usuarios.delete_many({})
    db.sesiones.delete_many({})
    db.auditoria_accesos.delete_many({})
    db.roles.delete_many({})
    db.configuracion.delete_many({})
    db.documentos.delete_many({})
    db.registro_errores.delete_many({})
    # Las pruebas abren varias sesiones de la misma cuenta; el límite de
    # sesiones simultáneas (por defecto 1) se prueba aparte.
    db.configuracion.insert_one({"_id": "sesion", "sesiones_simultaneas": 5})
    sesion_config.invalidar()
    db.crear_indices()
    _cargar_observaciones()
    limites.reiniciar()
    yield


@pytest.fixture
def cliente():
    with TestClient(app) as c:
        yield c


def nuevo_cliente():
    return TestClient(app)


@pytest.fixture
def crear_cliente():
    clientes = []

    def _crear():
        c = TestClient(app)
        clientes.append(c)
        return c

    yield _crear
    for c in clientes:
        c.close()


def registrar(c, email="ana@ejemplo.org", nombre="Ana Pérez", password="Coral-Seguro-2026", acepta=True):
    return c.post(
        "/auth/registro",
        json={"nombre": nombre, "email": email, "password": password, "acepta_politica": acepta},
        headers=CSRF,
    )


def login(c, email, password):
    return c.post("/auth/login", json={"email": email, "password": password}, headers=CSRF)


@pytest.fixture
def admin(crear_cliente):
    """Cliente con sesión de administrador."""
    db.usuarios.insert_one(
        {
            "nombre": "Admin Coraleum",
            "email": "admin@coraleum.org",
            "password_hash": hash_password(PASSWORD_ADMIN),
            "roles": ["admin"],
            "activo": True,
            "debe_cambiar_password": False,
            "token_version": 0,
            "intentos_fallidos": 0,
            "bloqueado_hasta": None,
            "solicitud": None,
            "creado_en": ahora(),
            "dos_pasos": {
                "activo": True,
                "secreto": dos_pasos.cifrar(SECRETO_ADMIN),
                "ultimo_paso": None,
                "recuperacion": [],
            },
        }
    )
    c = crear_cliente()
    assert login_2fa(c, "admin@coraleum.org", PASSWORD_ADMIN, SECRETO_ADMIN).status_code == 200
    return c
