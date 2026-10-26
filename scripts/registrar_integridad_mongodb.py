import os
import hashlib
from pathlib import Path
from datetime import datetime, timezone
from urllib.parse import quote_plus

import pandas as pd
from pymongo import MongoClient


# ============================================================
# CONFIGURACIÓN
# ============================================================

CSV_FILE = Path("resultados/observaciones_noaa_historico.csv")

MONGO_HOST = "localhost"
MONGO_PORT = 27017

DATABASE_NAME = "proyecto_noaa"
COLLECTION_NAME = "auditoria_integridad"


# ============================================================
# VARIABLES DE ENTORNO
# ============================================================

from dotenv import load_dotenv

load_dotenv()


# ============================================================
# CREDENCIALES
# ============================================================

def obtener_credenciales():

    usuario = os.getenv("MONGO_INITDB_ROOT_USERNAME")
    contraseña = os.getenv("MONGO_INITDB_ROOT_PASSWORD")

    if not usuario:
        raise ValueError(
            "No se encontró MONGO_INITDB_ROOT_USERNAME."
        )

    if not contraseña:
        raise ValueError(
            "No se encontró MONGO_INITDB_ROOT_PASSWORD."
        )

    return usuario, contraseña


# ============================================================
# CALCULAR SHA-256
# ============================================================

def calcular_sha256():

    if not CSV_FILE.exists():

        raise FileNotFoundError(
            f"No existe el archivo: {CSV_FILE}"
        )

    # Saltos de línea normalizados a LF: el hash es el mismo en
    # Windows, Linux, Mac y Docker (ver verificar_integridad.py).
    with open(CSV_FILE, "rb") as archivo:
        contenido = archivo.read()

    return hashlib.sha256(
        contenido.replace(b"\r\n", b"\n")
    ).hexdigest()


# ============================================================
# CONTAR REGISTROS
# ============================================================

def contar_registros():

    df = pd.read_csv(CSV_FILE)

    return len(df)


# ============================================================
# CONECTAR A MONGODB
# ============================================================

def conectar_mongodb():

    usuario, contraseña = obtener_credenciales()

    usuario_codificado = quote_plus(usuario)
    contraseña_codificada = quote_plus(contraseña)

    uri = (
        f"mongodb://{usuario_codificado}:"
        f"{contraseña_codificada}@"
        f"{MONGO_HOST}:{MONGO_PORT}/"
        f"?authSource=admin"
    )

    cliente = MongoClient(
        uri,
        serverSelectionTimeoutMS=5000
    )

    cliente.admin.command("ping")

    print("✅ Conexión con MongoDB confirmada.")

    return cliente


# ============================================================
# REGISTRAR AUDITORÍA
# ============================================================

def registrar_integridad():

    cliente = None

    try:

        print()
        print("=" * 60)
        print("REGISTRO DE INTEGRIDAD EN MONGODB")
        print("=" * 60)

        # ----------------------------------------------------
        # Calcular hash
        # ----------------------------------------------------

        hash_sha256 = calcular_sha256()

        print(
            f"SHA-256: {hash_sha256}"
        )

        # ----------------------------------------------------
        # Contar registros
        # ----------------------------------------------------

        cantidad_registros = contar_registros()

        print(
            f"Registros del CSV: "
            f"{cantidad_registros}"
        )

        # ----------------------------------------------------
        # Conectar
        # ----------------------------------------------------

        cliente = conectar_mongodb()

        db = cliente[DATABASE_NAME]

        collection = db[COLLECTION_NAME]

        # ----------------------------------------------------
        # Crear documento
        # ----------------------------------------------------

        documento = {

            "tipo": "integridad_historico",

            "archivo": CSV_FILE.name,

            "algoritmo": "SHA-256",

            "hash": hash_sha256,

            "registros": cantidad_registros,

            "estado": "OK",

            "fecha_registro": datetime.now(
                timezone.utc
            )
        }

        # ----------------------------------------------------
        # Insertar
        # ----------------------------------------------------

        resultado = collection.insert_one(
            documento
        )

        print(
            f"✅ Auditoría registrada."
        )

        print(
            f"ID: {resultado.inserted_id}"
        )

        # ----------------------------------------------------
        # Mostrar cantidad
        # ----------------------------------------------------

        cantidad_auditorias = collection.count_documents({})

        print(
            f"Registros de auditoría: "
            f"{cantidad_auditorias}"
        )

        print()
        print("=" * 60)
        print("AUDITORÍA COMPLETADA")
        print("=" * 60)

    except Exception as error:

        print()
        print("=" * 60)
        print("❌ ERROR EN LA AUDITORÍA")
        print("=" * 60)

        print(error)

        raise SystemExit(1)

    finally:

        if cliente is not None:

            cliente.close()


# ============================================================
# EJECUCIÓN
# ============================================================

if __name__ == "__main__":

    registrar_integridad()