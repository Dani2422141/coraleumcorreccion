"""Las 13 pruebas solicitadas para la sustentación, automatizadas.

Cada función lleva el número de la prueba del enunciado. Resultado
esperado en todas: el sistema controla o rechaza la acción.
"""

from datetime import timedelta

from api import config, db, limites, sesion_config
from api.seguridad import ahora
from tests.conftest import CSRF, login, registrar

PASSWORD = "Coral-Seguro-2026"


def _id(c):
    return c.get("/auth/me").json()["usuario"]["id"]


def _registrar_otro(crear_cliente, email, nombre):
    c = crear_cliente()
    assert registrar(c, email=email, nombre=nombre).status_code == 201
    return c


# 1 ------------------------------------------------------------------
def test_01_la_sesion_no_viaja_en_la_url(cliente, crear_cliente):
    """Copiar la URL en otro navegador no copia la sesión."""
    r = registrar(cliente)
    assert r.status_code == 201
    # La sesión está en cookies HttpOnly, no en la URL ni en el cuerpo.
    assert "token" not in r.text.lower() and "access" not in r.json()["usuario"]
    otro_navegador = crear_cliente()  # mismo servidor, sin las cookies
    assert otro_navegador.get("/auth/me").json() == {"usuario": None}
    assert otro_navegador.get("/fechas").status_code == 401
    # En el navegador original la sesión persiste (p. ej., al recargar).
    assert cliente.get("/auth/me").json()["usuario"]["email"] == "ana@ejemplo.org"


# 2 ------------------------------------------------------------------
def test_02_quince_caracteres_especiales_en_el_correo(cliente):
    especiales = "!#$%&'*+/=?^`{|}"[:15]
    assert len(especiales) == 15
    r = login(cliente, especiales, "Cualquier-clave-1")
    assert r.status_code == 422
    assert r.json()["detail"] == "El correo electrónico no es válido."
    assert especiales not in r.text  # el valor recibido nunca se refleja
    r = cliente.post(
        "/auth/registro",
        json={"nombre": "Ana", "email": especiales, "password": PASSWORD, "acepta_politica": True},
        headers=CSRF,
    )
    assert r.status_code == 422
    assert db.usuarios.count_documents({}) == 0


# 3 ------------------------------------------------------------------
def test_03_olvide_mi_contrasena(cliente, admin, crear_cliente):
    registrar(cliente)
    visitante = crear_cliente()
    existe = visitante.post("/auth/olvide-password", json={"email": "ana@ejemplo.org"}, headers=CSRF)
    no_existe = visitante.post("/auth/olvide-password", json={"email": "nadie@ejemplo.org"}, headers=CSRF)
    # Misma respuesta: no revela qué correos están registrados.
    assert existe.status_code == no_existe.status_code == 200
    assert existe.json() == no_existe.json()

    lista = admin.get("/admin/usuarios").json()
    assert lista["recuperaciones"] == 1
    ana = next(u for u in lista["usuarios"] if u["email"] == "ana@ejemplo.org")
    assert ana["recuperacion_solicitada"] is not None

    temporal = admin.post(f"/admin/usuarios/{ana['id']}/restablecer-password", headers=CSRF).json()["password_temporal"]
    assert admin.get("/admin/usuarios").json()["recuperaciones"] == 0
    nuevo = crear_cliente()
    assert login(nuevo, "ana@ejemplo.org", temporal).json()["usuario"]["debe_cambiar_password"] is True


def test_03b_olvide_mi_contrasena_tiene_limite(cliente):
    codigos = [
        cliente.post("/auth/olvide-password", json={"email": f"x{i}@ejemplo.org"}, headers=CSRF).status_code
        for i in range(7)
    ]
    assert 429 in codigos


# 4 ------------------------------------------------------------------
def test_04_cinco_contrasenas_incorrectas_bloquean(cliente, crear_cliente):
    registrar(cliente)
    otro = crear_cliente()
    codigos = [login(otro, "ana@ejemplo.org", f"Incorrecta-{i}-xyz").status_code for i in range(5)]
    assert codigos == [401, 401, 401, 401, 423]
    assert login(otro, "ana@ejemplo.org", PASSWORD).status_code == 423
    assert db.auditoria_accesos.count_documents({"evento": "cuenta_bloqueada"}) == 1


# 5 ------------------------------------------------------------------
def test_05_rol_nuevo_con_dos_permisos_para_dos_usuarios(admin, crear_cliente):
    u1 = _registrar_otro(crear_cliente, "luisa@ejemplo.org", "Luisa Gómez")
    u2 = _registrar_otro(crear_cliente, "pedro@ejemplo.org", "Pedro Ruiz")
    for c in (u1, u2):
        assert c.get("/fechas").status_code == 403
        assert c.get("/admin/auditoria").status_code == 403

    r = admin.post(
        "/admin/roles",
        json={"nombre": "Analista de datos", "descripcion": "Consulta y auditoría", "permisos": ["datos.consultar", "auditoria.ver"]},
        headers=CSRF,
    )
    assert r.status_code == 201
    clave = r.json()["rol"]["clave"]
    assert r.json()["rol"]["permisos"] == ["auditoria.ver", "datos.consultar"]

    for c in (u1, u2):
        assert admin.patch(f"/admin/usuarios/{_id(c)}", json={"roles": [clave]}, headers=CSRF).status_code == 200
        assert c.get("/auth/me").json()["usuario"]["permisos"] == ["auditoria.ver", "datos.consultar"]
        assert c.get("/areas").status_code == 200  # permiso 1
        assert c.get("/areas/8/historico").status_code == 403  # no tiene histórico
        # Permiso 2 (auditoría): administrativo, por eso exige 2FA primero.
        r = c.get("/admin/auditoria")
        assert r.status_code == 403 and r.json()["accion"] == "configurar-2fa"
        assert c.get("/admin/usuarios").status_code == 403  # no gestiona usuarios


def test_05b_no_se_puede_crear_rol_con_permiso_inexistente_o_nombre_repetido(admin):
    assert admin.post("/admin/roles", json={"nombre": "X1", "permisos": ["borrar.todo"]}, headers=CSRF).status_code == 400
    assert admin.post("/admin/roles", json={"nombre": "Administrador", "permisos": []}, headers=CSRF).status_code == 409


# 6 ------------------------------------------------------------------
def test_06_correo_duplicado(cliente, crear_cliente):
    assert registrar(cliente).status_code == 201
    for variante in ("ana@ejemplo.org", "ANA@Ejemplo.org", "  ana@ejemplo.org  "):
        assert registrar(crear_cliente(), email=variante, nombre="Otra Persona").status_code == 409
    assert db.usuarios.count_documents({}) == 1


# 7 ------------------------------------------------------------------
def test_07_admin_no_puede_poner_contrasena_de_un_caracter(cliente, admin, crear_cliente):
    registrar(cliente)
    usuario_id = _id(cliente)
    for debil in ["1", "a", "123456789101112131415", "abcdefghijkl"]:
        r = admin.post(f"/admin/usuarios/{usuario_id}/establecer-password", json={"password": debil}, headers=CSRF)
        assert r.status_code == 400, debil
    # Una contraseña válida sí se acepta y obliga a cambiarla.
    r = admin.post(f"/admin/usuarios/{usuario_id}/establecer-password", json={"password": "Temporal-del-Arrecife-5"}, headers=CSRF)
    assert r.status_code == 200 and r.json()["usuario"]["debe_cambiar_password"] is True
    eventos = list(db.auditoria_accesos.find({"evento": "password_restablecida"}))
    assert sum(1 for e in eventos if not e["exito"]) == 4 and sum(1 for e in eventos if e["exito"]) == 1


# 8 ------------------------------------------------------------------
def test_08_dos_roles_a_un_usuario_y_todos_sus_permisos(cliente, admin):
    registrar(cliente)
    usuario_id = _id(cliente)
    a = admin.post("/admin/roles", json={"nombre": "Lector", "permisos": ["datos.consultar"]}, headers=CSRF).json()["rol"]["clave"]
    b = admin.post("/admin/roles", json={"nombre": "Historiador", "permisos": ["datos.historico"]}, headers=CSRF).json()["rol"]["clave"]

    r = admin.patch(f"/admin/usuarios/{usuario_id}", json={"roles": [a, b]}, headers=CSRF)
    assert {x["clave"] for x in r.json()["usuario"]["roles"]} == {a, b}
    assert r.json()["usuario"]["permisos"] == ["datos.consultar", "datos.historico"]  # unión
    assert cliente.get("/areas").status_code == 200
    assert cliente.get("/areas/8/historico").status_code == 200

    # Modificar la totalidad de sus permisos: se cambian los de ambos roles.
    admin.patch(f"/admin/roles/{a}", json={"permisos": ["auditoria.ver"]}, headers=CSRF)
    admin.patch(f"/admin/roles/{b}", json={"permisos": ["configuracion.gestionar"]}, headers=CSRF)
    yo = cliente.get("/auth/me").json()["usuario"]
    assert yo["permisos"] == ["auditoria.ver", "configuracion.gestionar"]
    assert cliente.get("/areas").status_code == 403  # aplica de inmediato
    assert cliente.get("/areas/8/historico").status_code == 403


def test_08b_protecciones_contra_escalamiento(cliente, admin, crear_cliente):
    registrar(cliente)
    # Un gestor de usuarios sin todos los permisos no puede dar el rol admin.
    gestor = admin.post("/admin/roles", json={"nombre": "Gestor", "permisos": ["usuarios.gestionar"]}, headers=CSRF).json()["rol"]["clave"]
    g = _registrar_otro(crear_cliente, "gestor@ejemplo.org", "Gestora Uno")
    admin.patch(f"/admin/usuarios/{_id(g)}", json={"roles": [gestor]}, headers=CSRF)
    db.usuarios.update_one({"email": "gestor@ejemplo.org"}, {"$set": {"dos_pasos": {"activo": True}}})
    assert g.get("/admin/usuarios").status_code == 200
    r = g.patch(f"/admin/usuarios/{_id(cliente)}", json={"roles": ["admin"]}, headers=CSRF)
    assert r.status_code == 403
    r = g.patch(f"/admin/usuarios/{_id(g)}", json={"roles": [gestor, "admin"]}, headers=CSRF)
    assert r.status_code == 400  # ni siquiera sobre sí mismo
    assert g.post("/admin/roles", json={"nombre": "Z", "permisos": []}, headers=CSRF).status_code == 403
    # El rol Administrador no se modifica y los del sistema no se eliminan.
    assert admin.patch("/admin/roles/admin", json={"permisos": []}, headers=CSRF).status_code == 400
    assert admin.delete("/admin/roles/investigador", headers=CSRF).status_code == 400
    # Investigador/usuario no pueden recibir permisos administrativos.
    assert admin.patch("/admin/roles/investigador", json={"permisos": ["usuarios.gestionar"]}, headers=CSRF).status_code == 400


def test_08c_eliminar_rol_lo_quita_de_los_usuarios(cliente, admin):
    registrar(cliente)
    clave = admin.post("/admin/roles", json={"nombre": "Temporal", "permisos": ["datos.consultar"]}, headers=CSRF).json()["rol"]["clave"]
    admin.patch(f"/admin/usuarios/{_id(cliente)}", json={"roles": [clave]}, headers=CSRF)
    assert cliente.get("/areas").status_code == 200
    assert admin.delete(f"/admin/roles/{clave}", headers=CSRF).status_code == 200
    assert cliente.get("/areas").status_code == 403
    assert [r["clave"] for r in cliente.get("/auth/me").json()["usuario"]["roles"]] == ["usuario"]


# 9 ------------------------------------------------------------------
def test_09_auditoria_registra_cambios_del_admin(cliente, admin):
    registrar(cliente)
    usuario_id = _id(cliente)
    clave = admin.post("/admin/roles", json={"nombre": "Revisor", "permisos": ["datos.consultar"]}, headers=CSRF).json()["rol"]["clave"]
    admin.patch(f"/admin/roles/{clave}", json={"permisos": ["datos.consultar", "datos.historico"]}, headers=CSRF)
    admin.patch(f"/admin/usuarios/{usuario_id}", json={"roles": [clave, "usuario"]}, headers=CSRF)
    admin.post(f"/admin/usuarios/{usuario_id}/restablecer-password", headers=CSRF)
    admin.patch("/admin/configuracion/sesion", json={"inactividad_minutos": 10}, headers=CSRF)
    admin.patch(f"/admin/usuarios/{usuario_id}", json={"activo": False}, headers=CSRF)

    eventos = admin.get("/admin/auditoria").json()["eventos"]
    nombres = [e["evento"] for e in eventos]
    for esperado in ("rol_creado", "rol_actualizado", "usuario_actualizado", "password_restablecida", "configuracion_actualizada"):
        assert esperado in nombres, esperado
    for e in eventos:
        if e["evento"] in ("rol_creado", "usuario_actualizado", "configuracion_actualizada"):
            assert e["email"] == "admin@coraleum.org"  # quién lo hizo
    cambio_roles = next(e for e in eventos if e["evento"] == "usuario_actualizado" and "roles" in e["detalle"])
    assert cambio_roles["detalle"]["roles"] == ["usuario", f"{clave}, usuario"]
    assert next(e for e in eventos if e["evento"] == "configuracion_actualizada")["detalle"] == {"inactividad_minutos": [30, 10]}


# 10 y 11 ------------------------------------------------------------
def _envejecer_sesiones(minutos):
    db.sesiones.update_many({}, {"$set": {"ultima_actividad": ahora() - timedelta(minutes=minutos)}})


def test_10_reducir_vigencia_del_token(admin, cliente):
    r = admin.patch("/admin/configuracion/sesion", json={"token_minutos": 1}, headers=CSRF)
    assert r.status_code == 200 and r.json()["valores"]["token_minutos"] == 1
    registrar(cliente)
    cookie = next(c for c in cliente.cookies.jar if c.name == config.COOKIE_ACCESS)
    assert 0 < cookie.expires - ahora().timestamp() <= 61  # el token nuevo dura 1 minuto


def test_10b_reducir_inactividad_cierra_la_sesion(admin, cliente):
    registrar(cliente)
    assert cliente.get("/auth/me").json()["usuario"] is not None
    admin.patch("/admin/configuracion/sesion", json={"inactividad_minutos": 1}, headers=CSRF)
    _envejecer_sesiones(2)  # la persona lleva 2 minutos sin usar la aplicación
    estado = cliente.get("/auth/estado").json()
    assert estado["activa"] is False and estado["motivo"] == "inactividad"
    assert cliente.get("/auth/me").json()["usuario"] is None
    r = cliente.post("/auth/refresh", headers=CSRF)
    assert r.status_code == 401
    assert db.auditoria_accesos.count_documents({"evento": "sesion_expirada"}) >= 1


def test_11_aumentar_inactividad_mantiene_la_sesion(admin, cliente):
    registrar(cliente)
    r = admin.patch("/admin/configuracion/sesion", json={"inactividad_minutos": 60}, headers=CSRF)
    assert r.json()["valores"]["inactividad_minutos"] == 60
    _envejecer_sesiones(45)  # 45 minutos sin actividad: con 30 se habría cerrado
    assert cliente.get("/auth/estado").json()["activa"] is True
    assert cliente.get("/auth/me").json()["usuario"] is not None


def test_11b_limites_maximos_de_la_sesion(admin):
    for campo, valor in [("inactividad_minutos", 61), ("inactividad_minutos", 0), ("maxima_horas", 25), ("token_minutos", 0)]:
        r = admin.patch("/admin/configuracion/sesion", json={campo: valor}, headers=CSRF)
        assert r.status_code == 400, (campo, valor)
    assert sesion_config.obtener()["inactividad_minutos"] == 30


def test_11c_actividad_renueva_y_estado_no(admin, cliente):
    registrar(cliente)
    admin.patch("/admin/configuracion/sesion", json={"inactividad_minutos": 5}, headers=CSRF)
    _envejecer_sesiones(4)
    antes = cliente.get("/auth/estado").json()["segundos_restantes_inactividad"]
    assert antes <= 60  # consultar el estado NO cuenta como actividad
    despues = cliente.post("/auth/actividad", headers=CSRF).json()["segundos_restantes_inactividad"]
    assert despues > 280  # usar la aplicación sí la renueva


def test_11d_duracion_maxima_de_la_sesion(cliente):
    registrar(cliente)
    db.sesiones.update_many({}, {"$set": {"inicio": ahora() - timedelta(hours=13)}})
    estado = cliente.get("/auth/estado").json()
    assert estado["activa"] is False and estado["motivo"] == "duracion"


def test_logout_invalida_el_token_de_acceso_al_instante(cliente):
    registrar(cliente)
    acceso = cliente.cookies.get(config.COOKIE_ACCESS)
    cliente.post("/auth/logout", headers=CSRF)
    cliente.cookies.set(config.COOKIE_ACCESS, acceso)  # alguien guardó el token
    assert cliente.get("/auth/me").json()["usuario"] is None


# 12 -----------------------------------------------------------------
def test_12_secuencia_numerica_en_el_login(cliente, crear_cliente):
    registrar(cliente)
    otro = crear_cliente()
    r = login(otro, "ana@ejemplo.org", "123456789101112131415")
    assert r.status_code == 401
    assert r.json()["detail"] == "Correo o contraseña incorrectos."  # no revela la política
    assert db.usuarios.find_one({"email": "ana@ejemplo.org"})["intentos_fallidos"] == 1


# 13 -----------------------------------------------------------------
def test_13_registro_con_secuencia_numerica(cliente):
    r = registrar(cliente, password="123456789101112131415")
    assert r.status_code == 400
    assert "secuencia" in r.json()["detail"]
    for debil in ["98765432109876", "3005551234", "abcdefghijkl", "qwertyuiop12", "abcd1234efgh"]:
        limites.reiniciar()  # el límite de 5 registros por hora por IP es otra protección
        assert registrar(cliente, password=debil).status_code == 400, debil
    assert db.usuarios.count_documents({}) == 0
