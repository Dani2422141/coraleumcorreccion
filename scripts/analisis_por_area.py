import ast
import csv
import os
from collections import defaultdict
from urllib.parse import quote_plus

from dotenv import load_dotenv
from pymongo import MongoClient


# ============================================================
# CONFIGURACION
# ============================================================

load_dotenv()

USUARIO = os.getenv("MONGO_INITDB_ROOT_USERNAME")
PASSWORD = os.getenv("MONGO_INITDB_ROOT_PASSWORD")

MONGO_URI = (
    f"mongodb://{quote_plus(USUARIO)}:{quote_plus(PASSWORD)}"
    "@localhost:27017/?authSource=admin"
)

ARCHIVO_PIXELES = "datos/pixeles_noaa_unicos_para_automatizacion.csv"
ARCHIVO_SALIDA = "resultados/resumen_dhw_por_area_coralina.csv"


# ============================================================
# VALIDAR CONFIGURACION
# ============================================================

if not USUARIO or not PASSWORD:
    raise RuntimeError(
        "No se encontraron MONGO_INITDB_ROOT_USERNAME "
        "y/o MONGO_INITDB_ROOT_PASSWORD en .env"
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
        }
    }
]

datos_pixel = {
    documento["_id"]: documento
    for documento in coleccion.aggregate(pipeline)
}


# ============================================================
# CALCULAR RESUMEN POR AREA
# ============================================================

resultados = []

for fid, pixeles in pixeles_por_area.items():

    registros = [
        datos_pixel[pixel]
        for pixel in pixeles
        if pixel in datos_pixel
    ]

    if not registros:
        continue

    resultados.append(
        {
            "fid_area_coralina": fid,
            "numero_pixeles": len(registros),

            "dhw_promedio": round(
                sum(
                    r["dhw_promedio"]
                    for r in registros
                ) / len(registros),
                2,
            ),

            "dhw_max_asociado": round(
                max(
                    r["dhw_max"]
                    for r in registros
                ),
                2,
            ),

            "sst_promedio": round(
                sum(
                    r["sst_promedio"]
                    for r in registros
                ) / len(registros),
                2,
            ),

            "ssta_promedio": round(
                sum(
                    r["ssta_promedio"]
                    for r in registros
                ) / len(registros),
                2,
            ),

            "hotspot_promedio": round(
                sum(
                    r["hotspot_promedio"]
                    for r in registros
                ) / len(registros),
                2,
            ),
        }
    )


# ============================================================
# ORDENAR POR DHW
# ============================================================

resultados.sort(
    key=lambda fila: fila["dhw_promedio"],
    reverse=True
)


# ============================================================
# MOSTRAR RESULTADOS
# ============================================================

print()

print("=" * 75)
print("RESUMEN DE EXPOSICION TERMICA POR AREA CORALINA")
print("=" * 75)

print()

for posicion, fila in enumerate(
    resultados,
    start=1
):

    print(
        f"{posicion:2d}. "
        f"FID {fila['fid_area_coralina']:>4} | "
        f"Píxeles: {fila['numero_pixeles']:>2} | "
        f"DHW prom.: {fila['dhw_promedio']:>5.2f} | "
        f"DHW máx.: {fila['dhw_max_asociado']:>5.2f}"
    )

print()


# ============================================================
# GUARDAR CSV
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
        "dhw_promedio",
        "dhw_max_asociado",
        "sst_promedio",
        "ssta_promedio",
        "hotspot_promedio",
    ]

    escritor = csv.DictWriter(
        archivo,
        fieldnames=campos
    )

    escritor.writeheader()
    escritor.writerows(resultados)


# ============================================================
# CERRAR CONEXION
# ============================================================

cliente.close()


# ============================================================
# FINAL
# ============================================================

print("=" * 75)
print(
    f"Archivo generado: {ARCHIVO_SALIDA}"
)
print("=" * 75)