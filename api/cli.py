"""Herramientas de consola para administrar Coraleum.

Crear (o promover) el primer administrador, desde la carpeta del proyecto:

    docker compose exec backend python -m api.cli crear-admin

La contraseña se escribe de forma oculta y nunca queda en el historial
de comandos ni en el código.
"""

import getpass
import sys

from pydantic import TypeAdapter, ValidationError
from pydantic import EmailStr

from api import db, permisos
from api.seguridad import ahora, hash_password, validar_politica_password


def _pedir(texto, minimo=1):
    while True:
        valor = input(texto).strip()
        if len(valor) >= minimo:
            return valor
        print(f"  Debe tener al menos {minimo} caracteres.")


def crear_admin():
    db.crear_indices()
    print("=== Crear o promover administrador de Coraleum ===")
    while True:
        email = _pedir("Correo: ").lower()
        try:
            TypeAdapter(EmailStr).validate_python(email)
            break
        except ValidationError:
            print("  Correo no válido.")

    existente = db.usuarios.find_one({"email": email})
    if existente:
        roles_actuales = ", ".join(permisos.claves_de(existente))
        respuesta = input(f"Ya existe la cuenta de {existente.get('nombre')} ({roles_actuales}). ¿Agregarle el rol de administrador? [s/N]: ")
        if respuesta.strip().lower() not in {"s", "si", "sí"}:
            print("Cancelado.")
            return 1
        db.usuarios.update_one(
            {"_id": existente["_id"]},
            {
                "$set": {
                    "roles": list(dict.fromkeys(
                        [c for c in permisos.claves_de(existente) if c != permisos.ROL_USUARIO] + [permisos.ROL_ADMIN]
                    )),
                    "activo": True,
                    "intentos_fallidos": 0,
                    "bloqueado_hasta": None,
                },
                "$unset": {"rol": ""},
            },
        )
        print(f"✅ {email} ahora es administrador.")
        return 0

    nombre = _pedir("Nombre completo: ", minimo=2)
    while True:
        password = getpass.getpass("Contraseña (no se mostrará): ")
        error = validar_politica_password(password, email, nombre)
        if error:
            print(f"  {error}")
            continue
        if getpass.getpass("Repita la contraseña: ") != password:
            print("  Las contraseñas no coinciden.")
            continue
        break

    momento = ahora()
    db.usuarios.insert_one(
        {
            "nombre": nombre,
            "email": email,
            "password_hash": hash_password(password),
            "roles": [permisos.ROL_ADMIN],
            "activo": True,
            "debe_cambiar_password": False,
            "token_version": 0,
            "intentos_fallidos": 0,
            "bloqueado_hasta": None,
            "solicitud": None,
            "creado_en": momento,
            "ultimo_acceso": None,
        }
    )
    print(f"✅ Administrador {email} creado. Ya puede iniciar sesión en la aplicación.")
    return 0


def main(argumentos):
    if argumentos[:1] == ["crear-admin"]:
        return crear_admin()
    print(__doc__)
    return 1


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
