import os
from pathlib import Path
from urllib.parse import quote_plus
from io import StringIO

import pandas as pd
import requests
from dotenv import load_dotenv
from pymongo import MongoClient

from scripts.sincronizar_mongodb import sincronizar
from scripts.verificar_integridad import actualizar_hash


# ============================================================
# CONFIGURACIÓN
# ============================================================

BASE_DIR = (
    Path(__file__)
    .resolve()
    .parent
    .parent
)

PIXELS_FILE = (
    BASE_DIR
    / "datos"
    / "pixeles_noaa_unicos_para_automatizacion.csv"
)

OUTPUT_FILE = (
    BASE_DIR
    / "resultados"
    / "observaciones_noaa_historico.csv"
)

BASE_URL = (
    "https://oceanwatch.pifsc.noaa.gov/"
    "erddap/griddap"
)


# ============================================================
# DATASETS Y VARIABLES NOAA
# ============================================================

DATASETS = {

    "sst": {
        "dataset": "CRW_sst_v3_1",
        "variable": "analysed_sst"
    },

    "ssta": {
        "dataset": "CRW_sst_anom_v1_0",
        "variable":
            "sea_surface_temperature_anomaly"
    },

    "hotspot": {
        "dataset": "CRW_hs_v1_0",
        "variable": "hotspot"
    },

    "dhw": {
        "dataset": "CRW_dhw_v1_0",
        "variable":
            "degree_heating_week"
    },
}


# ============================================================
# VARIABLES DE ENTORNO
# ============================================================

load_dotenv(
    BASE_DIR / ".env"
)


# ============================================================
# OBTENER ÚLTIMA FECHA DISPONIBLE EN NOAA
# ============================================================

def obtener_ultima_fecha():

    url = (
        f"{BASE_URL}/CRW_sst_v3_1.csv"
        f"?analysed_sst[last][0][0]"
    )

    print(
        "Consultando última fecha "
        "disponible en NOAA..."
    )

    print(
        f"URL: {url}"
    )

    respuesta = requests.get(
        url,
        timeout=60
    )

    respuesta.raise_for_status()

    datos = pd.read_csv(
        StringIO(
            respuesta.text
        )
    )

    if len(datos) == 0:

        raise ValueError(
            "NOAA no devolvió datos."
        )

    columna_fecha = (
        datos["time"]
        .astype(str)
    )

    fechas_validas = columna_fecha[
        columna_fecha.str.match(
            r"^\d{4}-\d{2}-\d{2}"
            r"T\d{2}:\d{2}:\d{2}Z$"
        )
    ]

    if len(fechas_validas) == 0:

        raise ValueError(
            "No se encontró una fecha válida "
            "en la respuesta de NOAA."
        )

    fecha = fechas_validas.iloc[-1]

    print(
        f"Última fecha disponible: {fecha}"
    )

    return fecha


# ============================================================
# OBTENER ÚLTIMA FECHA DE MONGODB
# ============================================================

def obtener_ultima_fecha_mongodb():

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

    try:

        cliente.admin.command(
            "ping"
        )

        db = cliente[
            "proyecto_noaa"
        ]

        coleccion = db[
            "observaciones_noaa"
        ]

        resultado = coleccion.find_one(
            {},
            sort=[
                ("fecha", -1)
            ],
            projection={
                "_id": 0,
                "fecha": 1
            }
        )

        if resultado is None:

            print(
                "MongoDB no contiene "
                "observaciones."
            )

            return None

        ultima_fecha = (
            resultado["fecha"]
        )

        if hasattr(
            ultima_fecha,
            "strftime"
        ):

            ultima_fecha = (
                ultima_fecha.strftime(
                    "%Y-%m-%dT%H:%M:%SZ"
                )
            )

        else:

            ultima_fecha = str(
                ultima_fecha
            )

        print(
            f"Última fecha en MongoDB: "
            f"{ultima_fecha}"
        )

        return ultima_fecha

    finally:

        cliente.close()


# ============================================================
# CONSULTAR UN PÍXEL
# ============================================================

def consultar_noaa(
    dataset,
    variable,
    fecha,
    latitud,
    longitud
):

    url = (
        f"{BASE_URL}/{dataset}.csv"
        f"?{variable}"
        f"[({fecha})]"
        f"[({latitud})]"
        f"[({longitud})]"
    )

    print(
        f"Consultando: {url}"
    )

    respuesta = requests.get(
        url,
        timeout=60
    )

    if respuesta.status_code != 200:

        print(
            "Respuesta de NOAA:"
        )

        print(
            respuesta.text[:1000]
        )

    respuesta.raise_for_status()

    datos = pd.read_csv(
        StringIO(
            respuesta.text
        )
    )

    return datos


# ============================================================
# PROGRAMA PRINCIPAL
# ============================================================

def main():

    # ========================================================
    # LEER LOS 20 PÍXELES
    # ========================================================

    print(
        "Leyendo archivo de píxeles..."
    )

    pixels = pd.read_csv(
        PIXELS_FILE
    )

    print(
        f"Píxeles encontrados: "
        f"{len(pixels)}"
    )

    # ========================================================
    # OBTENER FECHAS
    # ========================================================

    fecha_noaa = (
        obtener_ultima_fecha()
    )

    fecha_mongodb = (
        obtener_ultima_fecha_mongodb()
    )

    print()
    print("=" * 60)
    print("COMPARACIÓN DE FECHAS")
    print("=" * 60)

    print(
        f"Última fecha NOAA:      "
        f"{fecha_noaa}"
    )

    print(
        f"Última fecha MongoDB: "
        f"{fecha_mongodb}"
    )

    # ========================================================
    # VERIFICAR SI HAY DATOS NUEVOS
    # ========================================================

    if (
        fecha_mongodb == fecha_noaa
    ):

        print()
        print(
            "✅ No hay datos nuevos."
        )

        print(
            "No se realizarán consultas "
            "a los 20 píxeles."
        )

        print(
            "El histórico no será modificado."
        )

        return 0

    # ========================================================
    # LISTA PARA RESULTADOS
    # ========================================================

    resultados = []

    # ========================================================
    # PROCESAR CADA PÍXEL
    # ========================================================

    for indice, pixel in pixels.iterrows():

        pixel_id = pixel[
            "pixel_id"
        ]

        latitud = float(
            pixel[
                "latitud_noaa"
            ]
        )

        longitud = float(
            pixel[
                "longitud_noaa_0_360"
            ]
        )

        print()
        print("=" * 60)

        print(
            f"Píxel "
            f"{indice + 1}/"
            f"{len(pixels)}"
        )

        print(
            f"ID: {pixel_id}"
        )

        print(
            f"Latitud: {latitud}"
        )

        print(
            f"Longitud: {longitud}"
        )

        registro = {

            "pixel_id": pixel_id,

            "fecha": fecha_noaa,

            "latitud": latitud,

            "longitud_noaa": longitud,

            "longitud_wgs84":
                float(
                    pixel[
                        "longitud_wgs84"
                    ]
                ),
        }

        # ====================================================
        # CONSULTAR LOS CUATRO PRODUCTOS
        # ====================================================

        for nombre, configuracion in (
            DATASETS.items()
        ):

            try:

                datos = consultar_noaa(
                    configuracion[
                        "dataset"
                    ],

                    configuracion[
                        "variable"
                    ],

                    fecha_noaa,

                    latitud,

                    longitud
                )

                if len(datos) == 0:

                    print(
                        f"⚠ Sin datos para "
                        f"{nombre}"
                    )

                    registro[
                        nombre
                    ] = None

                else:

                    valor = datos.iloc[-1][
                        configuracion[
                            "variable"
                        ]
                    ]

                    registro[
                        nombre
                    ] = valor

                    print(
                        f"{nombre}: {valor}"
                    )

            except Exception as error:

                print(
                    f"❌ Error en "
                    f"{nombre}: {error}"
                )

                registro[
                    nombre
                ] = None

        resultados.append(
            registro
        )

    # ========================================================
    # CREAR DATAFRAME FINAL
    # ========================================================

    resultado_df = pd.DataFrame(
        resultados
    )

    # ========================================================
    # CONVERTIR FECHA A DATETIME
    # ========================================================

    resultado_df["fecha"] = (
        pd.to_datetime(
            resultado_df["fecha"],
            utc=True,
            errors="coerce"
        )
    )

    if resultado_df[
        "fecha"
    ].isna().any():

        raise ValueError(
            "Los resultados contienen "
            "fechas inválidas."
        )

    # ========================================================
    # VALIDAR PRODUCTOS NOAA
    # ========================================================

    variables_noaa = [
        "sst",
        "ssta",
        "hotspot",
        "dhw"
    ]

    registros_incompletos = (
        resultado_df[
            variables_noaa
        ]
        .isna()
        .any(axis=1)
    )

    if registros_incompletos.any():

        print()
        print("=" * 60)
        print(
            "⚠ ADVERTENCIA: "
            "HAY REGISTROS INCOMPLETOS"
        )
        print("=" * 60)

        print(
            resultado_df.loc[
                registros_incompletos,
                ["pixel_id", "fecha"]
                + variables_noaa
            ]
        )

        raise ValueError(
            "No se guardó el nuevo bloque "
            "porque existen registros "
            "incompletos."
        )

    print()
    print(
        "✅ Los 20 píxeles tienen "
        "las 4 variables NOAA."
    )

    # ========================================================
    # SINCRONIZAR CON MONGODB
    # ========================================================

    print()
    print("=" * 60)
    print(
        "SINCRONIZANDO CON MONGODB"
    )
    print("=" * 60)

    resultado_mongodb = sincronizar(
        resultado_df
    )

    print()
    print(
        f"Registros enviados a MongoDB: "
        f"{resultado_mongodb['procesados']}"
    )

    print(
        f"Nuevos registros insertados: "
        f"{resultado_mongodb['insertados']}"
    )

    print(
        f"Registros ya existentes: "
        f"{resultado_mongodb['existentes']}"
    )

    # ========================================================
    # EXPORTAR MONGODB → CSV
    # ========================================================
    #
    # MongoDB es la fuente maestra.
    # El CSV se reconstruye desde MongoDB para evitar
    # inconsistencias entre ambas fuentes.
    # ========================================================

    if resultado_mongodb[
        "insertados"
    ] > 0:

        print()
        print("=" * 60)
        print(
            "EXPORTANDO MONGODB → CSV"
        )
        print("=" * 60)

        from scripts.sincronizar_mongodb import (
            exportar_mongodb_a_csv
        )

        historico_df = (
            exportar_mongodb_a_csv()
        )

        # ====================================================
        # VALIDAR CSV COMPLETO
        # ====================================================

        columnas_esperadas = [
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

        if list(
            historico_df.columns
        ) != columnas_esperadas:

            raise ValueError(
                "El CSV histórico no conserva "
                "las 9 columnas esperadas."
            )

        if historico_df[
            ["pixel_id", "fecha"]
        ].duplicated().any():

            raise ValueError(
                "El CSV histórico contiene "
                "duplicados de "
                "pixel_id + fecha."
            )

        # ====================================================
        # ACTUALIZAR SHA-256
        # ====================================================

        codigo_hash = (
            actualizar_hash()
        )

        if codigo_hash != 0:

            raise RuntimeError(
                "No fue posible actualizar "
                "correctamente el SHA-256."
            )

        print()
        print("=" * 60)
        print(
            "CSV Y SHA-256 ACTUALIZADOS"
        )
        print("=" * 60)

        print(
            f"Registros totales en el CSV: "
            f"{len(historico_df)}"
        )

    else:

        print()
        print(
            "No se actualizó el CSV porque "
            "MongoDB no recibió registros nuevos."
        )

    return 0


# ============================================================
# PUNTO DE ENTRADA
# ============================================================

if __name__ == "__main__":

    try:

        codigo = main()

        raise SystemExit(
            codigo
        )

    except Exception as error:

        print()
        print("=" * 60)
        print(
            "❌ ERROR EN ADQUISICIÓN NOAA"
        )
        print("=" * 60)

        print(
            error
        )

        raise SystemExit(1)