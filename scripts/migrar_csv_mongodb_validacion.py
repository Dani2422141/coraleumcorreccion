import os
from pathlib import Path

import pandas as pd


# ============================================================
# CONFIGURACIÓN
# ============================================================

CSV_FILE = Path("resultados/observaciones_noaa_historico.csv")

# Este script solo valida y prepara el CSV (no se conecta a MongoDB).
# Se eliminó la URI "mongodb://localhost:27017/" sin credenciales, que no se usaba.

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
    # Validar cantidad
    # --------------------------------------------------------

    # Validación fija de 40 registros eliminada (era de la carga inicial
    # de 2 fechas); la cantidad se valida al final como píxeles × fechas.
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

    for variable in variables_noaa:
        convertidos = pd.to_numeric(df[variable], errors="coerce")
        no_numericos = int(convertidos.isna().sum())
        if no_numericos > 0:
            raise ValueError(
                f"La columna '{variable}' tiene {no_numericos} valores no "
                f"numéricos. Ejecute scripts/reparar_historico.py."
            )
        df[variable] = convertidos

    print("✅ Todos los valores NOAA son numéricos.")

    # --------------------------------------------------------
    # Validar duplicados
    # --------------------------------------------------------

    duplicados = df.duplicated(
        subset=["pixel_id", "fecha"]
    )

    cantidad_duplicados = duplicados.sum()

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
            "pixel_id": fila["pixel_id"],

            "fecha": fila["fecha"].to_pydatetime(),

            "latitud": float(fila["latitud"]),

            "longitud_noaa": float(
                fila["longitud_noaa"]
            ),

            "longitud_wgs84": float(
                fila["longitud_wgs84"]
            ),

            "sst": float(fila["sst"]),

            "ssta": float(fila["ssta"]),

            "hotspot": float(fila["hotspot"]),

            "dhw": float(fila["dhw"])
        }

        documentos.append(documento)

    return documentos


# ============================================================
# PROGRAMA PRINCIPAL
# ============================================================

def main():

    try:

        df = validar_csv()

        documentos = convertir_documentos(df)

        print()
        print("=" * 60)
        print("VALIDACIÓN COMPLETADA")
        print("=" * 60)

        print(
            f"Documentos preparados para MongoDB: "
            f"{len(documentos)}"
        )

        print()
        print("⚠ MODO VALIDACIÓN")
        print("No se insertará ningún documento.")
        print("El CSV original no será modificado.")

    except Exception as error:

        print()
        print("=" * 60)
        print("❌ ERROR EN LA VALIDACIÓN")
        print("=" * 60)

        print(error)

        raise SystemExit(1)


if __name__ == "__main__":
    main()