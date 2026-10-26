import json
import csv


# ============================================================
# ARCHIVOS
# ============================================================

ARCHIVO_GEOJSON = r"datos\areas_coralinas_pnn.geojson"

ARCHIVO_RESUMEN = (
    r"resultados\resumen_dhw_por_area_coralina.csv"
)


# ============================================================
# LEER GEOJSON
# ============================================================

with open(
    ARCHIVO_GEOJSON,
    "r",
    encoding="utf-8"
) as archivo:

    geojson = json.load(archivo)


# ============================================================
# LEER FID DEL RESUMEN TERMICO
# ============================================================

with open(
    ARCHIVO_RESUMEN,
    "r",
    encoding="utf-8-sig",
    newline=""
) as archivo:

    lector = csv.DictReader(archivo)

    fids = {
        int(fila["fid_area_coralina"])
        for fila in lector
    }


# ============================================================
# MOSTRAR FID Y ETIQUETA
# ============================================================

print()
print("=" * 70)
print("FID | ETIQUETA")
print("=" * 70)

for feature in geojson["features"]:

    propiedades = feature["properties"]

    fid = propiedades["FID"]

    if fid in fids:

        etiqueta = propiedades["ETIQUETA"]

        print(
            f"{fid} | {etiqueta}"
        )

print()
print("=" * 70)