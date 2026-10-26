import os
from pathlib import Path
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
COLLECTION_NAME = "pixeles"


# ============================================================
# CARGAR VARIABLES DE ENTORNO
# ============================================================

from dotenv import load_dotenv

load_dotenv()


# ============================================================
# OBTENER CREDENCIALES
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
# LEER Y VALIDAR PÍXELES
# ============================================================

def obtener_pixeles():

    if not CSV_FILE.exists():

        raise FileNotFoundError(
            f"No existe el archivo: {CSV_FILE}"
        )

    df = pd.read_csv(CSV_FILE)

    columnas = [
        "pixel_id",
        "latitud",
        "longitud_noaa",
        "longitud_wgs84"
    ]

    for columna in columnas:

        if columna not in df.columns:

            raise ValueError(
                f"Falta la columna: {columna}"
            )

    # --------------------------------------------------------
    # Obtener un registro por píxel
    # --------------------------------------------------------

    pixeles = df[
        columnas
    ].drop_duplicates(
        subset=["pixel_id"]
    )

    print(
        f"Píxeles encontrados en CSV: "
        f"{len(pixeles)}"
    )

    if len(pixeles) != 20:

        raise ValueError(
            f"Se esperaban 20 píxeles y se encontraron "
            f"{len(pixeles)}."
        )

    # --------------------------------------------------------
    # Verificar que cada píxel tenga coordenadas únicas
    # --------------------------------------------------------

    coordenadas = df.groupby(
        "pixel_id"
    )[
        [
            "latitud",
            "longitud_noaa",
            "longitud_wgs84"
        ]
    ].nunique()

    if (coordenadas > 1).any().any():

        raise ValueError(
            "Existe al menos un píxel con coordenadas inconsistentes."
        )

    print(
        "✅ Coordenadas consistentes por píxel."
    )

    documentos = []

    for _, fila in pixeles.iterrows():

        documentos.append({
            "pixel_id": str(fila["pixel_id"]),

            "latitud": float(
                fila["latitud"]
            ),

            "longitud_noaa": float(
                fila["longitud_noaa"]
            ),

            "longitud_wgs84": float(
                fila["longitud_wgs84"]
            )
        })

    return documentos


# ============================================================
# MIGRAR PÍXELES
# ============================================================

def migrar_pixeles():

    cliente = None

    try:

        print()
        print("=" * 60)
        print("MIGRACIÓN DE PÍXELES")
        print("=" * 60)

        documentos = obtener_pixeles()

        cliente = conectar_mongodb()

        db = cliente[DATABASE_NAME]

        collection = db[COLLECTION_NAME]

        existentes = collection.count_documents({})

        print(
            f"Documentos existentes antes: "
            f"{existentes}"
        )

        # ----------------------------------------------------
        # Evitar duplicar información
        # ----------------------------------------------------

        if existentes != 0:

            raise ValueError(
                "La colección pixeles no está vacía. "
                "No se realizará la migración."
            )

        # ----------------------------------------------------
        # Insertar
        # ----------------------------------------------------

        resultado = collection.insert_many(
            documentos,
            ordered=True
        )

        print(
            f"✅ Píxeles insertados: "
            f"{len(resultado.inserted_ids)}"
        )

        # ----------------------------------------------------
        # Índice único
        # ----------------------------------------------------

        indice = collection.create_index(
            {"pixel_id": 1},
            unique=True
        )

        print(
            f"✅ Índice creado: {indice}"
        )

        # ----------------------------------------------------
        # Validación final
        # ----------------------------------------------------

        cantidad = collection.count_documents({})

        print(
            f"Píxeles en MongoDB: {cantidad}"
        )

        if cantidad != 20:

            raise ValueError(
                f"Se esperaban 20 píxeles y hay "
                f"{cantidad}."
            )

        print("✅ Los 20 píxeles fueron migrados correctamente.")

        print()
        print("=" * 60)
        print("MIGRACIÓN DE PÍXELES COMPLETADA")
        print("=" * 60)

    except Exception as error:

        print()
        print("=" * 60)
        print("❌ ERROR EN LA MIGRACIÓN DE PÍXELES")
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

    migrar_pixeles()