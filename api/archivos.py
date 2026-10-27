"""Validación de archivos cargados (soporte PDF de la solicitud de investigador).

Una extensión se cambia en un segundo (programa.exe → programa.pdf), así que
la extensión y el tipo que declara el navegador NO son prueba de nada. Aquí
se revisa el CONTENIDO del archivo (OWASP File Upload Cheat Sheet):

1. Tamaño máximo (2 MB) y archivo no vacío.
2. Extensión permitida (.pdf) y tipo declarado application/pdf.
3. Firma del archivo ("magic bytes"): un PDF real empieza por %PDF-.
   Un ejecutable de Windows empieza por MZ y se rechaza con ese diagnóstico.
4. Estructura mínima: debe terminar con el marcador %%EOF.
5. Sin contenido activo: se rechazan PDF con JavaScript, acciones que lanzan
   programas o archivos incrustados.

Además: el nombre se limpia, el archivo se guarda cifrado en la base de datos
(nunca en una carpeta servida por la web), se registra su huella SHA-256 y se
entrega al administrador solo como descarga (Content-Disposition: attachment).
"""

import hashlib
import re
import unicodedata
from urllib.parse import unquote


TAMANO_MAXIMO = 2 * 1024 * 1024  # 2 MB
ENCABEZADO_NOMBRE = "x-nombre-archivo"
EXTENSIONES_PERMITIDAS = (".pdf",)
TIPOS_PERMITIDOS = ("application/pdf",)

# Firmas de formatos peligrosos o que no son PDF (para explicar el rechazo).
_FIRMAS = (
    (b"MZ", "un programa ejecutable de Windows (.exe/.dll)"),
    (b"\x7fELF", "un programa ejecutable de Linux"),
    (b"\xcf\xfa\xed\xfe", "un programa ejecutable de macOS"),
    (b"#!", "un script ejecutable"),
    (b"PK\x03\x04", "un archivo comprimido (ZIP) o un documento de Office"),
    (b"Rar!", "un archivo comprimido (RAR)"),
    (b"7z\xbc\xaf", "un archivo comprimido (7z)"),
    (b"\xd0\xcf\x11\xe0", "un documento antiguo de Office"),
    (b"\x89PNG", "una imagen PNG"),
    (b"\xff\xd8\xff", "una imagen JPEG"),
    (b"<", "una página web o un archivo XML/SVG"),
)

# Contenido activo que no debe tener un documento de soporte.
_CONTENIDO_ACTIVO = (
    (re.compile(rb"/JavaScript\b"), "JavaScript"),
    (re.compile(rb"/JS[\s/<(\[]"), "JavaScript"),
    (re.compile(rb"/Launch\b"), "acción que ejecuta programas (/Launch)"),
    (re.compile(rb"/EmbeddedFiles?\b"), "archivos incrustados"),
    (re.compile(rb"/RichMedia\b"), "contenido multimedia activo"),
)

_VERSION_PDF = re.compile(rb"^%PDF-(1\.[0-7]|2\.0)")


def nombre_seguro(nombre_codificado):
    """Nombre de archivo sin rutas ni caracteres de control (máx. 120)."""
    nombre = unquote(nombre_codificado or "")
    nombre = nombre.replace("\\", "/").split("/")[-1]
    nombre = unicodedata.normalize("NFC", nombre)
    nombre = "".join(c for c in nombre if c.isprintable() and c not in '<>:"|?*')
    nombre = nombre.strip().strip(".")
    return (nombre or "documento.pdf")[-120:]


async def leer_cuerpo(request):
    """Lee el cuerpo sin pasar de TAMANO_MAXIMO (+1 para detectar el exceso)."""
    partes = []
    total = 0
    async for parte in request.stream():
        total += len(parte)
        if total > TAMANO_MAXIMO:
            return None
        partes.append(parte)
    return b"".join(partes)


def sha256(contenido):
    return hashlib.sha256(contenido).hexdigest()


def _rechazo(mensaje, motivo, estado=400, **extra):
    return {"estado": estado, "mensaje": mensaje, "auditoria": {"motivo": motivo, **extra}}


def validar_pdf(contenido, nombre, tipo_declarado):
    """None si el archivo es un PDF aceptable; si no, un dict con el rechazo."""
    if contenido is None:
        return _rechazo(
            f"El archivo supera el tamaño máximo permitido ({TAMANO_MAXIMO // (1024 * 1024)} MB).",
            "tamaño excedido",
            estado=413,
        )
    if not contenido:
        return _rechazo("El archivo está vacío.", "archivo vacío")

    extra = {"tamano": len(contenido), "sha256": sha256(contenido)[:16], "tipo_declarado": tipo_declarado or "ninguno"}

    if not nombre.lower().endswith(EXTENSIONES_PERMITIDAS):
        return _rechazo("Solo se permiten documentos PDF (.pdf).", "extensión no permitida", **extra)
    if tipo_declarado not in TIPOS_PERMITIDOS:
        return _rechazo("Solo se permiten documentos PDF (.pdf).", "tipo declarado no permitido", estado=415, **extra)

    if not contenido.startswith(b"%PDF-"):
        for firma, descripcion in _FIRMAS:
            if contenido.startswith(firma):
                return _rechazo(
                    f"El archivo se rechazó: aunque su nombre termina en .pdf, su contenido corresponde a "
                    f"{descripcion}. Solo se aceptan documentos PDF reales.",
                    f"contenido real: {descripcion} (extensión falsificada)",
                    estado=415,
                    **extra,
                )
        return _rechazo(
            "El archivo se rechazó: su contenido no corresponde a un documento PDF.",
            "firma de archivo desconocida (no empieza por %PDF-)",
            estado=415,
            **extra,
        )

    if not _VERSION_PDF.match(contenido):
        return _rechazo("El documento PDF no es válido.", "versión de PDF no reconocida", estado=415, **extra)
    if b"%%EOF" not in contenido[-2048:]:
        return _rechazo("El documento PDF está incompleto o dañado.", "falta el marcador %%EOF", **extra)

    for patron, descripcion in _CONTENIDO_ACTIVO:
        if patron.search(contenido):
            return _rechazo(
                f"El PDF se rechazó porque contiene {descripcion}. Envíe un PDF sin contenido activo "
                "(por ejemplo, use «Imprimir → Guardar como PDF»).",
                f"contenido activo: {descripcion}",
                estado=415,
                **extra,
            )
    return None

