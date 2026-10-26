import sys
import hashlib
from pathlib import Path


# ============================================================
# CONFIGURACIÓN
# ============================================================

BASE_DIR = Path(
    __file__
).resolve().parent.parent

ARCHIVO_DATOS = (
    BASE_DIR
    / "resultados"
    / "observaciones_noaa_historico.csv"
)

ARCHIVO_HASH = (
    BASE_DIR
    / "resultados"
    / "observaciones_noaa_historico.sha256"
)


# ============================================================
# CALCULAR SHA-256
# ============================================================

def calcular_hash(archivo):
    """SHA-256 del contenido con saltos de línea normalizados a LF.

    Windows guarda el CSV con CRLF y Linux/Mac/Docker con LF; sin esta
    normalización el mismo contenido producía hashes distintos según el
    sistema operativo y la verificación fallaba sin que hubiera alteración.
    """

    with open(
        archivo,
        "rb"
    ) as f:

        contenido = f.read()

    return hashlib.sha256(
        contenido.replace(b"\r\n", b"\n")
    ).hexdigest()


# ============================================================
# CREAR HASH INICIAL
# ============================================================

def crear_hash():

    if not ARCHIVO_DATOS.exists():

        print(
            "❌ No existe el archivo histórico:"
        )

        print(
            ARCHIVO_DATOS
        )

        return 1

    hash_actual = calcular_hash(
        ARCHIVO_DATOS
    )

    ARCHIVO_HASH.write_text(
        hash_actual + "\n",
        encoding="utf-8"
    )

    print()
    print("=" * 60)
    print("HASH SHA-256 CREADO")
    print("=" * 60)

    print(
        f"Archivo: {ARCHIVO_DATOS}"
    )

    print(
        f"SHA-256: {hash_actual}"
    )

    print(
        f"Hash guardado en: "
        f"{ARCHIVO_HASH}"
    )

    return 0


# ============================================================
# ACTUALIZAR HASH
# ============================================================

def actualizar_hash():

    if not ARCHIVO_DATOS.exists():

        print(
            "❌ No existe el archivo histórico."
        )

        return 1

    hash_actual = calcular_hash(
        ARCHIVO_DATOS
    )

    ARCHIVO_HASH.write_text(
        hash_actual + "\n",
        encoding="utf-8"
    )

    print()
    print("=" * 60)
    print("HASH SHA-256 ACTUALIZADO")
    print("=" * 60)

    print(
        f"Archivo: {ARCHIVO_DATOS}"
    )

    print(
        f"SHA-256: {hash_actual}"
    )

    print(
        f"Hash guardado en: "
        f"{ARCHIVO_HASH}"
    )

    return 0


# ============================================================
# VERIFICAR INTEGRIDAD
# ============================================================

def verificar_hash():

    if not ARCHIVO_DATOS.exists():

        print(
            "❌ No existe el archivo histórico."
        )

        return 1

    if not ARCHIVO_HASH.exists():

        print()
        print("=" * 60)
        print("⚠️ NO EXISTE HASH DE REFERENCIA")
        print("=" * 60)

        print(
            "Todavía no existe una huella "
            "SHA-256 para comparar."
        )

        print(
            "Ejecuta el programa con "
            "--crear para establecer "
            "la referencia inicial."
        )

        return 2

    hash_actual = calcular_hash(
        ARCHIVO_DATOS
    )

    # Acepta tanto "hash" como el formato estándar "hash  nombre_archivo"
    # (el que escribe backfill_noaa.py). Antes se comparaba la línea
    # completa y la verificación fallaba después de cada backfill.
    contenido_hash = (
        ARCHIVO_HASH
        .read_text(
            encoding="utf-8"
        )
        .split()
    )

    hash_guardado = (
        contenido_hash[0].lower()
        if contenido_hash
        else ""
    )

    print()
    print("=" * 60)
    print("VERIFICACIÓN DE INTEGRIDAD")
    print("=" * 60)

    print(
        f"Hash guardado: {hash_guardado}"
    )

    print(
        f"Hash actual:   {hash_actual}"
    )

    if hash_actual == hash_guardado:

        print()
        print(
            "✅ INTEGRIDAD CONFIRMADA"
        )

        print(
            "El archivo histórico no presenta "
            "modificaciones detectables."
        )

        return 0

    print()
    print("=" * 60)
    print("🚨 ALERTA DE INTEGRIDAD")
    print("=" * 60)

    print(
        "El archivo histórico NO coincide "
        "con el hash registrado."
    )

    print(
        "El archivo pudo haber sido modificado."
    )

    print(
        "NO se continuará con la adquisición NOAA."
    )

    return 1


# ============================================================
# PROGRAMA PRINCIPAL
# ============================================================

if __name__ == "__main__":

    if len(sys.argv) != 2:

        print()
        print("Uso:")

        print(
            "python scripts/"
            "verificar_integridad.py --crear"
        )

        print(
            "python scripts/"
            "verificar_integridad.py --check"
        )

        print(
            "python scripts/"
            "verificar_integridad.py --actualizar"
        )

        sys.exit(1)

    modo = sys.argv[1]

    if modo == "--crear":

        codigo = crear_hash()

        sys.exit(codigo)

    elif modo == "--check":

        codigo = verificar_hash()

        sys.exit(codigo)

    elif modo == "--actualizar":

        codigo = actualizar_hash()

        sys.exit(codigo)

    else:

        print(
            f"❌ Opción desconocida: {modo}"
        )

        sys.exit(1)