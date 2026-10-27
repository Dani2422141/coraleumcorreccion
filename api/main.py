"""Punto de entrada de la API de Coraleum."""

import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from pymongo.errors import PyMongoError
from starlette.concurrency import run_in_threadpool
from starlette.exceptions import HTTPException as StarletteHTTPException

from api import config, db, errores
from api.seguridad import borrar_cookies_sesion
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
    allow_headers=["Accept", "Content-Type", config.CSRF_HEADER, "X-Nombre-Archivo"],
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
    respuesta = JSONResponse(status_code=exc.status_code, content=contenido, headers=exc.headers)
    if getattr(exc, "borrar_cookies", False):
        borrar_cookies_sesion(respuesta)
    return respuesta


@app.exception_handler(RequestValidationError)
async def manejar_validacion(request: Request, exc: RequestValidationError):
    # Se informa qué campo falló, pero nunca el valor recibido.
    campos = sorted({str(e["loc"][-1]) for e in exc.errors() if e.get("loc")})
    if campos == ["email"]:
        detalle = "El correo electrónico no es válido."
    else:
        detalle = "Datos inválidos" + (f" en: {', '.join(campos)}." if campos else ".")
    return JSONResponse(status_code=422, content={"detail": detalle, "campos": campos})


@app.exception_handler(PyMongoError)
async def manejar_mongo(request: Request, exc: PyMongoError):
    referencia = await run_in_threadpool(errores.registrar, request, exc, 503)
    return JSONResponse(
        status_code=503,
        content={
            "detail": f"Servicio de datos no disponible temporalmente. Código de referencia: {referencia}.",
            "referencia": referencia,
        },
    )


@app.exception_handler(Exception)
async def manejar_general(request: Request, exc: Exception):
    # Se registra el detalle técnico (api/errores.py); a la persona solo se le
    # entrega un mensaje genérico con el código para reportarlo.
    referencia = await run_in_threadpool(errores.registrar, request, exc, 500)
    return JSONResponse(
        status_code=500,
        content={
            "detail": f"Ocurrió un error interno. Si persiste, reporte el código de referencia {referencia}.",
            "referencia": referencia,
        },
    )


@app.get("/health", tags=["estado"])
def health():
    try:
        db.cliente.admin.command("ping")
        errores.vaciar_pendientes()
        return {"estado": "ok", "mongodb": "conectado"}
    except PyMongoError as error:
        logger.error("Health check: MongoDB no disponible: %s", error)
        return JSONResponse(status_code=503, content={"estado": "error", "mongodb": "no disponible"})


app.include_router(router_auth)
app.include_router(router_admin)
app.include_router(router_datos)
app.include_router(router_datos_publico)
