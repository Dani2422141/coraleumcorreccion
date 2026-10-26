import csv
import os


# ============================================================
# CONFIGURACION
# ============================================================

ARCHIVO_ENTRADA = (
    "resultados/resumen_dhw_por_area_coralina.csv"
)

ARCHIVO_SALIDA = (
    "resultados/resumen_dhw_por_area_coralina_clasificado.csv"
)


# ============================================================
# LEER RESULTADOS
# ============================================================

with open(
    ARCHIVO_ENTRADA,
    "r",
    encoding="utf-8-sig",
    newline=""
) as archivo:

    lector = csv.DictReader(archivo)
    resultados = list(lector)


# ============================================================
# CLASIFICAR EXPOSICION RELATIVA
# ============================================================

for fila in resultados:

    dhw = float(fila["dhw_promedio"])

    if dhw < 3.57:
        categoria = "Baja"

    elif dhw < 4.74:
        categoria = "Intermedia"

    else:
        categoria = "Alta"

    fila["categoria_exposicion_relativa"] = categoria


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

    campos = list(resultados[0].keys())

    escritor = csv.DictWriter(
        archivo,
        fieldnames=campos
    )

    escritor.writeheader()
    escritor.writerows(resultados)


# ============================================================
# RESUMEN
# ============================================================

conteo = {
    "Baja": 0,
    "Intermedia": 0,
    "Alta": 0
}

for fila in resultados:
    conteo[fila["categoria_exposicion_relativa"]] += 1


print()
print("=" * 75)
print("CLASIFICACION RELATIVA DE EXPOSICION TERMICA")
print("=" * 75)
print()

print(f"Baja:       {conteo['Baja']} áreas")
print(f"Intermedia: {conteo['Intermedia']} áreas")
print(f"Alta:       {conteo['Alta']} áreas")

print()

print("=" * 75)
print(f"Archivo generado: {ARCHIVO_SALIDA}")
print("=" * 75)