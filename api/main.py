"""Punto de entrada de la API de Coraleum."""

import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from pymongo.errors import PyMongoError
from starlette.exceptions import HTTPException as StarletteHTTPException

from api import config, db
from api.rutas_admin import router as router_admin
from api.rutas_auth import router as router_auth
from api.rutas_datos import router as router_datos
from api.rutas_datos import router_publico as router_datos_publico

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")
logger = logging.getLogger("coraleum.api")


@asynccontextmanager
async def ciclo_de_vida(app):
    db.crear_indices()
    yield


app = FastAPI(
    title="API Coraleum - Áreas Coralinas",
    description="API para consultar la exposición térmica de las áreas coralinas del PNN Corales del Rosario y de San Bernardo.",
    version="3.0.0",
    lifespan=ciclo_de_vida,
    # La documentación interactiva solo se expone si se habilita explícitamente.
    docs_url="/docs" if config.DOCS_HABILITADA else None,
    redoc_url="/redoc" if config.DOCS_HABILITADA else None,
    openapi_url="/openapi.json" if config.DOCS_HABILITADA else None,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=config.ORIGENES_PERMITIDOS,
    allow_credentials=True,
    allow_methods=["GET", "POST", "PATCH"],
    allow_headers=["Accept", "Content-Type", config.CSRF_HEADER],
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
    contenido = {"detail": exc.detail}
    accion = (exc.headers or {}).get("X-Coraleum-Accion")
    if accion:
        contenido["accion"] = accion
    return JSONResponse(status_code=exc.status_code, content=contenido, headers=exc.headers)


@app.exception_handler(RequestValidationError)
async def manejar_validacion(request: Request, exc: RequestValidationError):
    # Se informa qué campo falló, pero nunca el valor recibido.
    campos = sorted({str(e["loc"][-1]) for e in exc.errors() if e.get("loc")})
    detalle = "Datos inválidos" + (f" en: {', '.join(campos)}." if campos else ".")
    return JSONResponse(status_code=422, content={"detail": detalle, "campos": campos})


@app.exception_handler(PyMongoError)
async def manejar_mongo(request: Request, exc: PyMongoError):
    logger.error("Error de base de datos en %s: %s", request.url.path, exc)
    return JSONResponse(status_code=503, content={"detail": "Servicio de datos no disponible temporalmente."})


@app.exception_handler(Exception)
async def manejar_general(request: Request, exc: Exception):
    logger.exception("Error no controlado en %s", request.url.path)
    return JSONResponse(status_code=500, content={"detail": "Error interno del servidor."})


@app.get("/health", tags=["estado"])
def health():
    try:
        db.cliente.admin.command("ping")
        return {"estado": "ok", "mongodb": "conectado"}
    except PyMongoError as error:
        logger.error("Health check: MongoDB no disponible: %s", error)
        return JSONResponse(status_code=503, content={"estado": "error", "mongodb": "no disponible"})


app.include_router(router_auth)
app.include_router(router_admin)
app.include_router(router_datos)
app.include_router(router_datos_publico)
