import os

import geopandas as gpd
import pandas as pd
import matplotlib.pyplot as plt
from matplotlib.patches import Patch


# ============================================================
# CONFIGURACION
# ============================================================

ARCHIVO_GEOJSON = (
    r"datos\areas_coralinas_pnn.geojson"
)

ARCHIVO_DATOS = (
    "resultados/estado_actual_areas_coralinas.csv"
)

ARCHIVO_SALIDA = (
    "resultados/mapa_exposicion_termica_areas_coralinas.png"
)


# ============================================================
# LEER GEOMETRIAS
# ============================================================

gdf = gpd.read_file(
    ARCHIVO_GEOJSON
)


# ============================================================
# LEER DATOS ACTUALES
# ============================================================

df = pd.read_csv(
    ARCHIVO_DATOS
)


# ============================================================
# PREPARAR IDENTIFICADOR
# ============================================================

gdf["FID"] = pd.to_numeric(
    gdf["FID"],
    errors="coerce"
).astype("Int64")

df["fid_area_coralina"] = pd.to_numeric(
    df["fid_area_coralina"],
    errors="coerce"
).astype("Int64")


# ============================================================
# UNIR GEOMETRIA + DATOS
# ============================================================

mapa = gdf.merge(
    df,
    left_on="FID",
    right_on="fid_area_coralina",
    how="left"
)


# ============================================================
# VERIFICAR UNION
# ============================================================

areas_sin_datos = mapa[
    mapa["dhw_promedio"].isna()
]

if len(areas_sin_datos) > 0:

    print()
    print(
        "ADVERTENCIA: existen áreas sin datos:"
    )

    print(
        areas_sin_datos["FID"].tolist()
    )

    print()


# ============================================================
# CREAR FIGURA
# ============================================================

fig, ax = plt.subplots(
    figsize=(12, 10)
)


# ============================================================
# DIBUJAR AREAS SEGUN CATEGORIA
# ============================================================

categorias = [
    "Baja",
    "Intermedia",
    "Alta"
]

colores = {
    "Baja": "#2ca25f",
    "Intermedia": "#fec44f",
    "Alta": "#de2d26"
}


for categoria in categorias:

    seleccion = mapa[
        mapa[
            "categoria_exposicion_relativa"
        ] == categoria
    ]

    if not seleccion.empty:

        seleccion.plot(
            ax=ax,
            color=colores[categoria],
            edgecolor="black",
            linewidth=0.6,
        )


# ============================================================
# AREAS SIN DATOS
# ============================================================

sin_datos = mapa[
    mapa["categoria_exposicion_relativa"].isna()
]

if not sin_datos.empty:

    sin_datos.plot(
        ax=ax,
        color="lightgray",
        edgecolor="black",
        linewidth=0.6,
    )


# ============================================================
# TITULO
# ============================================================

fecha_final = (
    df["fecha_final"]
    .iloc[0]
)

ax.set_title(
    "Exposición térmica relativa de áreas coralinas\n"
    f"PNN Corales del Rosario y de San Bernardo — "
    f"datos hasta {fecha_final}",
    fontsize=15,
    pad=15,
)


# ============================================================
# EJES
# ============================================================

ax.set_xlabel(
    "Longitud"
)

ax.set_ylabel(
    "Latitud"
)


# ============================================================
# LEYENDA
# ============================================================

leyenda = [
    Patch(
        facecolor=colores["Baja"],
        edgecolor="black",
        label="Baja"
    ),

    Patch(
        facecolor=colores["Intermedia"],
        edgecolor="black",
        label="Intermedia"
    ),

    Patch(
        facecolor=colores["Alta"],
        edgecolor="black",
        label="Alta"
    ),
]

if not sin_datos.empty:

    leyenda.append(
        Patch(
            facecolor="lightgray",
            edgecolor="black",
            label="Sin datos"
        )
    )


ax.legend(
    handles=leyenda,
    title="Exposición térmica relativa",
    loc="best"
)


# ============================================================
# CUADRICULA
# ============================================================

ax.grid(
    True,
    linestyle="--",
    linewidth=0.5,
    alpha=0.5
)


# ============================================================
# AJUSTAR MAPA
# ============================================================

plt.tight_layout()


# ============================================================
# GUARDAR
# ============================================================

os.makedirs(
    "resultados",
    exist_ok=True
)

plt.savefig(
    ARCHIVO_SALIDA,
    dpi=300,
    bbox_inches="tight"
)

plt.close()


# ============================================================
# FINAL
# ============================================================

print()
print("=" * 80)
print(
    "MAPA DE EXPOSICION TERMICA GENERADO"
)
print("=" * 80)
print()

print(
    f"Áreas en el mapa: {len(mapa)}"
)

print(
    f"Archivo generado: {ARCHIVO_SALIDA}"
)

print()

print("=" * 80)