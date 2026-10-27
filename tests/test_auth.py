"""Pruebas de autenticación, autorización por roles y protecciones."""

from datetime import timedelta

import jwt

from api.seguridad import ahora
from api import config, db
from tests.conftest import CSRF, PASSWORD_ADMIN, login, registrar

PASSWORD = "Coral-Seguro-2026"


def _id(c):
    return c.get("/auth/me").json()["usuario"]["id"]


# ------------------------------------------------------------
# Visitantes y rutas públicas
# ------------------------------------------------------------

def test_visitante_no_tiene_sesion(cliente):
    assert cliente.get("/auth/me").json() == {"usuario": None}


def test_visitante_no_accede_a_datos(cliente):
    for ruta in ["/fechas", "/areas", "/areas/8", "/areas/8/historico", "/resumen", "/geojson"]:
        assert cliente.get(ruta).status_code == 401, ruta


def test_estadisticas_publicas_sin_datos_ambientales(cliente):
    r = cliente.get("/estadisticas")
    assert r.status_code == 200
    assert r.json() == {"total_areas": 47, "total_pixeles": 20, "total_fechas": 35}


def test_visitante_no_accede_a_admin(cliente):
    assert cliente.get("/admin/usuarios").status_code == 401


# ------------------------------------------------------------
# Registro
# ------------------------------------------------------------

def test_registro_crea_usuario_sin_acceso_a_datos(cliente):
    r = registrar(cliente)
    assert r.status_code == 201
    usuario = r.json()["usuario"]
    assert usuario["rol"] == "usuario"
    assert "password_hash" not in usuario
    assert config.COOKIE_ACCESS in cliente.cookies
    # Registrarse no da acceso al histórico.
    r = cliente.get("/fechas")
    assert r.status_code == 403
    assert "investigador" in r.json()["detail"]


def test_password_se_guarda_con_argon2id(cliente):
    registrar(cliente)
    guardado = db.usuarios.find_one({"email": "ana@ejemplo.org"})
    assert guardado["password_hash"].startswith("$argon2id$")
    assert PASSWORD not in guardado["password_hash"]


def test_registro_rechaza_contrasenas_debiles(cliente):
    for debil in ["corta", "1234567890", "password123", "aaaaaaaaaaaa", "Pérez-12345678"]:
        r = registrar(cliente, email="ana@ejemplo.org", password=debil)
        assert r.status_code == 400, debil
    assert db.usuarios.count_documents({}) == 0


def test_registro_rechaza_correo_invalido_y_campos_extra(cliente):
    r = cliente.post("/auth/registro", json={"nombre": "Ana", "email": "no-es-correo", "password": PASSWORD}, headers=CSRF)
    assert r.status_code == 422
    r = cliente.post(
        "/auth/registro",
        json={"nombre": "Ana", "email": "a@b.org", "password": PASSWORD, "rol": "admin"},
        headers=CSRF,
    )
    assert r.status_code == 422  # no se puede auto-asignar un rol


def test_registro_duplicado(cliente, crear_cliente):
    registrar(cliente)
    r = registrar(crear_cliente(), email="ANA@ejemplo.org")
    assert r.status_code == 409


# ------------------------------------------------------------
# CSRF
# ------------------------------------------------------------

def test_csrf_sin_encabezado(cliente):
    r = cliente.post("/auth/login", json={"email": "a@b.org", "password": "x"})
    assert r.status_code == 403


def test_csrf_origen_no_permitido(cliente):
    r = cliente.post(
        "/auth/login",
        json={"email": "a@b.org", "password": "x"},
        headers={**CSRF, "Origin": "https://sitio-malicioso.example"},
    )
    assert r.status_code == 403


# ------------------------------------------------------------
# Inicio de sesión y bloqueo
# ------------------------------------------------------------

def test_login_mensaje_generico(cliente, crear_cliente):
    registrar(cliente)
    otro = crear_cliente()
    malo = login(otro, "ana@ejemplo.org", "Incorrecta-123456")
    inexistente = login(otro, "nadie@ejemplo.org", "Incorrecta-123456")
    assert malo.status_code == inexistente.status_code == 401
    assert malo.json()["detail"] == inexistente.json()["detail"]


def test_bloqueo_tras_intentos_fallidos(cliente, crear_cliente):
    registrar(cliente)
    otro = crear_cliente()
    for _ in range(config.MAX_INTENTOS_FALLIDOS - 1):
        assert login(otro, "ana@ejemplo.org", "Incorrecta-123456").status_code == 401
    # El 5.º intento fallido bloquea la cuenta y lo informa de inmediato.
    quinto = login(otro, "ana@ejemplo.org", "Incorrecta-123456")
    assert quinto.status_code == 423 and "bloqueada" in quinto.json()["detail"]
    # Bloqueada incluso con la contraseña correcta.
    assert login(otro, "ana@ejemplo.org", PASSWORD).status_code == 423
    eventos = [e["evento"] for e in db.auditoria_accesos.find()]
    assert "cuenta_bloqueada" in eventos


def test_limite_de_peticiones_login(cliente):
    codigos = [login(cliente, f"x{i}@ejemplo.org", "Incorrecta-123456").status_code for i in range(12)]
    assert 429 in codigos


def test_token_manipulado_es_rechazado(cliente):
    registrar(cliente)
    falso = jwt.encode({"sub": "x", "tipo": "access"}, "otra-clave-cualquiera-de-32-caracteres!!", algorithm="HS256")
    cliente.cookies.set(config.COOKIE_ACCESS, falso)
    assert cliente.get("/auth/me").json() == {"usuario": None}
    sin_firma = jwt.encode({"sub": "x", "tipo": "access"}, None, algorithm="none")
    cliente.cookies.set(config.COOKIE_ACCESS, sin_firma)
    assert cliente.get("/auth/me").json() == {"usuario": None}


# ------------------------------------------------------------
# Sesiones: renovación, reutilización y cierre
# ------------------------------------------------------------

def test_refresh_rota_el_token(cliente):
    registrar(cliente)
    viejo = cliente.cookies.get(config.COOKIE_REFRESH)
    r = cliente.post("/auth/refresh", headers=CSRF)
    assert r.status_code == 200
    assert cliente.cookies.get(config.COOKIE_REFRESH) != viejo


def test_reutilizar_refresh_revoca_la_familia(cliente, crear_cliente):
    registrar(cliente)
    robado = cliente.cookies.get(config.COOKIE_REFRESH)
    assert cliente.post("/auth/refresh", headers=CSRF).status_code == 200  # el usuario legítimo renueva
    # Pasado el margen de gracia entre pestañas (30 s), reusar el token es sospechoso.
    db.sesiones.update_many({"motivo_cierre": "rotada"}, {"$set": {"revocado_en": ahora() - timedelta(seconds=60)}})

    atacante = crear_cliente()
    atacante.cookies.set(config.COOKIE_REFRESH, robado)
    assert atacante.post("/auth/refresh", headers=CSRF).status_code == 401
    # La sesión legítima derivada también queda revocada.
    assert cliente.post("/auth/refresh", headers=CSRF).status_code == 401


def test_dos_pestanas_renuevan_a_la_vez_sin_cerrar_la_sesion(cliente, crear_cliente):
    """Dos pestañas del mismo navegador renuevan con el mismo token casi a la vez."""
    registrar(cliente)
    viejo = cliente.cookies.get(config.COOKIE_REFRESH)
    assert cliente.post("/auth/refresh", headers=CSRF).status_code == 200
    otra_pestana = crear_cliente()
    otra_pestana.cookies.set(config.COOKIE_REFRESH, viejo)
    r = otra_pestana.post("/auth/refresh", headers=CSRF)
    assert r.status_code == 409 and r.json()["accion"] == "reintentar"
    # La sesión sigue viva y no se registró como robo.
    assert cliente.get("/auth/me").json()["usuario"] is not None
    assert db.auditoria_accesos.count_documents({"evento": "refresh_reutilizado"}) == 0


def test_logout_revoca_el_refresh(cliente):
    registrar(cliente)
    refresh = cliente.cookies.get(config.COOKIE_REFRESH)
    assert cliente.post("/auth/logout", headers=CSRF).status_code == 200
    cliente.cookies.set(config.COOKIE_REFRESH, refresh)
    assert cliente.post("/auth/refresh", headers=CSRF).status_code == 401


def test_refresh_token_se_guarda_como_hash(cliente):
    registrar(cliente)
    token = cliente.cookies.get(config.COOKIE_REFRESH)
    assert db.sesiones.find_one({"token_hash": token}) is None
    assert db.sesiones.count_documents({}) == 1


def test_cambio_password_cierra_otras_sesiones(cliente, crear_cliente):
    registrar(cliente)
    otro = crear_cliente()
    assert login(otro, "ana@ejemplo.org", PASSWORD).status_code == 200
    r = cliente.post(
        "/auth/cambiar-password",
        json={"password_actual": PASSWORD, "password_nueva": "Nueva-Clave-Marina-77"},
        headers=CSRF,
    )
    assert r.status_code == 200
    assert cliente.get("/auth/me").json()["usuario"] is not None  # sigue dentro
    assert otro.get("/auth/me").json()["usuario"] is None  # la otra sesión cayó
    assert otro.post("/auth/refresh", headers=CSRF).status_code == 401
    assert login(otro, "ana@ejemplo.org", "Nueva-Clave-Marina-77").status_code == 200


# ------------------------------------------------------------
# Roles: solicitud de investigador y administración
# ------------------------------------------------------------

def test_flujo_investigador(cliente, admin):
    registrar(cliente)
    assert cliente.get("/fechas").status_code == 403
    r = cliente.post(
        "/auth/solicitar-investigador",
        json={"institucion": "Universidad de San Buenaventura", "motivo": "Análisis histórico de DHW para mi tesis"},
        headers=CSRF,
    )
    assert r.status_code == 200
    assert r.json()["usuario"]["solicitud"]["estado"] == "pendiente"

    pendientes = admin.get("/admin/usuarios", params={"solicitud": "pendiente"}).json()
    assert pendientes["pendientes"] == 1
    usuario_id = pendientes["usuarios"][0]["id"]

    r = admin.post(f"/admin/usuarios/{usuario_id}/solicitud", json={"decision": "aprobar"}, headers=CSRF)
    assert r.json()["usuario"]["rol"] == "investigador"

    # El cambio aplica de inmediato, sin volver a iniciar sesión.
    fechas = cliente.get("/fechas")
    assert fechas.status_code == 200
    assert fechas.json()["total_fechas"] == 35
    assert cliente.get("/areas").json()["total_areas"] == 47
    assert cliente.get("/areas/8/historico").json()["total_registros"] == 35


def test_solicitud_rechazada(cliente, admin):
    registrar(cliente)
    cliente.post("/auth/solicitar-investigador", json={"institucion": "Colegio", "motivo": "Quiero ver los datos"}, headers=CSRF)
    usuario_id = _id(cliente)
    r = admin.post(
        f"/admin/usuarios/{usuario_id}/solicitud",
        json={"decision": "rechazar", "comentario": "Falta información institucional"},
        headers=CSRF,
    )
    assert r.json()["usuario"]["rol"] == "usuario"
    assert cliente.get("/auth/me").json()["usuario"]["solicitud"]["estado"] == "rechazada"
    assert cliente.get("/fechas").status_code == 403


def test_no_admin_no_accede_a_administracion(cliente):
    registrar(cliente)
    assert cliente.get("/admin/usuarios").status_code == 403
    db.usuarios.update_one({"email": "ana@ejemplo.org"}, {"$set": {"roles": ["investigador"]}})
    assert cliente.get("/admin/usuarios").status_code == 403
    assert cliente.get("/admin/auditoria").status_code == 403


def test_desactivar_expulsa_de_inmediato(cliente, admin):
    registrar(cliente)
    usuario_id = _id(cliente)
    assert admin.patch(f"/admin/usuarios/{usuario_id}", json={"activo": False}, headers=CSRF).status_code == 200
    assert cliente.get("/auth/me").json()["usuario"] is None
    assert cliente.post("/auth/refresh", headers=CSRF).status_code == 401
    assert login(cliente, "ana@ejemplo.org", PASSWORD).status_code == 403


def test_admin_no_puede_quitarse_su_rol_ni_desactivarse(admin):
    mi_id = _id(admin)
    assert admin.patch(f"/admin/usuarios/{mi_id}", json={"roles": ["usuario"]}, headers=CSRF).status_code == 400
    assert admin.patch(f"/admin/usuarios/{mi_id}", json={"activo": False}, headers=CSRF).status_code == 400


def test_restablecer_password_obliga_a_cambiarla(cliente, admin, crear_cliente):
    registrar(cliente)
    usuario_id = _id(cliente)
    r = admin.post(f"/admin/usuarios/{usuario_id}/restablecer-password", headers=CSRF)
    temporal = r.json()["password_temporal"]
    assert cliente.get("/auth/me").json()["usuario"] is None  # sesión anterior cerrada

    nuevo = crear_cliente()
    r = login(nuevo, "ana@ejemplo.org", temporal)
    assert r.json()["usuario"]["debe_cambiar_password"] is True
    db.usuarios.update_one({"email": "ana@ejemplo.org"}, {"$set": {"roles": ["investigador"]}})
    bloqueado = nuevo.get("/fechas")
    assert bloqueado.status_code == 403 and bloqueado.json()["accion"] == "cambiar-password"

    r = nuevo.post(
        "/auth/cambiar-password",
        json={"password_actual": temporal, "password_nueva": "Mi-Clave-Definitiva-9"},
        headers=CSRF,
    )
    assert r.status_code == 200
    assert nuevo.get("/fechas").status_code == 200


def test_auditoria_registra_eventos_sin_secretos(cliente, admin):
    registrar(cliente)
    login(cliente, "ana@ejemplo.org", "Incorrecta-123456")
    eventos = admin.get("/admin/auditoria").json()["eventos"]
    nombres = {e["evento"] for e in eventos}
    assert {"registro", "login"} <= nombres
    assert any(e["evento"] == "login" and not e["exito"] for e in eventos)
    texto = str(eventos)
    assert PASSWORD not in texto and "Incorrecta-123456" not in texto and PASSWORD_ADMIN not in texto


def test_busqueda_admin_no_permite_regex(admin):
    r = admin.get("/admin/usuarios", params={"q": ".*"})
    assert r.status_code == 200
    assert r.json()["total"] == 0  # ".*" se busca literal, no como patrón
