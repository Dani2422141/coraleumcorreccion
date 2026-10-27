"""Pruebas 13 a 19 de la sustentación (lista ampliada del profesor).

La 13 (contraseña enmascarada y no copiable) es de la interfaz y se
comprueba en el navegador; aquí se verifica que la API nunca devuelve
contraseñas.
"""

from datetime import timedelta

from fastapi.testclient import TestClient
from pymongo.errors import ServerSelectionTimeoutError

from api import cifrado, config, db, errores, rutas_datos
from api.main import app
from api.seguridad import ahora, hash_password
from tests.conftest import CSRF, PASSWORD_ADMIN, SECRETO_ADMIN, codigo_actual, login, registrar

PASSWORD = "Coral-Seguro-2026"
PDF_VALIDO = (
    b"%PDF-1.4\n1 0 obj\n<< /Type /Catalog /Pages 2 0 R >>\nendobj\n"
    b"2 0 obj\n<< /Type /Pages /Kids [] /Count 0 >>\nendobj\ntrailer\n<< /Root 1 0 R >>\n%%EOF\n"
)
# Encabezado real de un ejecutable de Windows (MZ … "This program cannot be run in DOS mode").
EXE = b"MZ\x90\x00\x03\x00\x00\x00\x04\x00\x00\x00\xff\xff\x00\x00" + b"\x00" * 48 + b"This program cannot be run in DOS mode.\r\n" + b"\x00" * 400


def _subir(c, contenido, nombre="carta.pdf", tipo="application/pdf"):
    return c.post(
        "/auth/solicitud/soporte",
        content=contenido,
        headers={**CSRF, "Content-Type": tipo, "X-Nombre-Archivo": nombre},
    )


def _configurar(admin, **valores):
    r = admin.patch("/admin/configuracion/sesion", json=valores, headers=CSRF)
    assert r.status_code == 200, r.text
    return r.json()["valores"]


# 13 -----------------------------------------------------------------
def test_13_la_api_nunca_devuelve_la_contrasena(cliente):
    r = registrar(cliente, password="ABC-frase-larga-segura")
    assert "ABC-frase" not in r.text and "password" not in r.json()["usuario"]
    assert "ABC-frase" not in cliente.get("/auth/me").text


# 14 -----------------------------------------------------------------
def test_14_exe_renombrado_a_pdf_se_rechaza_por_su_contenido(cliente):
    registrar(cliente)
    r = _subir(cliente, EXE, nombre="carta_universidad.pdf")
    assert r.status_code == 415
    assert "programa ejecutable de Windows" in r.json()["detail"]
    assert db.documentos.count_documents({}) == 0
    evento = db.auditoria_accesos.find_one({"evento": "archivo_rechazado"})
    assert evento["exito"] is False
    assert "extensión falsificada" in evento["detalle"]["motivo"]
    assert evento["detalle"]["archivo"] == "carta_universidad.pdf"


def test_14b_otros_archivos_no_validos(cliente):
    registrar(cliente)
    assert _subir(cliente, PDF_VALIDO, nombre="carta.exe").status_code == 400  # extensión
    assert _subir(cliente, b"hola, no soy un pdf", nombre="carta.pdf").status_code == 415  # firma
    assert _subir(cliente, PDF_VALIDO, tipo="application/x-msdownload").status_code == 415  # tipo
    con_js = PDF_VALIDO.replace(b"/Type /Catalog", b"/Type /Catalog /OpenAction << /S /JavaScript /JS (app.alert(1)) >>")
    r = _subir(cliente, con_js)
    assert r.status_code == 415 and "JavaScript" in r.json()["detail"]
    grande = PDF_VALIDO[:-7] + b"0" * (2 * 1024 * 1024) + b"\n%%EOF\n"
    assert _subir(cliente, grande).status_code == 413
    assert _subir(cliente, b"").status_code == 400
    assert db.documentos.count_documents({}) == 0
    assert db.auditoria_accesos.count_documents({"evento": "archivo_rechazado"}) == 6


def test_14c_pdf_valido_se_adjunta_cifrado_y_el_admin_lo_descarga(cliente, admin):
    registrar(cliente)
    r = _subir(cliente, PDF_VALIDO, nombre="../../etc/carta<script>.pdf")
    assert r.status_code == 201, r.text
    soporte = r.json()["soporte"]
    assert soporte["nombre"] == "cartascript.pdf"  # sin rutas ni caracteres peligrosos
    r = cliente.post(
        "/auth/solicitar-investigador",
        json={"institucion": "Universidad del Mar", "motivo": "Tesis sobre blanqueamiento coralino", "soporte_id": soporte["id"]},
        headers=CSRF,
    )
    assert r.status_code == 200 and r.json()["usuario"]["solicitud"]["soporte"]["nombre"] == "cartascript.pdf"

    crudo = db.documentos.cruda.find_one({})
    assert not bytes(crudo["contenido"]).startswith(b"%PDF")  # guardado cifrado
    assert crudo["nombre_original"].startswith(cifrado.PREFIJO)

    usuario_id = cliente.get("/auth/me").json()["usuario"]["id"]
    r = admin.get(f"/admin/usuarios/{usuario_id}/soporte")
    assert r.status_code == 200 and r.content == PDF_VALIDO
    assert r.headers["content-type"] == "application/pdf"
    assert r.headers["content-disposition"].startswith("attachment")
    assert cliente.get(f"/admin/usuarios/{usuario_id}/soporte").status_code == 403


# 15 -----------------------------------------------------------------
def test_15_misma_cuenta_en_dos_navegadores(admin, crear_cliente):
    assert _configurar(admin, sesiones_simultaneas=1)["sesiones_simultaneas"] == 1
    chrome = crear_cliente()
    chrome.headers["User-Agent"] = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) Chrome/130.0 Safari/537.36"
    assert registrar(chrome).status_code == 201

    firefox = crear_cliente()
    firefox.headers["User-Agent"] = "Mozilla/5.0 (Windows NT 10.0; rv:131.0) Gecko/20100101 Firefox/131.0"
    r = login(firefox, "ana@ejemplo.org", PASSWORD)
    assert r.status_code == 200
    assert r.json()["sesiones_cerradas"] == ["Chrome en Windows"]

    # El primer navegador queda fuera y se le explica por qué.
    assert chrome.get("/auth/me").json()["usuario"] is None
    r = chrome.post("/auth/refresh", headers=CSRF)
    assert r.status_code == 401 and "otro navegador" in r.json()["detail"]
    assert r.json()["accion"] == "sesion-reemplazada"
    assert chrome.get("/auth/estado").json()["motivo"] in ("reemplazada", "cerrada")
    assert firefox.get("/auth/me").json()["usuario"] is not None
    evento = db.auditoria_accesos.find_one({"evento": "sesion_reemplazada"})
    assert evento["detalle"]["cerradas"] == "Chrome en Windows"
    assert evento["detalle"]["nueva"] == "Firefox en Windows"
    # No se confunde con un robo de sesión.
    assert db.auditoria_accesos.count_documents({"evento": "refresh_reutilizado"}) == 0


def test_15b_varias_sesiones_permitidas_y_cerrar_las_demas(admin, crear_cliente):
    _configurar(admin, sesiones_simultaneas=2)
    a, b, c = crear_cliente(), crear_cliente(), crear_cliente()
    registrar(a)
    assert login(b, "ana@ejemplo.org", PASSWORD).json()["sesiones_cerradas"] == []
    lista = b.get("/auth/sesiones").json()
    assert lista["limite"] == 2 and len(lista["sesiones"]) == 2
    assert [s["actual"] for s in lista["sesiones"]] == [True, False]
    # Una tercera sesión cierra la que lleva más tiempo sin usarse (a).
    db.sesiones.update_many({}, {"$set": {"ultima_actividad": ahora() - timedelta(minutes=1)}})
    b.get("/auth/sesiones")  # b registra actividad
    db.sesiones.update_one({"revocado_en": None, "familia": lista["sesiones"][0]["id"]}, {"$set": {"ultima_actividad": ahora()}})
    assert len(login(c, "ana@ejemplo.org", PASSWORD).json()["sesiones_cerradas"]) == 1
    assert a.get("/auth/me").json()["usuario"] is None
    assert b.get("/auth/me").json()["usuario"] is not None
    # Desde c se cierran las demás.
    assert c.post("/auth/sesiones/cerrar-otras", headers=CSRF).json()["cerradas"] == 1
    assert b.get("/auth/me").json()["usuario"] is None
    assert b.post("/auth/refresh", headers=CSRF).json()["accion"] == "sesion-remota"
    assert c.get("/auth/me").json()["usuario"] is not None


def test_15c_limite_de_sesiones_validado(admin):
    for valor in (0, 6):
        assert admin.patch("/admin/configuracion/sesion", json={"sesiones_simultaneas": valor}, headers=CSRF).status_code == 400


# 16 -----------------------------------------------------------------
def test_16_fallo_forzado_queda_en_el_registro_de_errores(admin):
    with TestClient(app, raise_server_exceptions=False) as c:
        c.cookies = admin.cookies
        r = c.post("/admin/errores/simular", headers=CSRF)
    assert r.status_code == 500
    referencia = r.json()["referencia"]
    assert referencia in r.json()["detail"]
    assert "Traceback" not in r.text and "RuntimeError" not in r.text  # sin detalles internos
    lista = admin.get("/admin/errores").json()["errores"]
    error = next(e for e in lista if e["referencia"] == referencia)
    assert error["tipo"] == "RuntimeError" and error["estado"] == 500
    assert error["ruta"] == "/admin/errores/simular" and "Traceback" in error["traza"]
    assert db.auditoria_accesos.count_documents({"evento": "fallo_simulado"}) == 1
    with open(f"{errores.CARPETA_LOGS}/errores.log", encoding="utf-8") as archivo:
        assert referencia in archivo.read()


def test_16b_caida_de_la_base_de_datos_se_registra_al_volver(admin, cliente, monkeypatch):
    registrar(cliente)
    db.usuarios.update_one({"email": "ana@ejemplo.org"}, {"$set": {"roles": ["investigador"]}})

    def caida(*args, **kwargs):
        raise ServerSelectionTimeoutError("mongodb:27017: [Errno 111] Connection refused")

    class BaseDeDatosCaida:
        def __getattr__(self, nombre):
            return caida

    monkeypatch.setattr(rutas_datos, "coleccion", BaseDeDatosCaida())
    with TestClient(app, raise_server_exceptions=False) as c:
        c.cookies = cliente.cookies
        r = c.get("/resumen")
    assert r.status_code == 503
    referencia = r.json()["referencia"]
    assert "Connection refused" not in r.text
    assert len(errores._pendientes) >= 1  # se guardó en memoria mientras la BD estaba caída
    monkeypatch.undo()
    lista = admin.get("/admin/errores").json()["errores"]  # la BD volvió: se escriben
    error = next(e for e in lista if e["referencia"] == referencia)
    assert error["estado"] == 503 and error["registrado_tarde"] is True


def test_16c_solo_administradores_ven_los_errores(cliente):
    registrar(cliente)
    assert cliente.get("/admin/errores").status_code == 403
    assert cliente.post("/admin/errores/simular", headers=CSRF).status_code == 403


# 17 -----------------------------------------------------------------
def test_17_cerrar_sesion_en_una_pestana_invalida_la_otra(cliente):
    registrar(cliente)
    db.usuarios.update_one({"email": "ana@ejemplo.org"}, {"$set": {"roles": ["investigador"]}})
    assert cliente.get("/resumen").status_code == 200
    # Segunda pestaña: mismas cookies (mismo navegador). Aun si guardara una
    # copia de las cookies antiguas, el servidor ya cerró la sesión.
    segunda = TestClient(app)
    for cookie in cliente.cookies.jar:
        segunda.cookies.set(cookie.name, cookie.value, path=cookie.path)
    assert segunda.get("/resumen").status_code == 200
    assert cliente.post("/auth/logout", headers=CSRF).status_code == 200
    assert segunda.get("/resumen").status_code == 401
    r = segunda.post("/auth/refresh", headers=CSRF)
    assert r.status_code == 401 and r.json()["accion"] == "sesion-logout"


# 18 -----------------------------------------------------------------
def _texto_crudo(coleccion):
    return " ".join(str(d) for d in coleccion.cruda.find({}))


def test_18_datos_sensibles_cifrados_en_la_base_de_datos(cliente):
    registrar(cliente, email="ana@ejemplo.org", nombre="Ana Pérez")
    cliente.post(
        "/auth/solicitar-investigador",
        json={"institucion": "Universidad del Mar", "motivo": "Tesis sobre blanqueamiento coralino"},
        headers=CSRF,
    )
    crudo = db.usuarios.cruda.find_one({})
    assert crudo["password_hash"].startswith("$argon2id$")  # contraseña: hash irreversible
    assert PASSWORD not in str(crudo)
    for campo in ("email", "nombre"):
        assert crudo[campo].startswith(cifrado.PREFIJO)
    assert crudo["consentimiento"]["ip"].startswith(cifrado.PREFIJO)
    assert crudo["solicitud"]["institucion"].startswith(cifrado.PREFIJO)
    assert len(crudo["email_hmac"]) == 64  # índice ciego para buscar sin descifrar
    for coleccion in (db.usuarios, db.sesiones, db.auditoria_accesos):
        texto = _texto_crudo(coleccion)
        assert "ana@ejemplo.org" not in texto and "Ana Pérez" not in texto and "testclient" not in texto
        assert "Universidad del Mar" not in texto
    # La aplicación sigue funcionando con los datos cifrados.
    assert cliente.get("/auth/me").json()["usuario"]["email"] == "ana@ejemplo.org"
    assert login(TestClient(app), "ANA@ejemplo.org", PASSWORD).status_code == 200


def test_18b_cuentas_antiguas_se_cifran_al_iniciar(cliente):
    db.usuarios.cruda.insert_one(
        {
            "nombre": "Cuenta Antigua",
            "email": "antigua@ejemplo.org",
            "password_hash": hash_password(PASSWORD),
            "roles": ["usuario"],
            "activo": True,
            "token_version": 0,
            "creado_en": ahora(),
        }
    )
    db.crear_indices()  # lo que hace la API al arrancar
    crudo = db.usuarios.cruda.find_one({"nombre": {"$ne": None}, "email_hmac": cifrado.indice("antigua@ejemplo.org")})
    assert crudo["email"].startswith(cifrado.PREFIJO) and crudo["nombre"].startswith(cifrado.PREFIJO)
    assert login(cliente, "antigua@ejemplo.org", PASSWORD).status_code == 200


def test_18c_el_admin_ve_los_datos_descifrados(admin, cliente):
    registrar(cliente)
    lista = admin.get("/admin/usuarios?q=ana@ejemplo").json()["usuarios"]
    assert [u["email"] for u in lista] == ["ana@ejemplo.org"]
    eventos = admin.get("/admin/auditoria?evento=registro").json()["eventos"]
    assert eventos[0]["email"] == "ana@ejemplo.org"


# 19 -----------------------------------------------------------------
def test_19_cambiar_correo_y_contrasena_desde_el_perfil(cliente, crear_cliente):
    registrar(cliente)
    otro_navegador = crear_cliente()
    assert login(otro_navegador, "ana@ejemplo.org", PASSWORD).status_code == 200
    registrar(crear_cliente(), email="beto@ejemplo.org", nombre="Beto Ruiz")

    def cambiar(email, password=PASSWORD):
        return cliente.post("/auth/cambiar-email", json={"email_nuevo": email, "password": password}, headers=CSRF)

    assert cambiar("nueva@ejemplo.org", "Clave-incorrecta-1").status_code == 400
    assert cambiar("no-es-un-correo").status_code == 422
    assert cambiar("ana@ejemplo.org").status_code == 400  # igual al actual
    r = cambiar("BETO@ejemplo.org")
    assert r.status_code == 409 and "beto" not in r.text.lower()
    r = cambiar("ana.nueva@ejemplo.org")
    assert r.status_code == 200 and r.json()["usuario"]["email"] == "ana.nueva@ejemplo.org"

    # La sesión actual sigue; la del otro navegador se cierra.
    assert cliente.get("/auth/me").json()["usuario"]["email"] == "ana.nueva@ejemplo.org"
    assert otro_navegador.get("/auth/me").json()["usuario"] is None
    assert otro_navegador.post("/auth/refresh", headers=CSRF).json()["accion"] == "sesion-credenciales"
    assert login(crear_cliente(), "ana@ejemplo.org", PASSWORD).status_code == 401
    assert login(crear_cliente(), "ana.nueva@ejemplo.org", PASSWORD).status_code == 200
    assert db.auditoria_accesos.count_documents({"evento": "cambio_email", "exito": True}) == 1

    # Y la contraseña, desde el mismo perfil.
    r = cliente.post(
        "/auth/cambiar-password",
        json={"password_actual": PASSWORD, "password_nueva": "Otra-Frase-Segura-2026"},
        headers=CSRF,
    )
    assert r.status_code == 200
    assert login(crear_cliente(), "ana.nueva@ejemplo.org", "Otra-Frase-Segura-2026").status_code == 200


def test_19b_con_2fa_el_cambio_de_correo_pide_el_codigo(admin):
    r = admin.post(
        "/auth/cambiar-email",
        json={"email_nuevo": "jefa@coraleum.org", "password": PASSWORD_ADMIN},
        headers=CSRF,
    )
    assert r.status_code == 400 and "código" in r.json()["detail"]
    r = admin.post(
        "/auth/cambiar-email",
        json={"email_nuevo": "jefa@coraleum.org", "password": PASSWORD_ADMIN, "codigo": codigo_actual(SECRETO_ADMIN, 1)},
        headers=CSRF,
    )
    assert r.status_code == 200 and r.json()["usuario"]["email"] == "jefa@coraleum.org"
    assert config.COOKIE_ACCESS in admin.cookies
