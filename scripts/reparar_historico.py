"""Repara el histórico NOAA afectado por el error de backfill_noaa.py.

Contexto
--------
Una versión de backfill_noaa.py devolvía la respuesta cruda de NOAA
(lista de líneas CSV) en lugar del valor numérico. Esas listas quedaron
guardadas como texto en las columnas sst, ssta, hotspot y dhw, por ejemplo:

    "['time,latitude,longitude,analysed_sst', 'UTC,...', '2026-09-04T12:00:00Z,10.075,284.125,30.83']"

El valor real está en la última columna de la fila de datos. Este script:

1. Lee resultados/observaciones_noaa_historico.csv.
2. Para cada celda no numérica, extrae el valor y VERIFICA que la fecha,
   latitud y longitud de la respuesta coincidan con las de la fila.
   Si algo no coincide, se detiene sin escribir nada.
3. Guarda una copia del original en observaciones_noaa_historico_backup.csv.
4. Escribe el CSV reparado (saltos de línea LF) y actualiza el SHA-256.

Uso (desde la raíz del proyecto):
    python scripts/reparar_historico.py            # solo diagnóstico
    python scripts/reparar_historico.py --aplicar  # repara y actualiza hash
"""

import ast
import csv
import shutil
import sys
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(BASE_DIR))

from scripts.verificar_integridad import calcular_hash  # noqa: E402

CSV_FILE = BASE_DIR / "resultados" / "observaciones_noaa_historico.csv"
BACKUP_FILE = BASE_DIR / "resultados" / "observaciones_noaa_historico_backup.csv"
HASH_FILE = BASE_DIR / "resultados" / "observaciones_noaa_historico.sha256"

VARIABLES = ["sst", "ssta", "hotspot", "dhw"]

# Rangos físicamente plausibles para el Caribe colombiano (control de cordura).
RANGOS = {
    "sst": (15.0, 40.0),
    "ssta": (-10.0, 10.0),
    "hotspot": (-10.0, 10.0),
    "dhw": (0.0, 40.0),
}


class ErrorReparacion(Exception):
    pass


def es_numero(valor):
    try:
        float(valor)
        return True
    except (TypeError, ValueError):
        return False


def extraer_valor(celda, fila, variable):
    """Extrae el número de una respuesta NOAA guardada como texto."""
    try:
        lineas = ast.literal_eval(celda)
    except (ValueError, SyntaxError) as error:
        raise ErrorReparacion(f"{variable}: contenido irreconocible") from error

    if not isinstance(lineas, list) or len(lineas) != 3:
        raise ErrorReparacion(f"{variable}: se esperaban 3 líneas (encabezado, unidades, dato)")

    encabezado = lineas[0].split(",")
    datos = dict(zip(encabezado, lineas[2].split(",")))

    if datos.get("time", "")[:10] != fila["fecha"][:10]:
        raise ErrorReparacion(f"{variable}: la fecha de NOAA no coincide con la fila")
    if abs(float(datos["latitude"]) - float(fila["latitud"])) > 1e-6:
        raise ErrorReparacion(f"{variable}: la latitud de NOAA no coincide con la fila")
    if abs(float(datos["longitude"]) - float(fila["longitud_noaa"])) > 1e-6:
        raise ErrorReparacion(f"{variable}: la longitud de NOAA no coincide con la fila")

    valor = float(datos[encabezado[-1]])
    minimo, maximo = RANGOS[variable]
    if not minimo <= valor <= maximo:
        raise ErrorReparacion(f"{variable}: valor {valor} fuera de rango [{minimo}, {maximo}]")

    return round(valor, 2)


def reparar(filas):
    reparadas = 0
    errores = []
    for numero, fila in enumerate(filas, start=2):
        fila_reparada = False
        for variable in VARIABLES:
            if es_numero(fila[variable]):
                continue
            try:
                fila[variable] = f"{extraer_valor(fila[variable], fila, variable):g}"
                fila_reparada = True
            except ErrorReparacion as error:
                errores.append(f"Línea {numero} ({fila['pixel_id']}, {fila['fecha']}): {error}")
        if fila_reparada:
            reparadas += 1
    return reparadas, errores


def main():
    aplicar = "--aplicar" in sys.argv

    with CSV_FILE.open("r", encoding="utf-8-sig", newline="") as archivo:
        lector = csv.DictReader(archivo)
        columnas = lector.fieldnames
        filas = list(lector)

    reparadas, errores = reparar(filas)

    print(f"Filas totales:     {len(filas)}")
    print(f"Filas a reparar:   {reparadas}")

    if errores:
        print("\nNo se puede reparar automáticamente. Problemas encontrados:")
        for error in errores[:20]:
            print(f"  - {error}")
        sys.exit(1)

    pendientes = [f for f in filas if not all(es_numero(f[v]) for v in VARIABLES)]
    if pendientes:
        print(f"Quedan {len(pendientes)} filas no numéricas. No se escribe nada.")
        sys.exit(1)

    if reparadas == 0:
        print("El histórico ya está correcto. No hay nada que reparar.")
        return

    if not aplicar:
        print("\nDiagnóstico OK. Ejecute con --aplicar para escribir los cambios.")
        return

    shutil.copy2(CSV_FILE, BACKUP_FILE)
    with CSV_FILE.open("w", encoding="utf-8", newline="") as archivo:
        escritor = csv.DictWriter(archivo, fieldnames=columnas, lineterminator="\n")
        escritor.writeheader()
        escritor.writerows(filas)

    digest = calcular_hash(CSV_FILE)
    HASH_FILE.write_text(f"{digest}  observaciones_noaa_historico.csv\n", encoding="utf-8")

    print(f"\nRespaldo del original: {BACKUP_FILE.name}")
    print(f"CSV reparado:          {CSV_FILE.name}")
    print(f"Nuevo SHA-256:         {digest}")
    print("\nSiguiente paso: volver a cargar MongoDB con scripts/migrar_csv_mongodb.py")


if __name__ == "__main__":
    main()
