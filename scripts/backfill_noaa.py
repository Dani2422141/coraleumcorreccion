import csv
import hashlib
import os
import sys
from datetime import datetime, timezone, timedelta

import requests
from pymongo import MongoClient
from dotenv import load_dotenv


BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

ENV_FILE = os.path.join(BASE_DIR, ".env")

PIXELS_FILE = os.path.join(
    BASE_DIR,
    "datos",
    "pixeles_noaa_unicos_para_automatizacion.csv",
)

OUTPUT_FILE = os.path.join(
    BASE_DIR,
    "resultados",
    "observaciones_noaa_historico.csv",
)

HASH_FILE = os.path.join(
    BASE_DIR,
    "resultados",
    "observaciones_noaa_historico.sha256",
)

BASE_URL = "https://oceanwatch.pifsc.noaa.gov/erddap/griddap"


DATASETS = {
    "sst": {
        "dataset": "CRW_sst_v3_1",
        "variable": "analysed_sst",
    },
    "ssta": {
        "dataset": "CRW_sst_anom_v1_0",
        "variable": "sea_surface_temperature_anomaly",
    },
    "hotspot": {
        "dataset": "CRW_hs_v1_0",
        "variable": "hotspot",
    },
    "dhw": {
        "dataset": "CRW_dhw_v1_0",
        "variable": "degree_heating_week",
    },
}


REQUIRED_FIELDS = [
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


def conectar_mongodb():
    load_dotenv(ENV_FILE)

    username = os.getenv("MONGO_INITDB_ROOT_USERNAME")
    password = os.getenv("MONGO_INITDB_ROOT_PASSWORD")

    if not username or not password:
        raise RuntimeError(
            "No se encontraron MONGO_INITDB_ROOT_USERNAME "
            "y MONGO_INITDB_ROOT_PASSWORD en el archivo .env."
        )

    client = MongoClient(
        "mongodb://localhost:27017/",
        username=username,
        password=password,
        authSource="admin",
    )

    client.admin.command("ping")

    return client["proyecto_noaa"]


def cargar_pixeles():
    if not os.path.exists(PIXELS_FILE):
        raise FileNotFoundError(
            f"No existe el archivo de pixeles: {PIXELS_FILE}"
        )

    pixeles = []

    with open(
        PIXELS_FILE,
        "r",
        encoding="utf-8-sig",
        newline="",
    ) as archivo:

        lector = csv.DictReader(archivo)

        columnas_requeridas = {
            "pixel_id",
            "latitud_noaa",
            "longitud_noaa_0_360",
            "longitud_wgs84",
        }

        columnas_archivo = set(lector.fieldnames or [])

        faltantes = columnas_requeridas - columnas_archivo

        if faltantes:
            raise RuntimeError(
                "Faltan columnas en el archivo de pixeles: "
                + ", ".join(sorted(faltantes))
            )

        for fila in lector:
            pixeles.append(
                {
                    "pixel_id": fila["pixel_id"],
                    "latitud": float(fila["latitud_noaa"]),
                    "longitud_noaa": float(
                        fila["longitud_noaa_0_360"]
                    ),
                    "longitud_wgs84": float(
                        fila["longitud_wgs84"]
                    ),
                }
            )

    if not pixeles:
        raise RuntimeError(
            "El archivo de pixeles esta vacio."
        )

    return pixeles

NOAA_SESSION = requests.Session()

def consultar_noaa(
    dataset,
    variable,
    fecha,
    latitud,
    longitud,
):
    url = (
        f"{BASE_URL}/{dataset}.csv?"
        f"{variable}[({fecha})][({latitud})][({longitud})]"
    )

    max_intentos = 4
    timeout = 120

    for intento in range(1, max_intentos + 1):
        try:
            respuesta = NOAA_SESSION.get(
                url,
                timeout=timeout,
            )

            respuesta.raise_for_status()

            # Respuesta correcta: salir del ciclo de reintentos y continuar
            # con la extracción del valor numérico (más abajo).
            # ERROR CORREGIDO: antes aquí había
            #   return respuesta.text.strip().splitlines()
            # lo que devolvía la respuesta cruda de NOAA (una lista de
            # líneas) y se guardaba en MongoDB/CSV en lugar del número.
            break

        except (
            requests.exceptions.ConnectTimeout,
            requests.exceptions.ReadTimeout,
            requests.exceptions.ConnectionError,
        ) as exc:

            if intento == max_intentos:
                raise RuntimeError(
                    f"No fue posible consultar NOAA despues de "
                    f"{max_intentos} intentos. "
                    f"Dataset: {dataset}, "
                    f"fecha: {fecha}, "
                    f"latitud: {latitud}, "
                    f"longitud: {longitud}"
                ) from exc

            espera = 5 * intento

            print(
                f"    NOAA no respondio en el intento "
                f"{intento}/{max_intentos}. "
                f"Reintentando en {espera} segundos..."
            )

            import time
            time.sleep(espera)

    lineas = respuesta.text.strip().splitlines()

    if len(lineas) < 2:
        raise RuntimeError(
            f"NOAA no devolvio datos para "
            f"{dataset}, {fecha}, "
            f"{latitud}, {longitud}"
        )

    lector = csv.DictReader(lineas)

    for fila in lector:

        valor = fila.get(variable)

        if valor is None:
            continue

        valor = valor.strip()

        if valor == "":
            continue

        try:
            return float(valor)
        except ValueError:
            continue

    raise RuntimeError(
        f"NOAA no devolvio un valor numerico valido para "
        f"{dataset}, {fecha}, "
        f"{latitud}, {longitud}"
    )


def obtener_fecha_utc(fecha):
    try:
        return datetime.strptime(
            fecha,
            "%Y-%m-%dT%H:%M:%SZ",
        ).replace(
            tzinfo=timezone.utc
        )
    except ValueError as exc:
        raise ValueError(
            f"Formato de fecha invalido: {fecha}. "
            f"Debe ser YYYY-MM-DDTHH:MM:SSZ"
        ) from exc


def generar_fechas(
    fecha_inicio,
    fecha_fin,
):
    inicio = obtener_fecha_utc(
        fecha_inicio
    )

    fin = obtener_fecha_utc(
        fecha_fin
    )

    if inicio > fin:
        raise ValueError(
            "La fecha inicial no puede ser posterior "
            "a la fecha final."
        )

    fecha_actual = inicio

    while fecha_actual <= fin:

        yield fecha_actual.strftime(
            "%Y-%m-%dT%H:%M:%SZ"
        )

        fecha_actual += timedelta(
            days=1
        )


def construir_observacion(
    pixel,
    fecha,
):
    print(
        f"  Consultando pixel "
        f"{pixel['pixel_id']} "
        f"para {fecha}..."
    )

    sst = consultar_noaa(
        DATASETS["sst"]["dataset"],
        DATASETS["sst"]["variable"],
        fecha,
        pixel["latitud"],
        pixel["longitud_noaa"],
    )

    ssta = consultar_noaa(
        DATASETS["ssta"]["dataset"],
        DATASETS["ssta"]["variable"],
        fecha,
        pixel["latitud"],
        pixel["longitud_noaa"],
    )

    hotspot = consultar_noaa(
        DATASETS["hotspot"]["dataset"],
        DATASETS["hotspot"]["variable"],
        fecha,
        pixel["latitud"],
        pixel["longitud_noaa"],
    )

    dhw = consultar_noaa(
        DATASETS["dhw"]["dataset"],
        DATASETS["dhw"]["variable"],
        fecha,
        pixel["latitud"],
        pixel["longitud_noaa"],
    )

    observacion = {
        "pixel_id": pixel["pixel_id"],
        "fecha": obtener_fecha_utc(fecha),
        "latitud": pixel["latitud"],
        "longitud_noaa": pixel["longitud_noaa"],
        "longitud_wgs84": pixel["longitud_wgs84"],
        "sst": sst,
        "ssta": ssta,
        "hotspot": hotspot,
        "dhw": dhw,
    }

    for campo in REQUIRED_FIELDS:

        if campo not in observacion:
            raise RuntimeError(
                f"Falta el campo requerido: {campo}"
            )

    return observacion


def actualizar_csv_desde_mongodb(db):

    documentos = list(
        db.observaciones_noaa.find(
            {},
            {
                "_id": 0
            },
        ).sort(
            [
                ("fecha", 1),
                ("pixel_id", 1),
            ]
        )
    )

    with open(
        OUTPUT_FILE,
        "w",
        encoding="utf-8",
        newline="",
    ) as archivo:

        escritor = csv.DictWriter(
            archivo,
            fieldnames=REQUIRED_FIELDS,
        )

        escritor.writeheader()

        for documento in documentos:

            fila = documento.copy()

            if isinstance(
                fila["fecha"],
                datetime,
            ):
                fila["fecha"] = (
                    fila["fecha"]
                    .astimezone(timezone.utc)
                    .strftime(
                        "%Y-%m-%dT%H:%M:%SZ"
                    )
                )

            escritor.writerow(
                fila
            )

    with open(
        OUTPUT_FILE,
        "rb",
    ) as archivo:

        # Saltos de línea normalizados a LF (mismo criterio que
        # verificar_integridad.py) para que el hash no dependa del SO.
        digest = hashlib.sha256(
            archivo.read().replace(b"\r\n", b"\n")
        ).hexdigest()

    with open(
        HASH_FILE,
        "w",
        encoding="utf-8",
    ) as archivo:

        archivo.write(
            f"{digest}  "
            f"observaciones_noaa_historico.csv\n"
        )

    print()
    print(
        f"CSV actualizado: "
        f"{OUTPUT_FILE}"
    )

    print(
        f"SHA-256: {digest}"
    )


def main():

    if len(sys.argv) not in (3, 4):

        print(
            "Uso:\n"
            "python scripts\\backfill_noaa.py "
            "FECHA_INICIO FECHA_FIN [--dry-run]\n\n"
            "Ejemplo de prueba:\n"
            "python scripts\\backfill_noaa.py "
            "2026-08-28T12:00:00Z "
            "2026-08-28T12:00:00Z "
            "--dry-run\n\n"
            "Ejemplo de ejecucion:\n"
            "python scripts\\backfill_noaa.py "
            "2026-08-28T12:00:00Z "
            "2026-09-03T12:00:00Z"
        )

        return 1

    fecha_inicio = sys.argv[1]

    fecha_fin = sys.argv[2]

    dry_run = (
        len(sys.argv) == 4
        and sys.argv[3] == "--dry-run"
    )

    if (
        len(sys.argv) == 4
        and sys.argv[3] != "--dry-run"
    ):
        print(
            "Error: el unico argumento adicional "
            "permitido es --dry-run."
        )

        return 1

    fechas = list(
        generar_fechas(
            fecha_inicio,
            fecha_fin,
        )
    )

    print()
    print("=" * 60)
    print("BACKFILL HISTORICO NOAA")
    print("=" * 60)
    print()

    print(
        f"Fecha inicial: {fecha_inicio}"
    )

    print(
        f"Fecha final:   {fecha_fin}"
    )

    print(
        f"Cantidad de fechas: {len(fechas)}"
    )

    if dry_run:

        print()
        print(
            "*** MODO DRY-RUN ***"
        )

        print(
            "NO se modificara MongoDB."
        )

        print(
            "NO se modificara el CSV."
        )

        print(
            "NO se modificara el SHA-256."
        )

    pixeles = cargar_pixeles()

    print()
    print(
        f"Cantidad de pixeles: "
        f"{len(pixeles)}"
    )

    print(
        f"Observaciones esperadas: "
        f"{len(fechas) * len(pixeles)}"
    )

    print()

    db = conectar_mongodb()

    print(
        "Conexion con MongoDB: OK"
    )

    observaciones_nuevas = []

    omitidas = 0

    for fecha in fechas:

        print()
        print("=" * 60)
        print(
            f"FECHA: {fecha}"
        )
        print("=" * 60)

        fecha_dt = obtener_fecha_utc(
            fecha
        )

        for pixel in pixeles:

            existe = (
                db.observaciones_noaa.find_one(
                    {
                        "pixel_id":
                            pixel["pixel_id"],
                        "fecha":
                            fecha_dt,
                    },
                    {
                        "_id": 1
                    },
                )
            )

            if existe:

                print(
                    f"  OMITIDA "
                    f"{pixel['pixel_id']} "
                    f"(ya existe)"
                )

                omitidas += 1

                continue

            observacion = (
                construir_observacion(
                    pixel,
                    fecha,
                )
            )

            observaciones_nuevas.append(
                observacion
            )

    print()
    print("=" * 60)
    print("VALIDACION PREVIA")
    print("=" * 60)
    print()

    print(
        f"Observaciones nuevas preparadas: "
        f"{len(observaciones_nuevas)}"
    )

    print(
        f"Observaciones omitidas: "
        f"{omitidas}"
    )

    if not observaciones_nuevas:

        print()
        print(
            "No hay observaciones nuevas."
        )

        return 0

    for observacion in observaciones_nuevas:

        for campo in REQUIRED_FIELDS:

            if campo not in observacion:

                raise RuntimeError(
                    f"Falta el campo requerido: "
                    f"{campo}"
                )

    if dry_run:

        print()
        print("=" * 60)
        print("DRY-RUN COMPLETADO")
        print("=" * 60)
        print()

        print(
            "Las consultas NOAA fueron "
            "realizadas correctamente."
        )

        print(
            "Los datos fueron validados."
        )

        print()
        print(
            "NO se insertaron datos en MongoDB."
        )

        print(
            "NO se modifico el CSV."
        )

        print(
            "NO se modifico el SHA-256."
        )

        return 0

    print()
    print("=" * 60)
    print("INSERTANDO EN MONGODB")
    print("=" * 60)
    print()

    resultado = (
        db.observaciones_noaa.insert_many(
            observaciones_nuevas,
            ordered=True,
        )
    )

    print(
        f"Insertadas correctamente: "
        f"{len(resultado.inserted_ids)}"
    )

    actualizar_csv_desde_mongodb(
        db
    )

    print()
    print("=" * 60)
    print("BACKFILL COMPLETADO CORRECTAMENTE")
    print("=" * 60)

    return 0


if __name__ == "__main__":

    try:

        raise SystemExit(
            main()
        )

    except Exception as exc:

        print()
        print("=" * 60)
        print("ERROR EN BACKFILL")
        print("=" * 60)
        print()

        print(
            str(exc)
        )

        raise