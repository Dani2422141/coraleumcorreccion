import os
import sys
from pathlib import Path
from urllib.parse import quote_plus

import pandas as pd
from dotenv import load_dotenv
from pymongo import MongoClient


# ============================================================
# CONFIGURACIÓN
# ============================================================

BASE_DIR = Path(__file__).resolve().parent.parent

CSV_FILE = (
    BASE_DIR
    / "resultados"
    / "observaciones_noaa_historico.csv"
)

DATABASE_NAME = "proyecto_noaa"

COLLECTION_NAME = "observaciones_noaa"

COLUMNAS_REQUERIDAS = [
    "pixel_id",
    "fecha",
    "latitud",
    "longitud_noaa",
    "longitud_wgs84",
    "sst",
    "ssta",
    "hotspot",
    "dhw",
]


# ============================================================
# VARIABLES DE ENTORNO
# ============================================================

load_dotenv(BASE_DIR / ".env")


# ============================================================
# OBTENER ARCHIVO CSV
# ============================================================

def obtener_archivo_csv():

    if len(sys.argv) > 1:

        archivo = Path(sys.argv[1])

        if not archivo.is_absolute():
            archivo = BASE_DIR / archivo

        return archivo

    return CSV_FILE


# ============================================================
# LEER CSV
# ============================================================

def leer_csv():

    print()
    print("=" * 60)
    print("SINCRONIZACIÓN CSV → MONGODB")
    print("=" * 60)

    archivo_csv = obtener_archivo_csv()

    print(f"Archivo: {archivo_csv}")

    if not archivo_csv.exists():

        raise FileNotFoundError(
            f"No existe el archivo: {archivo_csv}"
        )

    df = pd.read_csv(
        archivo_csv
    )

    print(
        f"Registros leídos: {len(df)}"
    )

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

    df = df[COLUMNAS_REQUERIDAS].copy()

    df["fecha"] = pd.to_datetime(
        df["fecha"],
        errors="coerce",
        utc=True
    )

    if df["fecha"].isna().any():

        raise ValueError(
            "Existen fechas inválidas."
        )

    return df


# ============================================================
# CONVERTIR FILA A DOCUMENTO
# ============================================================

def convertir_documento(fila):

    return {
        "pixel_id": str(
            fila["pixel_id"]
        ),

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
        ),
    }


# ============================================================
# CONECTAR A MONGODB
# ============================================================

def conectar_mongodb():

    usuario = os.getenv(
        "MONGO_INITDB_ROOT_USERNAME"
    )

    contraseña = os.getenv(
        "MONGO_INITDB_ROOT_PASSWORD"
    )

    if not usuario:

        raise ValueError(
            "No se encontró "
            "MONGO_INITDB_ROOT_USERNAME."
        )

    if not contraseña:

        raise ValueError(
            "No se encontró "
            "MONGO_INITDB_ROOT_PASSWORD."
        )

    contraseña_codificada = quote_plus(
        contraseña
    )

    uri = (
        f"mongodb://{usuario}:"
        f"{contraseña_codificada}"
        f"@localhost:27017/"
        f"?authSource=admin"
    )

    cliente = MongoClient(
        uri,
        serverSelectionTimeoutMS=5000
    )

    cliente.admin.command(
        "ping"
    )

    print(
        "✅ Conexión con MongoDB confirmada."
    )

    return cliente


# ============================================================
# SINCRONIZAR DATAFRAME → MONGODB
# ============================================================

def sincronizar(df):

    cliente = conectar_mongodb()

    try:

        db = cliente[
            DATABASE_NAME
        ]

        coleccion = db[
            COLLECTION_NAME
        ]

        total = len(df)

        existentes = 0

        insertados = 0

        documentos_insertados = []

        print()
        print("=" * 60)
        print("PROCESANDO DOCUMENTOS")
        print("=" * 60)

        for _, fila in df.iterrows():

            documento = convertir_documento(
                fila
            )

            filtro = {
                "pixel_id": documento[
                    "pixel_id"
                ],
                "fecha": documento[
                    "fecha"
                ],
            }

            encontrado = coleccion.find_one(
                filtro,
                {"_id": 1}
            )

            if encontrado:

                existentes += 1

                continue

            # Guardamos una copia independiente.
            # MongoDB agregará _id al objeto que recibe,
            # pero la copia que devolvemos no tendrá _id.
            documento_para_retorno = (
                documento.copy()
            )

            coleccion.insert_one(
                documento
            )

            documentos_insertados.append(
                documento_para_retorno
            )

            insertados += 1

        total_mongodb = (
            coleccion.count_documents({})
        )

        print()
        print("=" * 60)
        print("RESULTADO DE LA SINCRONIZACIÓN")
        print("=" * 60)

        print(
            f"Registros procesados: {total}"
        )

        print(
            f"Ya existentes:        {existentes}"
        )

        print(
            f"Nuevos insertados:    {insertados}"
        )

        print(
            f"Total en MongoDB:     {total_mongodb}"
        )

        return {
            "procesados": total,
            "existentes": existentes,
            "insertados": insertados,
            "total_mongodb": total_mongodb,
            "documentos_insertados":
                documentos_insertados,
        }

    finally:

        cliente.close()


# ============================================================
# EXPORTAR MONGODB → CSV
# ============================================================

def exportar_mongodb_a_csv():

    cliente = conectar_mongodb()

    try:

        db = cliente[
            DATABASE_NAME
        ]

        coleccion = db[
            COLLECTION_NAME
        ]

        documentos = list(
            coleccion.find(
                {},
                {"_id": 0}
            ).sort(
                [
                    ("fecha", 1),
                    ("pixel_id", 1)
                ]
            )
        )

        if not documentos:

            raise ValueError(
                "MongoDB no contiene "
                "observaciones para exportar."
            )

        df = pd.DataFrame(
            documentos
        )

        df = df[
            COLUMNAS_REQUERIDAS
        ].copy()

        df["fecha"] = (
            pd.to_datetime(
                df["fecha"],
                utc=True
            )
            .dt.strftime(
                "%Y-%m-%dT%H:%M:%SZ"
            )
        )

        df.to_csv(
            CSV_FILE,
            index=False,
            encoding="utf-8-sig"
        )

        print()
        print("=" * 60)
        print("EXPORTACIÓN MONGODB → CSV")
        print("=" * 60)

        print(
            f"Registros exportados: "
            f"{len(df)}"
        )

        print(
            f"Archivo: {CSV_FILE}"
        )

        return df

    finally:

        cliente.close()


# ============================================================
# PROGRAMA PRINCIPAL
# ============================================================

def main():

    try:

        df = leer_csv()

        resultado = sincronizar(
            df
        )

        print()
        print("=" * 60)
        print("SINCRONIZACIÓN COMPLETADA")
        print("=" * 60)

        if resultado["insertados"] == 0:

            print(
                "✅ No había registros nuevos."
            )

        else:

            print(
                "✅ Se insertaron nuevos registros."
            )

    except Exception as error:

        print()
        print("=" * 60)
        print("❌ ERROR EN LA SINCRONIZACIÓN")
        print("=" * 60)

        print(error)

        raise SystemExit(1)


if __name__ == "__main__":

    main()