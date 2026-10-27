"""Copias de seguridad de la base de datos de Coraleum (MongoDB en Docker).

Uso, desde la carpeta del proyecto y con Docker encendido:

    python scripts/respaldo_mongodb.py respaldar            # crea una copia nueva
    python scripts/respaldo_mongodb.py listar               # muestra las copias
    python scripts/respaldo_mongodb.py verificar ARCHIVO    # comprueba una copia
    python scripts/respaldo_mongodb.py restaurar ARCHIVO    # reemplaza la BD con la copia

Las copias quedan en la carpeta respaldos/ (excluida de Git), comprimidas,
con su huella SHA-256 y verificadas tras crearlas. Se conservan las últimas
14 (cámbielo con --conservar N).

⚠️ Las copias contienen los datos de los usuarios (correos, hashes de
contraseñas, auditoría). Guárdelas en un lugar privado y nunca las suba a Git.
"""

import argparse
import hashlib
import os
import secrets
import subprocess
import sys
from datetime import datetime
from pathlib import Path

from dotenv import load_dotenv

BASE_DIR = Path(__file__).resolve().parent.parent
CARPETA = BASE_DIR / "respaldos"
CONTENEDOR = os.getenv("CORALEUM_CONTENEDOR_MONGO", "proyecto-noaa-mongodb")
PREFIJO = "coraleum_"
EXTENSION = ".archive.gz"


class ErrorRespaldo(Exception):
    pass


# ------------------------------------------------------------
# Utilidades
# ------------------------------------------------------------

def docker(*argumentos, entrada=None):
    try:
        resultado = subprocess.run(
            ["docker", *argumentos],
            input=entrada,
            capture_output=True,
            text=True,
            check=False,
        )
    except FileNotFoundError as error:
        raise ErrorRespaldo("No se encontró el comando 'docker'. ¿Está instalado Docker Desktop?") from error
    if resultado.returncode != 0:
        mensaje = (resultado.stderr or resultado.stdout or "").strip()
        raise ErrorRespaldo(f"docker {argumentos[0]} falló: {mensaje[-500:]}")
    return resultado.stdout


def credenciales():
    load_dotenv(BASE_DIR / ".env")
    usuario = os.getenv("MONGO_INITDB_ROOT_USERNAME")
    clave = os.getenv("MONGO_INITDB_ROOT_PASSWORD")
    base = os.getenv("MONGO_DATABASE", "proyecto_noaa")
    if not usuario or not clave:
        raise ErrorRespaldo("Faltan MONGO_INITDB_ROOT_USERNAME / MONGO_INITDB_ROOT_PASSWORD en el archivo .env.")
    return usuario, clave, base


def sha256(ruta):
    h = hashlib.sha256()
    with open(ruta, "rb") as archivo:
        for bloque in iter(lambda: archivo.read(1024 * 1024), b""):
            h.update(bloque)
    return h.hexdigest()


def verificar_contenedor():
    estado = docker("inspect", "-f", "{{.State.Running}}", CONTENEDOR).strip()
    if estado != "true":
        raise ErrorRespaldo(f"El contenedor {CONTENEDOR} no está encendido. Ejecute: docker compose up -d")


class ConfigTemporal:
    """Archivo de configuración con la contraseña DENTRO del contenedor.

    Así la contraseña no aparece en la línea de comandos (visible para
    otros procesos). Se borra siempre al terminar.
    """

    def __init__(self, usuario, clave):
        # Ruta DENTRO del contenedor de MongoDB: nombre aleatorio y se borra al terminar.
        self.ruta = f"/tmp/coraleum_cfg_{secrets.token_hex(8)}.yaml"  # nosec B108
        # Comillas simples de YAML: solo hay que duplicar las comillas simples.
        clave_yaml = clave.replace("'", "''")
        self.contenido = f"password: '{clave_yaml}'\n"
        self.uri = f"mongodb://{usuario}@localhost:27017/?authSource=admin"

    def __enter__(self):
        docker("exec", "-i", CONTENEDOR, "sh", "-c", f"umask 077 && cat > {self.ruta}", entrada=self.contenido)
        return self

    def __exit__(self, *_):
        try:
            docker("exec", CONTENEDOR, "rm", "-f", self.ruta)
        except ErrorRespaldo:
            pass


def ruta_archivo(nombre):
    ruta = Path(nombre)
    if not ruta.is_absolute() and not ruta.exists():
        ruta = CARPETA / nombre
    if not ruta.exists():
        raise ErrorRespaldo(f"No existe el archivo {nombre}.")
    return ruta


# ------------------------------------------------------------
# Operaciones
# ------------------------------------------------------------

def verificar(ruta, silencioso=False):
    """Comprueba la huella SHA-256 y que MongoDB pueda leer el archivo."""
    ruta = ruta_archivo(ruta)
    huella = ruta.with_name(ruta.name + ".sha256")
    if not huella.exists():
        raise ErrorRespaldo(f"Falta la huella {huella.name}.")
    esperado = huella.read_text(encoding="utf-8").split()[0]
    if sha256(ruta) != esperado:
        raise ErrorRespaldo(f"La huella SHA-256 de {ruta.name} NO coincide: el archivo está dañado o fue modificado.")

    usuario, clave, _ = credenciales()
    # Ruta DENTRO del contenedor de MongoDB: nombre aleatorio y se borra al terminar.
    destino = f"/tmp/coraleum_verif_{secrets.token_hex(6)}.gz"  # nosec B108
    docker("cp", str(ruta), f"{CONTENEDOR}:{destino}")
    try:
        with ConfigTemporal(usuario, clave) as cfg:
            # --dryRun lee todo el archivo sin escribir en la base de datos.
            docker(
                "exec", CONTENEDOR, "mongorestore", f"--uri={cfg.uri}", f"--config={cfg.ruta}",
                f"--archive={destino}", "--gzip", "--dryRun", "--quiet",
            )
    finally:
        docker("exec", CONTENEDOR, "rm", "-f", destino)
    if not silencioso:
        print(f"✅ {ruta.name}: huella correcta y archivo legible.")
    return True


def respaldar(conservar):
    verificar_contenedor()
    usuario, clave, base = credenciales()
    CARPETA.mkdir(exist_ok=True)

    marca = datetime.now().strftime("%Y%m%d_%H%M%S")
    nombre = f"{PREFIJO}{marca}{EXTENSION}"
    # Ruta DENTRO del contenedor de MongoDB: nombre aleatorio y se borra al terminar.
    temporal = f"/tmp/{nombre}"  # nosec B108
    destino = CARPETA / nombre

    print(f"Creando copia de la base '{base}'...")
    try:
        with ConfigTemporal(usuario, clave) as cfg:
            docker(
                "exec", CONTENEDOR, "mongodump", f"--uri={cfg.uri}", f"--config={cfg.ruta}",
                f"--db={base}", f"--archive={temporal}", "--gzip", "--quiet",
            )
        docker("cp", f"{CONTENEDOR}:{temporal}", str(destino))
    finally:
        try:
            docker("exec", CONTENEDOR, "rm", "-f", temporal)
        except ErrorRespaldo:
            pass

    if not destino.exists() or destino.stat().st_size == 0:
        raise ErrorRespaldo("La copia quedó vacía.")
    destino.with_name(destino.name + ".sha256").write_text(f"{sha256(destino)}  {destino.name}\n", encoding="utf-8")

    verificar(destino, silencioso=True)
    print(f"✅ Copia creada y verificada: respaldos/{destino.name} ({destino.stat().st_size / 1024:.1f} KB)")
    rotar(conservar)
    return destino


def listar():
    copias = sorted(CARPETA.glob(f"{PREFIJO}*{EXTENSION}")) if CARPETA.exists() else []
    if not copias:
        print("No hay copias en respaldos/.")
        return copias
    print(f"{len(copias)} copia(s) en respaldos/:")
    for copia in copias:
        print(f"  {copia.name}  {copia.stat().st_size / 1024:8.1f} KB")
    return copias


def rotar(conservar):
    copias = sorted(CARPETA.glob(f"{PREFIJO}*{EXTENSION}"))
    for vieja in copias[:-conservar] if conservar > 0 else []:
        vieja.unlink(missing_ok=True)
        vieja.with_name(vieja.name + ".sha256").unlink(missing_ok=True)
        print(f"   Copia antigua eliminada: {vieja.name}")


def restaurar(nombre, confirmar=True):
    ruta = ruta_archivo(nombre)
    verificar_contenedor()
    verificar(ruta, silencioso=True)
    usuario, clave, base = credenciales()

    if confirmar:
        print(f"⚠️  Esto REEMPLAZA la base '{base}' con el contenido de {ruta.name}.")
        print("   Los cambios hechos después de esa copia (usuarios nuevos, auditoría, etc.) se perderán.")
        if input("   Escriba RESTAURAR para continuar: ").strip() != "RESTAURAR":
            print("Cancelado.")
            return False

    # Copia de seguridad del estado actual antes de reemplazarlo.
    print("Guardando primero una copia del estado actual...")
    respaldar(conservar=0)

    # Ruta DENTRO del contenedor de MongoDB: nombre aleatorio y se borra al terminar.
    destino = f"/tmp/coraleum_rest_{secrets.token_hex(6)}.gz"  # nosec B108
    docker("cp", str(ruta), f"{CONTENEDOR}:{destino}")
    try:
        with ConfigTemporal(usuario, clave) as cfg:
            docker(
                "exec", CONTENEDOR, "mongorestore", f"--uri={cfg.uri}", f"--config={cfg.ruta}",
                f"--archive={destino}", "--gzip", "--drop", f"--nsInclude={base}.*", "--quiet",
            )
    finally:
        docker("exec", CONTENEDOR, "rm", "-f", destino)
    print(f"✅ Base '{base}' restaurada desde {ruta.name}.")
    print("   Reinicie el backend para que tome los cambios: docker compose restart backend")
    return True


def main(argv=None):
    parser = argparse.ArgumentParser(description="Copias de seguridad de MongoDB para Coraleum.")
    sub = parser.add_subparsers(dest="accion", required=True)
    p_resp = sub.add_parser("respaldar", help="Crea una copia nueva.")
    p_resp.add_argument("--conservar", type=int, default=14, help="Cuántas copias conservar (0 = todas).")
    sub.add_parser("listar", help="Lista las copias.")
    p_ver = sub.add_parser("verificar", help="Comprueba una copia.")
    p_ver.add_argument("archivo")
    p_res = sub.add_parser("restaurar", help="Restaura una copia.")
    p_res.add_argument("archivo")
    argumentos = parser.parse_args(argv)

    try:
        if argumentos.accion == "respaldar":
            respaldar(argumentos.conservar)
        elif argumentos.accion == "listar":
            listar()
        elif argumentos.accion == "verificar":
            verificar(argumentos.archivo)
        elif argumentos.accion == "restaurar":
            restaurar(argumentos.archivo)
    except ErrorRespaldo as error:
        print(f"❌ {error}")
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
