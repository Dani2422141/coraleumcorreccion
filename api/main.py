import ast
import csv
import json
import logging
import os
from collections import defaultdict
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import quote_plus

from dotenv import load_dotenv
from fastapi import FastAPI, HTTPException, Query, Request
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from pymongo import MongoClient
from pymongo.errors import PyMongoError
from starlette.exceptions import HTTPException as StarletteHTTPException

load_dotenv()

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")
logger = logging.getLogger("coraleum.api")

BASE_DIR = Path(__file__).resolve().parent.parent
ARCHIVO_PIXELES = BASE_DIR / "datos" / "pixeles_noaa_unicos_para_automatizacion.csv"
ARCHIVO_GEOJSON = BASE_DIR / "datos" / "areas_coralinas_pnn.geojson"

MONGO_HOST = os.getenv("MONGO_HOST", "mongodb")
MONGO_PORT = os.getenv("MONGO_PORT", "27017")
MONGO_DATABASE = os.getenv("MONGO_DATABASE", "proyecto_noaa")
MONGO_COLLECTION = os.getenv("MONGO_COLLECTION", "observaciones_noaa")


def construir_mongo_uri():
    """Construye la cadena de conexión sin escribir credenciales en el código.

    Orden de preferencia:
    1. MONGO_URI completa (útil en desarrollo o en un servicio gestionado).
    2. Usuario de aplicación (MONGO_APP_*), con permisos solo sobre la BD.
    3. Usuario administrador (MONGO_INITDB_ROOT_*), solo como respaldo local.
    """
    uri = os.getenv("MONGO_URI")
    if uri:
        return uri

    candidatos = [
        (os.getenv("MONGO_APP_USERNAME"), os.getenv("MONGO_APP_PASSWORD"), MONGO_DATABASE),
        (os.getenv("MONGO_INITDB_ROOT_USERNAME"), os.getenv("MONGO_INITDB_ROOT_PASSWORD"), "admin"),
    ]
    for usuario, clave, auth_source in candidatos:
        if usuario and clave:
            return (
                f"mongodb://{quote_plus(usuario)}:{quote_plus(clave)}"
                f"@{MONGO_HOST}:{MONGO_PORT}/{MONGO_DATABASE}?authSource={auth_source}"
            )

    raise RuntimeError(
        "Configure MONGO_URI, o MONGO_APP_USERNAME/MONGO_APP_PASSWORD, en el entorno (.env)."
    )


DOCS_HABILITADA = os.getenv("ENABLE_DOCS", "false").strip().lower() in {"1", "true", "yes", "si", "sí"}

app = FastAPI(
    title="API Coraleum - Áreas Coralinas",
    description="API para consultar la exposición térmica de las áreas coralinas del PNN Corales del Rosario y de San Bernardo.",
    version="2.1.0",
    # La documentación interactiva solo se expone si se habilita explícitamente.
    docs_url="/docs" if DOCS_HABILITADA else None,
    redoc_url="/redoc" if DOCS_HABILITADA else None,
    openapi_url="/openapi.json" if DOCS_HABILITADA else None,
)

cors_origins = [
    origin.strip()
    for origin in os.getenv("CORS_ORIGINS", "http://localhost:5173,http://localhost:3000").split(",")
    if origin.strip() and origin.strip() != "*"
]
app.add_middleware(
    CORSMiddleware,
    allow_origins=cors_origins,
    allow_credentials=True,
    allow_methods=["GET"],
    allow_headers=["Accept", "Content-Type"],
)


@app.middleware("http")
async def cabeceras_seguridad(request: Request, call_next):
    respuesta = await call_next(request)
    respuesta.headers.setdefault("X-Content-Type-Options", "nosniff")
    respuesta.headers.setdefault("Cache-Control", "no-store")
    return respuesta


# ------------------------------------------------------------
# Manejo uniforme de errores: nunca se devuelven trazas ni
# detalles internos (RS05). Los detalles quedan en el log.
# ------------------------------------------------------------

@app.exception_handler(StarletteHTTPException)
async def manejar_http(request: Request, exc: StarletteHTTPException):
    return JSONResponse(status_code=exc.status_code, content={"detail": exc.detail})


@app.exception_handler(RequestValidationError)
async def manejar_validacion(request: Request, exc: RequestValidationError):
    return JSONResponse(status_code=422, content={"detail": "Parámetros de consulta inválidos."})


@app.exception_handler(PyMongoError)
async def manejar_mongo(request: Request, exc: PyMongoError):
    logger.error("Error de base de datos en %s: %s", request.url.path, exc)
    return JSONResponse(status_code=503, content={"detail": "Servicio de datos no disponible temporalmente."})


@app.exception_handler(Exception)
async def manejar_general(request: Request, exc: Exception):
    logger.exception("Error no controlado en %s", request.url.path)
    return JSONResponse(status_code=500, content={"detail": "Error interno del servidor."})


cliente = MongoClient(construir_mongo_uri(), serverSelectionTimeoutMS=5000)
db = cliente[MONGO_DATABASE]
coleccion = db[MONGO_COLLECTION]

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


@app.get("/health")
def health():
    try:
        cliente.admin.command("ping")
        return {"estado": "ok", "mongodb": "conectado"}
    except PyMongoError as error:
        logger.error("Health check: MongoDB no disponible: %s", error)
        return JSONResponse(status_code=503, content={"estado": "error", "mongodb": "no disponible"})


@app.get("/fechas")
def fechas_disponibles():
    fechas = [formatear_fecha(fecha) for fecha in obtener_fechas()]
    return {
        "total_fechas": len(fechas),
        "fecha_inicial": fechas[0] if fechas else None,
        "fecha_final": fechas[-1] if fechas else None,
        "fechas": fechas,
    }


@app.get("/geojson")
def geojson():
    return GEOJSON


@app.get("/resumen")
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


@app.get("/areas")
def areas(fecha: str | None = FechaQuery):
    fecha_datetime = resolver_fecha(fecha)
    resultados = obtener_areas_por_fecha(fecha_datetime)
    return {
        "fecha_consultada": formatear_fecha(fecha_datetime),
        "total_areas": len(resultados),
        "areas": resultados,
    }


@app.get("/areas/{fid}")
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


@app.get("/areas/{fid}/historico")
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
