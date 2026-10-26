import os
from pathlib import Path

import pandas as pd
from pymongo import MongoClient
from pymongo.errors import BulkWriteError
from dotenv import load_dotenv

load_dotenv()


# ============================================================
# CONFIGURACIÓN
# ============================================================

CSV_FILE = Path("resultados/observaciones_noaa_historico.csv")

MONGO_HOST = "localhost"
MONGO_PORT = 27017

DATABASE_NAME = "proyecto_noaa"

COLLECTION_NAME = "observaciones_noaa"


# ============================================================
# COLUMNAS ESPERADAS
# ============================================================

COLUMNAS_REQUERIDAS = [
    "pixel_id",
    "fecha",
    "latitud",
    "longitud_noaa",
    "longitud_wgs84",
    "sst",
    "ssta",
    "hotspot",
    "dhw"
]


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
# VALIDAR CSV
# ============================================================

def validar_csv():

    print()
    print("=" * 60)
    print("VALIDACIÓN DEL CSV PARA MIGRACIÓN")
    print("=" * 60)

    if not CSV_FILE.exists():

        raise FileNotFoundError(
            f"No existe el archivo: {CSV_FILE}"
        )

    print(f"Archivo: {CSV_FILE}")

    df = pd.read_csv(CSV_FILE)

    print(f"Registros encontrados: {len(df)}")

    # --------------------------------------------------------
    # Validar columnas
    # --------------------------------------------------------

    columnas_faltantes = [
        columna
        for columna in COLUMNAS_REQUERIDAS
        if columna not in df.columns
    ]

    if columnas_faltantes:

        raise ValueError(
            "Faltan columnas requeridas: "
            + ", ".join(columnas_faltantes)
        )

    print("✅ Columnas requeridas presentes.")

    # --------------------------------------------------------
    # (Se eliminó la validación fija de "exactamente 40 registros",
    # que correspondía a la primera carga de 2 fechas. La cantidad
    # ahora se valida al final como píxeles × fechas.)
    # --------------------------------------------------------

    print(f"Registros en el CSV: {len(df)}")

    # --------------------------------------------------------
    # Convertir fecha
    # --------------------------------------------------------

    df["fecha"] = pd.to_datetime(
        df["fecha"],
        errors="coerce",
        utc=True
    )

    if df["fecha"].isna().any():

        raise ValueError(
            "Existen registros con fechas inválidas."
        )

    print("✅ Todas las fechas son válidas.")

    # --------------------------------------------------------
    # Validar datos NOAA
    # --------------------------------------------------------

    variables_noaa = [
        "sst",
        "ssta",
        "hotspot",
        "dhw"
    ]

    if df[variables_noaa].isna().any().any():

        raise ValueError(
            "Existen valores NOAA faltantes."
        )

    print("✅ No existen valores NOAA faltantes.")

    # Los valores deben ser NÚMEROS. Esta validación faltaba y habría
    # detectado las 520 filas con texto crudo de NOAA que dejó el error
    # de backfill_noaa.py.
    for variable in variables_noaa:

        convertidos = pd.to_numeric(
            df[variable],
            errors="coerce"
        )

        no_numericos = int(convertidos.isna().sum())

        if no_numericos > 0:

            raise ValueError(
                f"La columna '{variable}' tiene {no_numericos} "
                f"valores no numéricos. Ejecute "
                f"scripts/reparar_historico.py antes de migrar."
            )

        df[variable] = convertidos

    print("✅ Todos los valores NOAA son numéricos.")

    # --------------------------------------------------------
    # Validar duplicados
    # --------------------------------------------------------

    duplicados = df.duplicated(
        subset=["pixel_id", "fecha"]
    )

    cantidad_duplicados = int(duplicados.sum())

    print(
        f"Duplicados pixel_id + fecha: "
        f"{cantidad_duplicados}"
    )

    if cantidad_duplicados > 0:

        raise ValueError(
            "El CSV contiene duplicados "
            "pixel_id + fecha."
        )

    print("✅ No existen duplicados.")

    # --------------------------------------------------------
    # Validar píxeles
    # --------------------------------------------------------

    cantidad_pixeles = df["pixel_id"].nunique()

    print(
        f"Píxeles únicos: {cantidad_pixeles}"
    )

    if cantidad_pixeles != 20:

        raise ValueError(
            f"Se esperaban 20 píxeles y se encontraron "
            f"{cantidad_pixeles}."
        )

    print("✅ Se encontraron exactamente 20 píxeles.")

    # --------------------------------------------------------
    # Validar fechas
    # --------------------------------------------------------

    cantidad_fechas = df["fecha"].nunique()

    print(
        f"Fechas únicas: {cantidad_fechas}"
    )

    # Cada fecha debe tener un registro por cada píxel (serie completa).
    esperados = cantidad_pixeles * cantidad_fechas

    if len(df) != esperados:

        raise ValueError(
            f"Serie incompleta: se esperaban {esperados} registros "
            f"({cantidad_pixeles} píxeles × {cantidad_fechas} fechas) "
            f"y se encontraron {len(df)}."
        )

    print(
        f"✅ Serie completa: {cantidad_pixeles} píxeles × "
        f"{cantidad_fechas} fechas = {esperados} registros."
    )

    return df


# ============================================================
# CONVERTIR DATAFRAME A DOCUMENTOS MONGODB
# ============================================================

def convertir_documentos(df):

    documentos = []

    for _, fila in df.iterrows():

        documento = {
            "pixel_id": str(fila["pixel_id"]),

            "fecha": fila["fecha"].to_pydatetime(),

            "latitud": float(
                fila["latitud"]
            ),

            "longitud_noaa": float(
                fila["longitud_noaa"]
            ),

            "longitud_wgs84": float(
                fila["longitud_wgs84"]
            ),

            "sst": float(
                fila["sst"]
            ),

            "ssta": float(
                fila["ssta"]
            ),

            "hotspot": float(
                fila["hotspot"]
            ),

            "dhw": float(
                fila["dhw"]
            )
        }

        documentos.append(documento)

    return documentos


# ============================================================
# CONECTAR A MONGODB
# ============================================================

def conectar_mongodb():

    usuario, contraseña = obtener_credenciales()

    from urllib.parse import quote_plus

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
# INSERTAR DOCUMENTOS
# ============================================================

def insertar_documentos(collection, documentos):

    print()
    print("=" * 60)
    print("MIGRACIÓN A MONGODB")
    print("=" * 60)

    print(
        f"Documentos a insertar: {len(documentos)}"
    )

    try:

        resultado = collection.insert_many(
            documentos,
            ordered=True
        )

        insertados = len(
            resultado.inserted_ids
        )

        print(
            f"✅ Documentos insertados: {insertados}"
        )

        return insertados

    except BulkWriteError as error:

        print()
        print("❌ ERROR DURANTE LA INSERCIÓN")

        print(error.details)

        raise


# ============================================================
# VALIDAR RESULTADO FINAL
# ============================================================

def validar_migracion(collection, cantidad_esperada):

    print()
    print("=" * 60)
    print("VALIDACIÓN FINAL DE MONGODB")
    print("=" * 60)

    cantidad = collection.count_documents({})

    print(
        f"Documentos encontrados: {cantidad}"
    )

    if cantidad != cantidad_esperada:

        raise ValueError(
            f"Se esperaban {cantidad_esperada} documentos "
            f"y MongoDB contiene {cantidad}."
        )

    duplicados = list(
        collection.aggregate([
            {
                "$group": {
                    "_id": {
                        "pixel_id": "$pixel_id",
                        "fecha": "$fecha"
                    },
                    "cantidad": {
                        "$sum": 1
                    }
                }
            },
            {
                "$match": {
                    "cantidad": {
                        "$gt": 1
                    }
                }
            }
        ])
    )

    if duplicados:

        raise ValueError(
            "MongoDB contiene duplicados "
            "pixel_id + fecha."
        )

    print("✅ Cantidad de documentos correcta.")
    print("✅ No existen duplicados.")
    print("✅ Migración validada correctamente.")


# ============================================================
# PROGRAMA PRINCIPAL
# ============================================================

def main():

    cliente = None

    try:

        # ----------------------------------------------------
        # 1. Validar CSV
        # ----------------------------------------------------

        df = validar_csv()

        # ----------------------------------------------------
        # 2. Convertir documentos
        # ----------------------------------------------------

        documentos = convertir_documentos(df)

        print()
        print(
            f"Documentos preparados: "
            f"{len(documentos)}"
        )

        # ----------------------------------------------------
        # 3. Conectar MongoDB
        # ----------------------------------------------------

        cliente = conectar_mongodb()

        db = cliente[DATABASE_NAME]

        collection = db[COLLECTION_NAME]

        # ----------------------------------------------------
        # 4. Comprobar estado antes de insertar
        # ----------------------------------------------------

        existentes = collection.count_documents({})

        print(
            f"Documentos existentes antes "
            f"de la migración: {existentes}"
        )

        if existentes != 0:

            raise ValueError(
                "La colección no está vacía. "
                "No se realizará la migración."
            )

        # ----------------------------------------------------
        # 5. Insertar
        # ----------------------------------------------------

        insertar_documentos(
            collection,
            documentos
        )

        # ----------------------------------------------------
        # 6. Validar resultado
        # ----------------------------------------------------

        validar_migracion(
            collection,
            len(documentos)
        )

        print()
        print("=" * 60)
        print("PROCESO COMPLETADO CORRECTAMENTE")
        print("=" * 60)

        print(
            f"Registros migrados: "
            f"{len(documentos)}"
        )

        print(
            f"Base de datos: "
            f"{DATABASE_NAME}"
        )

        print(
            f"Colección: "
            f"{COLLECTION_NAME}"
        )

        print()
        print(
            "El CSV original no fue modificado."
        )

    except Exception as error:

        print()
        print("=" * 60)
        print("❌ ERROR EN LA MIGRACIÓN")
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

    main()