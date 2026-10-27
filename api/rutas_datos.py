"""Rutas de consulta de datos ambientales (fechas, áreas, histórico, resumen).

Cada ruta exige un permiso (`datos.consultar` o `datos.historico`): la
protección se aplica en el backend, por lo que no basta con ocultar los
botones en la interfaz.
"""

import ast
import csv
import json
import time
from collections import defaultdict
from datetime import datetime, timezone
from pathlib import Path

from fastapi import APIRouter, Depends, HTTPException, Query

from api.db import observaciones as coleccion
from api.deps import requerir_permiso

BASE_DIR = Path(__file__).resolve().parent.parent
ARCHIVO_PIXELES = BASE_DIR / "datos" / "pixeles_noaa_unicos_para_automatizacion.csv"
ARCHIVO_GEOJSON = BASE_DIR / "datos" / "areas_coralinas_pnn.geojson"

router = APIRouter(tags=["datos"], dependencies=[Depends(requerir_permiso("datos.consultar", "datos.historico"))])

CONSULTAR = Depends(requerir_permiso("datos.consultar"))
HISTORICO = Depends(requerir_permiso("datos.historico"))

# Solo cifras agregadas (sin valores ambientales): las usa la página de
# inicio, que es pública.
router_publico = APIRouter(tags=["público"])

pixeles_por_area = defaultdict(list)
with ARCHIVO_PIXELES.open("r", encoding="utf-8-sig", newline="") as archivo:
    for fila in csv.DictReader(archivo):
        pixel_id = fila["pixel_id"]
        for fid in ast.literal_eval(fila["fid_areas_coralinas"]):
            pixeles_por_area[int(fid)].append(pixel_id)


def cargar_geojson():
    with ARCHIVO_GEOJSON.open("r", encoding="utf-8") as archivo:
        return json.load(archivo)


GEOJSON = cargar_geojson()


def obtener_fechas():
    return sorted(coleccion.distinct("fecha"))


def obtener_ultima_fecha():
    fechas = obtener_fechas()
    return fechas[-1] if fechas else None


def formatear_fecha(fecha):
    if fecha is None:
        return None
    return fecha.strftime("%Y-%m-%d %H:%M:%S")


def convertir_fecha(fecha):
    try:
        value = fecha.strip()
        if len(value) == 10:
            parsed = datetime.fromisoformat(value)
        else:
            parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
        if parsed.tzinfo is not None:
            parsed = parsed.astimezone(timezone.utc).replace(tzinfo=None)
        return parsed
    except ValueError as error:
        raise HTTPException(
            status_code=400,
            detail="Formato de fecha inválido. Use YYYY-MM-DD o YYYY-MM-DD HH:MM:SS.",
        ) from error


def resolver_fecha(fecha):
    """Valida la fecha recibida y verifica que exista en los datos.

    Si no se envía fecha, se usa la más reciente.
    """
    if fecha is None:
        return obtener_ultima_fecha()
    fecha_datetime = convertir_fecha(fecha)
    if fecha_datetime not in obtener_fechas():
        raise HTTPException(status_code=404, detail="No hay datos para la fecha solicitada.")
    return fecha_datetime


def obtener_categoria(dhw):
    # Clasificación relativa del proyecto; no es una alerta oficial NOAA.
    if dhw < 3.57:
        return "Baja"
    if dhw < 4.74:
        return "Intermedia"
    return "Alta"


def resumir_area(fid, registros, fecha_datetime):
    """Combina los valores por píxel de un área en un único resumen."""
    total = len(registros)
    dhw_promedio = round(sum(r["dhw"] for r in registros) / total, 2)
    return {
        "fid_area_coralina": fid,
        "numero_pixeles": total,
        "dhw_promedio": dhw_promedio,
        "dhw_max_asociado": round(max(r["dhw"] for r in registros), 2),
        "sst_promedio": round(sum(r["sst"] for r in registros) / total, 2),
        "ssta_promedio": round(sum(r["ssta"] for r in registros) / total, 2),
        "hotspot_promedio": round(sum(r["hotspot"] for r in registros) / total, 2),
        "categoria_exposicion_relativa": obtener_categoria(dhw_promedio),
        "fecha": formatear_fecha(fecha_datetime),
        "fecha_inicial": formatear_fecha(fecha_datetime),
        "fecha_final": formatear_fecha(fecha_datetime),
    }


def agrupar_por_pixel(match):
    """Promedia las variables por (fecha, píxel) para el filtro indicado."""
    pipeline = [
        {"$match": match},
        {
            "$group": {
                "_id": {"fecha": "$fecha", "pixel_id": "$pixel_id"},
                "dhw": {"$avg": "$dhw"},
                "sst": {"$avg": "$sst"},
                "ssta": {"$avg": "$ssta"},
                "hotspot": {"$avg": "$hotspot"},
            }
        },
    ]
    return list(coleccion.aggregate(pipeline))


def obtener_areas_por_fecha(fecha_datetime):
    if fecha_datetime is None:
        return []

    datos_pixel = {
        documento["_id"]["pixel_id"]: documento
        for documento in agrupar_por_pixel({"fecha": fecha_datetime})
    }

    resultados = []
    for fid, pixeles in sorted(pixeles_por_area.items()):
        registros = [datos_pixel[pixel] for pixel in pixeles if pixel in datos_pixel]
        if registros:
            resultados.append(resumir_area(fid, registros, fecha_datetime))
    return resultados


def validar_fid(fid):
    if fid not in pixeles_por_area:
        raise HTTPException(status_code=404, detail="No se encontró el área solicitada.")


FechaQuery = Query(
    default=None,
    max_length=25,
    description="Fecha exacta: YYYY-MM-DD o YYYY-MM-DD HH:MM:SS. Si se omite, se usa la más reciente.",
)


@router.get("/fechas")
def fechas_disponibles():
    # Las fechas las usan tanto el Explorador como el histórico.
    fechas = [formatear_fecha(fecha) for fecha in obtener_fechas()]
    return {
        "total_fechas": len(fechas),
        "fecha_inicial": fechas[0] if fechas else None,
        "fecha_final": fechas[-1] if fechas else None,
        "fechas": fechas,
    }


@router.get("/geojson")
def geojson():
    return GEOJSON


@router.get("/resumen", dependencies=[CONSULTAR])
def resumen():
    fechas = obtener_fechas()
    areas_actuales = obtener_areas_por_fecha(fechas[-1] if fechas else None)
    counts = {"Baja": 0, "Intermedia": 0, "Alta": 0}
    for area_item in areas_actuales:
        categoria = area_item["categoria_exposicion_relativa"]
        counts[categoria] = counts.get(categoria, 0) + 1

    if areas_actuales:
        total = len(areas_actuales)
        promedio = {
            "dhw": round(sum(a["dhw_promedio"] for a in areas_actuales) / total, 2),
            "sst": round(sum(a["sst_promedio"] for a in areas_actuales) / total, 2),
            "ssta": round(sum(a["ssta_promedio"] for a in areas_actuales) / total, 2),
            "hotspot": round(sum(a["hotspot_promedio"] for a in areas_actuales) / total, 2),
        }
        dhw_max = round(max(a["dhw_max_asociado"] for a in areas_actuales), 2)
    else:
        promedio = {"dhw": 0, "sst": 0, "ssta": 0, "hotspot": 0}
        dhw_max = 0

    return {
        "total_areas": len(pixeles_por_area),
        "areas_con_datos": len(areas_actuales),
        "total_pixeles": len(coleccion.distinct("pixel_id")),
        "total_fechas": len(fechas),
        "fecha_final": formatear_fecha(fechas[-1]) if fechas else None,
        "fecha_inicial": formatear_fecha(fechas[0]) if fechas else None,
        "clasificacion": counts,
        "promedios": promedio,
        "dhw_max": dhw_max,
    }


@router.get("/areas", dependencies=[CONSULTAR])
def areas(fecha: str | None = FechaQuery):
    fecha_datetime = resolver_fecha(fecha)
    resultados = obtener_areas_por_fecha(fecha_datetime)
    return {
        "fecha_consultada": formatear_fecha(fecha_datetime),
        "total_areas": len(resultados),
        "areas": resultados,
    }


@router.get("/areas/{fid}", dependencies=[CONSULTAR])
def area(fid: int, fecha: str | None = FechaQuery):
    """Detalle de un área para la fecha seleccionada (o la más reciente)."""
    validar_fid(fid)
    fecha_datetime = resolver_fecha(fecha)
    pixeles = set(pixeles_por_area[fid])
    registros = [
        documento
        for documento in agrupar_por_pixel({"fecha": fecha_datetime, "pixel_id": {"$in": list(pixeles)}})
    ]
    if not registros:
        raise HTTPException(status_code=404, detail="El área no tiene datos para la fecha solicitada.")
    return resumir_area(fid, registros, fecha_datetime)


@router.get("/areas/{fid}/historico", dependencies=[HISTORICO])
def historico_area(fid: int):
    """Serie histórica del área en UNA sola consulta a MongoDB."""
    validar_fid(fid)

    por_fecha = defaultdict(list)
    for documento in agrupar_por_pixel({"pixel_id": {"$in": pixeles_por_area[fid]}}):
        por_fecha[documento["_id"]["fecha"]].append(documento)

    historico = [
        resumir_area(fid, registros, fecha_datetime)
        for fecha_datetime, registros in sorted(por_fecha.items())
    ]
    return {
        "fid_area_coralina": fid,
        "total_registros": len(historico),
        "historico": historico,
    }


@router_publico.get("/estadisticas")
def estadisticas_publicas():
    fechas = obtener_fechas()
    return {
        "total_areas": len(pixeles_por_area),
        "total_pixeles": len({p for pixeles in pixeles_por_area.values() for p in pixeles}),
        "total_fechas": len(fechas),
    }


# ------------------------------------------------------------
# "El parque hoy" (público): solo cifras AGREGADAS de todo el parque,
# sin datos por área. El detalle sigue siendo para investigadores.
# ------------------------------------------------------------

# Escala de alertas de NOAA Coral Reef Watch (versión de diciembre de 2023).
NIVELES_NOAA = (
    "sin_estres", "vigilancia", "advertencia",
    "alerta_1", "alerta_2", "alerta_3", "alerta_4", "alerta_5",
)


def nivel_noaa(hotspot, dhw):
    """Nivel de alerta de blanqueamiento.

    Los niveles de alerta se asignan por el DHW acumulado (como el máximo de
    7 días de NOAA, que mantiene la alerta aunque el HotSpot del día baje).
    """
    if dhw >= 20:
        return "alerta_5"
    if dhw >= 16:
        return "alerta_4"
    if dhw >= 12:
        return "alerta_3"
    if dhw >= 8:
        return "alerta_2"
    if dhw >= 4:
        return "alerta_1"
    if hotspot >= 1:
        return "advertencia"
    if hotspot > 0:
        return "vigilancia"
    return "sin_estres"


_cache_parque = {"valor": None, "hasta": 0.0}


@router_publico.get("/estado-parque")
def estado_parque():
    momento = time.monotonic()
    if _cache_parque["valor"] is not None and momento < _cache_parque["hasta"]:
        return _cache_parque["valor"]

    fechas = obtener_fechas()
    if not fechas:
        return {"disponible": False}
    ultima = fechas[-1]
    areas = obtener_areas_por_fecha(ultima)
    niveles = {clave: 0 for clave in NIVELES_NOAA}
    for area in areas:
        niveles[nivel_noaa(area["hotspot_promedio"], area["dhw_promedio"])] += 1

    serie = []
    pipeline = [
        {"$group": {"_id": {"fecha": "$fecha", "pixel_id": "$pixel_id"}, "dhw": {"$avg": "$dhw"}, "sst": {"$avg": "$sst"}}},
        {"$group": {"_id": "$_id.fecha", "dhw_promedio": {"$avg": "$dhw"}, "dhw_maximo": {"$max": "$dhw"}, "sst": {"$avg": "$sst"}}},
        {"$sort": {"_id": 1}},
    ]
    for fila in coleccion.aggregate(pipeline):
        serie.append(
            {
                "fecha": formatear_fecha(fila["_id"]),
                "dhw_promedio": round(fila["dhw_promedio"], 2),
                "dhw_maximo": round(fila["dhw_maximo"], 2),
                "sst_promedio": round(fila["sst"], 2),
            }
        )

    total = len(areas) or 1
    valor = {
        "disponible": True,
        "fecha": formatear_fecha(ultima),
        "total_areas": len(areas),
        "niveles": niveles,
        "dhw_promedio": round(sum(a["dhw_promedio"] for a in areas) / total, 2),
        "dhw_maximo": round(max((a["dhw_max_asociado"] for a in areas), default=0), 2),
        "sst_promedio": round(sum(a["sst_promedio"] for a in areas) / total, 2),
        "serie": serie[-60:],
    }
    _cache_parque.update(valor=valor, hasta=momento + 300)
    return valor
