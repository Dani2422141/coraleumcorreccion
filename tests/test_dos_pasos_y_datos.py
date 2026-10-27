"""Pruebas de verificación en dos pasos y de derechos del titular (Ley 1581)."""

import re

import pyotp

from api import config, db
from tests.conftest import CSRF, PASSWORD_ADMIN, codigo_actual, login, login_2fa, registrar

PASSWORD = "Coral-Seguro-2026"


def _configurar_2fa(c, password=PASSWORD):
    """Activa 2FA y devuelve (secreto, códigos de recuperación)."""
    r = c.post("/auth/2fa/iniciar", json={"password": password}, headers=CSRF)
    assert r.status_code == 200, r.text
    assert r.json()["qr"].startswith("data:image/svg+xml;base64,")
    secreto = r.json()["clave_manual"].replace(" ", "")
    r = c.post("/auth/2fa/activar", json={"codigo": codigo_actual(secreto)}, headers=CSRF)
    assert r.status_code == 200, r.text
    return secreto, r.json()["codigos_recuperacion"]


def _crear_admin_sin_2fa(c):
    registrar(c, email="nueva@coraleum.org", nombre="Nueva Admin")
    db.usuarios.update_one({"email": "nueva@coraleum.org"}, {"$set": {"roles": ["admin"]}})


# ------------------------------------------------------------
# Consentimiento (Ley 1581 de 2012)
# ------------------------------------------------------------

def test_registro_sin_aceptar_politica_es_rechazado(cliente):
    r = registrar(cliente, acepta=False)
    assert r.status_code == 400
    assert "política" in r.json()["detail"]
    assert db.usuarios.count_documents({}) == 0


def test_registro_sin_campo_de_consentimiento_es_rechazado(cliente):
    r = cliente.post("/auth/registro", json={"nombre": "Ana", "email": "a@b.org", "password": PASSWORD}, headers=CSRF)
    assert r.status_code == 422


def test_registro_guarda_prueba_del_consentimiento(cliente):
    r = registrar(cliente)
    assert r.json()["usuario"]["politica_version"] == config.POLITICA_VERSION
    consentimiento = db.usuarios.find_one({"email": "ana@ejemplo.org"})["consentimiento"]
    assert consentimiento["version"] == config.POLITICA_VERSION
    assert consentimiento["fecha"] is not None and consentimiento["ip"]


def test_aceptar_politica_en_cuenta_antigua(cliente):
    registrar(cliente)
    db.usuarios.update_one({"email": "ana@ejemplo.org"}, {"$unset": {"consentimiento": ""}})
    antes = cliente.get("/auth/me").json()["usuario"]
    assert antes["politica_version"] is None and antes["politica_pendiente"] is True
    r = cliente.post("/auth/aceptar-politica", headers=CSRF)
    assert r.json()["usuario"]["politica_version"] == config.POLITICA_VERSION
    assert r.json()["usuario"]["politica_pendiente"] is False


def test_mis_datos_no_incluye_secretos(cliente):
    registrar(cliente)
    _configurar_2fa(cliente)
    datos = cliente.get("/auth/mis-datos").json()
    assert datos["cuenta"]["email"] == "ana@ejemplo.org"
    assert datos["consentimiento"]["version"] == config.POLITICA_VERSION
    assert any(e["evento"] == "registro" for e in datos["registro_de_actividad"])
    texto = str(datos)
    guardado = db.usuarios.find_one({"email": "ana@ejemplo.org"})
    assert "argon2" not in texto
    assert guardado["dos_pasos"]["secreto"] not in texto


def test_eliminar_cuenta_borra_datos_y_anonimiza_auditoria(cliente, crear_cliente):
    registrar(cliente)
    usuario_id = db.usuarios.find_one({"email": "ana@ejemplo.org"})["_id"]
    otro = crear_cliente()
    assert login(otro, "ana@ejemplo.org", PASSWORD).status_code == 200

    malo = cliente.post("/auth/eliminar-cuenta", json={"password": "Otra-Clave-123456", "confirmacion": "ELIMINAR"}, headers=CSRF)
    assert malo.status_code == 400
    sin_confirmar = cliente.post("/auth/eliminar-cuenta", json={"password": PASSWORD, "confirmacion": "si"}, headers=CSRF)
    assert sin_confirmar.status_code == 422

    r = cliente.post("/auth/eliminar-cuenta", json={"password": PASSWORD, "confirmacion": "ELIMINAR"}, headers=CSRF)
    assert r.status_code == 200
    assert db.usuarios.find_one({"email": "ana@ejemplo.org"}) is None
    assert db.sesiones.count_documents({"usuario_id": usuario_id}) == 0
    assert db.auditoria_accesos.count_documents({"email": "ana@ejemplo.org"}) == 0
    assert db.auditoria_accesos.count_documents({"anonimizado": True}) >= 2
    # Las otras sesiones también quedan cerradas.
    assert otro.get("/auth/me").json()["usuario"] is None
    assert login(otro, "ana@ejemplo.org", PASSWORD).status_code == 401


def test_ultimo_admin_no_puede_eliminar_su_cuenta(admin):
    from tests.conftest import SECRETO_ADMIN
    r = admin.post(
        "/auth/eliminar-cuenta",
        json={"password": PASSWORD_ADMIN, "confirmacion": "ELIMINAR", "codigo": codigo_actual(SECRETO_ADMIN, 1)},
        headers=CSRF,
    )
    assert r.status_code == 400
    assert "único administrador" in r.json()["detail"]


# ------------------------------------------------------------
# Verificación en dos pasos
# ------------------------------------------------------------

def test_admin_sin_2fa_no_usa_el_panel(cliente):
    _crear_admin_sin_2fa(cliente)
    r = cliente.get("/admin/usuarios")
    assert r.status_code == 403
    assert r.json()["accion"] == "configurar-2fa"
    # Pero sí puede ver los datos y configurar su 2FA.
    assert cliente.get("/fechas").status_code == 200


def test_activar_2fa_y_login_en_dos_pasos(cliente, crear_cliente):
    _crear_admin_sin_2fa(cliente)
    secreto, codigos = _configurar_2fa(cliente)
    assert len(codigos) == 8 and all(re.fullmatch(r"[A-Z2-9]{5}-[A-Z2-9]{5}", c) for c in codigos)
    assert cliente.get("/admin/usuarios").status_code == 200

    guardado = db.usuarios.find_one({"email": "nueva@coraleum.org"})["dos_pasos"]
    assert secreto not in guardado["secreto"]  # el secreto está cifrado
    assert all(c not in str(guardado["recuperacion"]) for c in codigos)  # códigos como hash

    nuevo = crear_cliente()
    r = login(nuevo, "nueva@coraleum.org", PASSWORD)
    assert r.json()["requiere_2fa"] is True
    assert config.COOKIE_ACCESS not in nuevo.cookies  # la contraseña sola no abre sesión
    assert nuevo.get("/auth/me").json()["usuario"] is None

    malo = nuevo.post("/auth/2fa/verificar", json={"desafio": r.json()["desafio"], "codigo": "000000"}, headers=CSRF)
    assert malo.status_code == 401
    bueno = nuevo.post(
        "/auth/2fa/verificar",
        json={"desafio": r.json()["desafio"], "codigo": codigo_actual(secreto, 1)},
        headers=CSRF,
    )
    assert bueno.status_code == 200
    assert nuevo.get("/admin/usuarios").status_code == 200


def test_codigo_totp_no_se_puede_reutilizar(cliente, crear_cliente):
    registrar(cliente)
    secreto, _ = _configurar_2fa(cliente)
    c1, c2 = crear_cliente(), crear_cliente()
    codigo = codigo_actual(secreto, 1)
    r1 = login(c1, "ana@ejemplo.org", PASSWORD)
    assert c1.post("/auth/2fa/verificar", json={"desafio": r1.json()["desafio"], "codigo": codigo}, headers=CSRF).status_code == 200
    r2 = login(c2, "ana@ejemplo.org", PASSWORD)
    assert c2.post("/auth/2fa/verificar", json={"desafio": r2.json()["desafio"], "codigo": codigo}, headers=CSRF).status_code == 401


def test_codigo_de_recuperacion_es_de_un_solo_uso(cliente, crear_cliente):
    registrar(cliente)
    _, codigos = _configurar_2fa(cliente)
    c1 = crear_cliente()
    r = login(c1, "ana@ejemplo.org", PASSWORD)
    ok = c1.post("/auth/2fa/verificar", json={"desafio": r.json()["desafio"], "codigo": codigos[0].lower()}, headers=CSRF)
    assert ok.status_code == 200
    assert ok.json()["usuario"]["codigos_recuperacion_restantes"] == 7

    c2 = crear_cliente()
    r = login(c2, "ana@ejemplo.org", PASSWORD)
    otra_vez = c2.post("/auth/2fa/verificar", json={"desafio": r.json()["desafio"], "codigo": codigos[0]}, headers=CSRF)
    assert otra_vez.status_code == 401


def test_desafio_falso_o_de_otro_tipo_es_rechazado(cliente):
    registrar(cliente)
    _configurar_2fa(cliente)
    acceso = cliente.cookies.get(config.COOKIE_ACCESS)
    for falso in ["no-es-un-token-valido", acceso]:  # un token de acceso no sirve como desafío
        r = cliente.post("/auth/2fa/verificar", json={"desafio": falso, "codigo": "123456"}, headers=CSRF)
        assert r.status_code == 401


def test_fallos_de_2fa_bloquean_la_cuenta(cliente, crear_cliente):
    registrar(cliente)
    secreto, _ = _configurar_2fa(cliente)
    atacante = crear_cliente()
    r = login(atacante, "ana@ejemplo.org", PASSWORD)
    for _ in range(config.MAX_INTENTOS_FALLIDOS):
        atacante.post("/auth/2fa/verificar", json={"desafio": r.json()["desafio"], "codigo": "111111"}, headers=CSRF)
    r = atacante.post("/auth/2fa/verificar", json={"desafio": r.json()["desafio"], "codigo": codigo_actual(secreto, 1)}, headers=CSRF)
    assert r.status_code == 423


def test_admin_no_puede_desactivar_su_2fa(admin):
    from tests.conftest import SECRETO_ADMIN
    r = admin.post("/auth/2fa/desactivar", json={"password": PASSWORD_ADMIN, "codigo": codigo_actual(SECRETO_ADMIN, 1)}, headers=CSRF)
    assert r.status_code == 400


def test_usuario_puede_desactivar_su_2fa(cliente, crear_cliente):
    registrar(cliente)
    secreto, _ = _configurar_2fa(cliente)
    r = cliente.post("/auth/2fa/desactivar", json={"password": PASSWORD, "codigo": codigo_actual(secreto, 1)}, headers=CSRF)
    assert r.status_code == 200 and r.json()["usuario"]["dos_pasos"] is False
    assert login(crear_cliente(), "ana@ejemplo.org", PASSWORD).json().get("requiere_2fa") is None


def test_admin_restablece_2fa_de_otra_cuenta(cliente, admin, crear_cliente):
    registrar(cliente)
    _configurar_2fa(cliente)
    usuario_id = cliente.get("/auth/me").json()["usuario"]["id"]
    r = admin.post(f"/admin/usuarios/{usuario_id}/restablecer-2fa", headers=CSRF)
    assert r.status_code == 200 and r.json()["usuario"]["dos_pasos"] is False
    assert cliente.get("/auth/me").json()["usuario"] is None  # sesiones cerradas
    assert login(crear_cliente(), "ana@ejemplo.org", PASSWORD).json()["usuario"]["dos_pasos"] is False


def test_regenerar_codigos_invalida_los_anteriores(cliente, crear_cliente):
    registrar(cliente)
    secreto, viejos = _configurar_2fa(cliente)
    r = cliente.post("/auth/2fa/regenerar-codigos", json={"password": PASSWORD, "codigo": codigo_actual(secreto, 1)}, headers=CSRF)
    nuevos = r.json()["codigos_recuperacion"]
    assert set(nuevos).isdisjoint(viejos)
    c = crear_cliente()
    reto = login(c, "ana@ejemplo.org", PASSWORD).json()["desafio"]
    assert c.post("/auth/2fa/verificar", json={"desafio": reto, "codigo": viejos[1]}, headers=CSRF).status_code == 401


def test_qr_contiene_uri_estandar(cliente):
    registrar(cliente)
    r = cliente.post("/auth/2fa/iniciar", json={"password": PASSWORD}, headers=CSRF)
    secreto = r.json()["clave_manual"].replace(" ", "")
    uri = pyotp.TOTP(secreto).provisioning_uri(name="ana@ejemplo.org", issuer_name="Coraleum")
    assert uri.startswith("otpauth://totp/Coraleum:ana%40ejemplo.org")


def test_auditoria_registra_2fa(admin):
    eventos = {e["evento"] for e in admin.get("/admin/auditoria").json()["eventos"]}
    assert {"login_primer_paso", "login"} <= eventos


def test_login_2fa_helper_con_admin(crear_cliente, admin):
    from tests.conftest import SECRETO_ADMIN
    otro = crear_cliente()
    assert login_2fa(otro, "admin@coraleum.org", PASSWORD_ADMIN, SECRETO_ADMIN, desfase=1).status_code == 200
