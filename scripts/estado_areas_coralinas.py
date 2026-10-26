import ast
import csv
import os
from collections import defaultdict
from datetime import datetime
from urllib.parse import quote_plus

from dotenv import load_dotenv
from pymongo import MongoClient


# ============================================================
# CONFIGURACION
# ============================================================

load_dotenv()

USUARIO = os.getenv("MONGO_INITDB_ROOT_USERNAME")
PASSWORD = os.getenv("MONGO_INITDB_ROOT_PASSWORD")

if not USUARIO or not PASSWORD:
    raise RuntimeError(
        "No se encontraron MONGO_INITDB_ROOT_USERNAME "
        "y/o MONGO_INITDB_ROOT_PASSWORD en .env"
    )

MONGO_URI = (
    f"mongodb://{quote_plus(USUARIO)}:{quote_plus(PASSWORD)}"
    "@localhost:27017/?authSource=admin"
)

ARCHIVO_PIXELES = (
    "datos/pixeles_noaa_unicos_para_automatizacion.csv"
)

ARCHIVO_SALIDA = (
    "resultados/estado_actual_areas_coralinas.csv"
)


# ============================================================
# LEER RELACION PIXEL -> AREA CORALINA
# ============================================================

pixeles_por_area = defaultdict(list)

with open(
    ARCHIVO_PIXELES,
    "r",
    encoding="utf-8-sig",
    newline=""
) as archivo:

    lector = csv.DictReader(archivo)

    for fila in lector:

        pixel_id = fila["pixel_id"]

        fids = ast.literal_eval(
            fila["fid_areas_coralinas"]
        )

        for fid in fids:
            pixeles_por_area[int(fid)].append(pixel_id)


# ============================================================
# CONSULTAR MONGODB
# ============================================================

cliente = MongoClient(MONGO_URI)

db = cliente["proyecto_noaa"]

coleccion = db["observaciones_noaa"]


# ============================================================
# OBTENER FECHAS DISPONIBLES
# ============================================================

fechas = coleccion.distinct("fecha")

if not fechas:
    cliente.close()
    raise RuntimeError(
        "No existen observaciones NOAA en MongoDB."
    )

fechas = sorted(str(fecha) for fecha in fechas)

fecha_inicial = fechas[0]
fecha_final = fechas[-1]


# ============================================================
# AGREGAR DATOS POR PIXEL
# ============================================================

pipeline = [
    {
        "$group": {
            "_id": "$pixel_id",

            "latitud": {
                "$first": "$latitud"
            },

            "longitud_wgs84": {
                "$first": "$longitud_wgs84"
            },

            "dhw_promedio": {
                "$avg": "$dhw"
            },

            "dhw_max": {
                "$max": "$dhw"
            },

            "sst_promedio": {
                "$avg": "$sst"
            },

            "ssta_promedio": {
                "$avg": "$ssta"
            },

            "hotspot_promedio": {
                "$avg": "$hotspot"
            },

            "fecha_inicial": {
                "$min": "$fecha"
            },

            "fecha_final": {
                "$max": "$fecha"
            },

            "numero_observaciones": {
                "$sum": 1
            },
        }
    }
]


datos_pixel = {
    documento["_id"]: documento
    for documento in coleccion.aggregate(pipeline)
}


# ============================================================
# CALCULAR ESTADO POR AREA
# ============================================================

resultados = []

for fid, pixeles in sorted(
    pixeles_por_area.items()
):

    registros = [
        datos_pixel[pixel]
        for pixel in pixeles
        if pixel in datos_pixel
    ]

    if not registros:
        continue

    dhw_promedio = round(
    sum(
        r["dhw_promedio"]
        for r in registros
    )
    / len(registros),
    2
)

    dhw_max = max(
        r["dhw_max"]
        for r in registros
    )

    sst_promedio = (
        sum(
            r["sst_promedio"]
            for r in registros
        )
        / len(registros)
    )

    ssta_promedio = (
        sum(
            r["ssta_promedio"]
            for r in registros
        )
        / len(registros)
    )

    hotspot_promedio = (
        sum(
            r["hotspot_promedio"]
            for r in registros
        )
        / len(registros)
    )

    # ========================================================
    # CLASIFICACION RELATIVA ACTUAL
    # ========================================================

    if dhw_promedio < 3.57:
        categoria = "Baja"

    elif dhw_promedio < 4.74:
        categoria = "Intermedia"

    else:
        categoria = "Alta"

    resultados.append(
        {
            "fid_area_coralina": fid,

            "numero_pixeles": len(
                registros
            ),

            "fecha_inicial": fecha_inicial,

            "fecha_final": fecha_final,

            "dhw_promedio": dhw_promedio,

            "dhw_max_asociado": round(
                dhw_max,
                2
            ),

            "sst_promedio": round(
                sst_promedio,
                2
            ),

            "ssta_promedio": round(
                ssta_promedio,
                2
            ),

            "hotspot_promedio": round(
                hotspot_promedio,
                2
            ),

            "categoria_exposicion_relativa": (
                categoria
            ),
        }
    )


# ============================================================
# GUARDAR RESULTADO
# ============================================================

os.makedirs(
    "resultados",
    exist_ok=True
)

with open(
    ARCHIVO_SALIDA,
    "w",
    encoding="utf-8-sig",
    newline=""
) as archivo:

    campos = [
        "fid_area_coralina",
        "numero_pixeles",
        "fecha_inicial",
        "fecha_final",
        "dhw_promedio",
        "dhw_max_asociado",
        "sst_promedio",
        "ssta_promedio",
        "hotspot_promedio",
        "categoria_exposicion_relativa",
    ]

    escritor = csv.DictWriter(
        archivo,
        fieldnames=campos
    )

    escritor.writeheader()

    escritor.writerows(
        resultados
    )


# ============================================================
# MOSTRAR RESUMEN
# ============================================================

conteo = {
    "Baja": 0,
    "Intermedia": 0,
    "Alta": 0,
}

for fila in resultados:

    conteo[
        fila[
            "categoria_exposicion_relativa"
        ]
    ] += 1


print()

print("=" * 80)
print(
    "ESTADO ACTUAL DE AREAS CORALINAS"
)
print("=" * 80)

print()

print(
    f"Areas procesadas: {len(resultados)}"
)

print(
    f"Fecha inicial:    {fecha_inicial}"
)

print(
    f"Fecha final:      {fecha_final}"
)

print()

print(
    f"Baja:             {conteo['Baja']}"
)

print(
    f"Intermedia:       {conteo['Intermedia']}"
)

print(
    f"Alta:             {conteo['Alta']}"
)

print()

print("=" * 80)

print(
    f"Archivo generado: {ARCHIVO_SALIDA}"
)

print("=" * 80)

cliente.close()