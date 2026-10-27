# Coraleum — Explorador de Estrés Térmico en Corales

Aplicación para consultar datos NOAA Coral Reef Watch asociados a las 47 áreas coralinas del PNN Corales del Rosario y de San Bernardo.

## Arquitectura actual

```text
                  NOAA / datos históricos
                           │
                           ▼
                       MongoDB
                    (contenedor Docker)
                           │
                           ▼
                    FastAPI / Python
                       puerto 8000
                           │
                           ▼
                 Nginx + React / Vite
                       puerto 3000
```

El frontend ya no contiene datos térmicos de prueba. Consulta la API y la API consulta MongoDB.

La geometría del mapa proviene de `datos/areas_coralinas_pnn.geojson`, por lo que los polígonos se dibujan con la forma geográfica real del archivo, en lugar de usar puntos `mapX/mapY` inventados.

> El GeoJSON incluido solamente tiene `FID` y `ETIQUETA`; por eso la interfaz identifica las áreas mediante su FID. No se inventaron nombres de áreas que no existan en los datos fuente.

## Cambios principales

- Frontend convertido de TypeScript/TSX a JavaScript/JSX.
- React + Vite mantenidos como stack del frontend.
- Datos térmicos obtenidos desde MongoDB mediante FastAPI.
- Fechas disponibles obtenidas desde `/api/fechas`.
- Áreas obtenidas desde `/api/areas?fecha=...`.
- Histórico obtenido desde `/api/areas/{fid}/historico`.
- Resumen territorial obtenido desde `/api/resumen`.
- GeoJSON obtenido desde `/api/geojson`.
- Mapa SVG basado en los polígonos reales del GeoJSON.
- Backend dockerizado y conectado al servicio MongoDB mediante el hostname `mongodb` de Docker Compose.
- Frontend Nginx configurado para hacer proxy de `/api/*` hacia FastAPI.
- En desarrollo con Vite, `/api/*` se proxifica a `http://localhost:8000`.

## 1. Configurar variables de entorno

Copia `.env.example` como `.env` y reemplaza **todos** los valores:

```env
MONGO_INITDB_ROOT_USERNAME=admin_coraleum      # administrador (solo scripts)
MONGO_INITDB_ROOT_PASSWORD=clave_larga_1
MONGO_APP_USERNAME=coraleum_api                # usuario que usa la API
MONGO_APP_PASSWORD=clave_larga_2
MONGO_DATABASE=proyecto_noaa
CORS_ORIGINS=http://localhost:3000,http://127.0.0.1:3000,http://localhost:5173
ENABLE_DOCS=false
JWT_SECRET=clave_larga_3                       # firma de las sesiones (mín. 32 caracteres)
COOKIE_SECURE=false                            # true solo con HTTPS
```

Para generar claves seguras (para `JWT_SECRET` usa 48 en lugar de 24):

```bash
python -c "import secrets; print(secrets.token_urlsafe(24))"
```

No subas `.env` al repositorio (está en `.gitignore`).

La primera vez que MongoDB arranca con el volumen vacío ejecuta
`mongo-init/01-crear-usuario-app.js`, que crea el usuario de la aplicación con
permisos `readWrite` **solo** sobre `proyecto_noaa`. La API nunca usa el usuario
administrador.

## 2. Levantar todo con Docker

Desde la raíz del proyecto:

```bash
docker compose up -d --build
```

Esto levanta:

| Servicio | Puerto | Uso |
|---|---|---|
| `mongodb` | `127.0.0.1:27017` (solo este equipo) | Base de datos, con autenticación |
| `backend` | no publicado | FastAPI, accesible solo por Nginx en `/api` |
| `frontend` | `3000` | React servido por Nginx |

Abre:

```text
http://localhost:3000
```

Comprobación de salud de la API (a través de Nginx):

```text
http://localhost:3000/api/health
```

La documentación interactiva (`/docs`) está desactivada por defecto. Para usarla
en desarrollo pon `ENABLE_DOCS=true` en `.env`, descomenta el bloque `ports` del
servicio `backend` en `docker-compose.yml` y abre `http://localhost:8000/docs`.

## 3. Conexión frontend → backend cuando ambos están dockerizados

El navegador entra a `http://localhost:3000`.

El frontend solicita, por ejemplo:

```text
/api/areas?fecha=2026-09-03%2012:00:00
```

Nginx recibe esa solicitud y la reenvía internamente a:

```text
http://backend:8000/areas?fecha=2026-09-03%2012:00:00
```

`backend` es el nombre del servicio Docker y funciona porque ambos servicios están en la misma red creada por Docker Compose.

Esto evita poner `localhost:8000` dentro del código del navegador cuando el frontend está dentro de Docker.

## 4. Desarrollo del frontend fuera de Docker

Primero descomenta el bloque `ports` del servicio `backend` en `docker-compose.yml` (publica la API solo en `127.0.0.1:8000`). Luego levanta solamente MongoDB + backend:

```bash
docker compose up -d mongodb backend
```

Luego, dentro de `frontend/`:

```bash
npm install
npm run dev
```

Vite escucha en `http://localhost:5173` y tiene configurado un proxy:

```text
/api/* → http://localhost:8000/*
```

Por lo tanto el código React sigue usando `/api/...` y no necesitas cambiar URLs entre desarrollo y producción.

## 5. Cargar los datos en MongoDB

Con MongoDB levantado y el entorno virtual de Python activo, desde la raíz del proyecto:

```bash
python scripts/verificar_integridad.py --check   # el histórico no fue alterado
python scripts/migrar_csv_mongodb.py              # 700 observaciones
python scripts/migrar_pixeles_mongodb.py          # 20 píxeles
python scripts/registrar_integridad_mongodb.py    # registro SHA-256 en auditoria_integridad
```

Los scripts usan el usuario administrador del `.env` y se conectan a
`localhost:27017`, que Docker publica solo para este equipo.

El hash SHA-256 se calcula con los saltos de línea normalizados, así que la
verificación da el mismo resultado en Windows, Linux, Mac y Docker.

Si alguna vez el histórico vuelve a tener valores no numéricos en `sst`, `ssta`,
`hotspot` o `dhw`, `migrar_csv_mongodb.py` se detiene y pide ejecutar
`python scripts/reparar_historico.py` (diagnóstico) y luego
`python scripts/reparar_historico.py --aplicar`.

Si el script se ejecutara dentro de un contenedor, en cambio, debe usar `mongodb:27017`, no `localhost:27017`.

## 6. Endpoints usados por React

### `GET /fechas`

Devuelve las fechas existentes en MongoDB.

### `GET /areas?fecha=YYYY-MM-DD HH:MM:SS`

Devuelve el estado térmico de las áreas para una fecha concreta.

### `GET /areas/{fid}?fecha=YYYY-MM-DD HH:MM:SS`

Devuelve la información de un área para la fecha indicada (o la más reciente si se omite).

### `GET /areas/{fid}/historico`

Devuelve la serie histórica de esa área.

### `GET /resumen`

Calcula los KPIs territoriales directamente a partir de MongoDB.

### `GET /geojson`

Devuelve la geometría real de las 47 áreas coralinas.

### `GET /health`

Comprueba la conexión con MongoDB (público).

### `GET /estadisticas`

Totales de áreas, píxeles y fechas para la página de inicio (público, sin valores ambientales).

### Autenticación y administración

`POST /auth/registro`, `POST /auth/login`, `POST /auth/refresh`, `POST /auth/logout`,
`GET /auth/me`, `POST /auth/cambiar-password`, `POST /auth/solicitar-investigador`,
`GET /admin/usuarios`, `PATCH /admin/usuarios/{id}`, `POST /admin/usuarios/{id}/solicitud`,
`POST /admin/usuarios/{id}/restablecer-password`, `GET /admin/auditoria`, `GET /admin/integridad`.

Las rutas de datos (`/fechas`, `/areas`, `/areas/{fid}`, `/areas/{fid}/historico`,
`/resumen`, `/geojson`) requieren rol **investigador** o **admin**.

## 7. Usuarios, roles e inicio de sesión

| Rol | Cómo se obtiene | Acceso |
|---|---|---|
| Visitante | Sin cuenta | Inicio, Conoce los Corales, Estrés Térmico, Indicadores NOAA, Metodología, asistente Coral |
| Usuario | Registro abierto en la aplicación | Lo anterior + solicitar acceso de investigador |
| Investigador | Lo aprueba un administrador | + Explorador Térmico (mapa, fechas, detalle, histórico) y Resumen |
| Administrador | Por consola (abajo) | Todo + gestión de usuarios, solicitudes y auditoría |

La autorización se aplica en el **backend**: sin el rol, la API responde 401/403
aunque se llame directamente.

### Crear el primer administrador

Con los contenedores encendidos:

```bash
docker compose exec backend python -m api.cli crear-admin
```

Pide correo, nombre y contraseña (oculta). Si el correo ya existe, ofrece
convertir esa cuenta en administrador.

### Recuperar una contraseña

En **Administración → Usuarios → Restablecer clave** se genera una contraseña
temporal que se muestra una sola vez. Al iniciar sesión con ella, el usuario
debe crear una nueva antes de usar la aplicación.

### Medidas de seguridad

- Contraseñas con **Argon2id**; mínimo 10 caracteres y rechazo de contraseñas comunes.
- Sesión en cookies **HttpOnly + SameSite=Strict** (JavaScript no puede leerlas):
  token de acceso de 15 min y refresh token de 7 días, **rotativo** y guardado
  como hash. Reutilizar un refresh token ya usado revoca todas las sesiones derivadas.
- Protección **CSRF**: encabezado `X-Requested-With: Coraleum` y verificación de `Origin`.
- **Bloqueo** de la cuenta 15 min tras 5 intentos fallidos y **límite de peticiones**
  por IP en inicio de sesión y registro.
- El rol se lee de la base de datos en cada petición: los cambios de rol y las
  desactivaciones aplican de inmediato.
- **Auditoría** de accesos (colección `auditoria_accesos`, 180 días) visible para el administrador.

Con HTTPS en producción, pon `COOKIE_SECURE=true` en `.env` y agrega el dominio a `CORS_ORIGINS`.

### Verificación en dos pasos (2FA)

Obligatoria para administradores: al entrar a **Administración** por primera vez
se pide activarla escaneando un código QR con Google Authenticator, Microsoft
Authenticator o Authy. Se entregan 8 códigos de recuperación de un solo uso.
Para el resto de cuentas es opcional, desde **Mi cuenta**.

Si alguien pierde el celular y los códigos, otro administrador puede quitarle la
2FA en **Administración → Usuarios → Quitar 2FA**.

## 8. Protección de datos personales (Ley 1581 de 2012)

- El registro exige aceptar la **política de tratamiento de datos** (casilla obligatoria).
  Se guarda la prueba del consentimiento: versión, fecha, IP y medio.
- Las cuentas creadas antes, o cuando cambia la política, deben aceptarla al iniciar sesión.
- En **Mi cuenta** cada persona puede **descargar sus datos** (JSON) y **eliminar su cuenta**.
  Al eliminarla se borran sus datos y su registro de auditoría queda anónimo.
- La política está en `frontend/src/views/ViewPrivacidad.jsx`. **Antes de publicar,
  completen los campos marcados `[COMPLETAR]`** (dirección, correo y teléfono de contacto).
  Si cambian el texto, suban la versión en `POLITICA_VERSION` (`api/config.py`) y en
  `VERSION` (`ViewPrivacidad.jsx`).

## 9. Copias de seguridad

Con Docker encendido y el entorno virtual activo:

```bash
python scripts/respaldo_mongodb.py respaldar            # crea y verifica una copia
python scripts/respaldo_mongodb.py listar
python scripts/respaldo_mongodb.py verificar ARCHIVO
python scripts/respaldo_mongodb.py restaurar ARCHIVO    # pide escribir RESTAURAR
```

Las copias quedan en `respaldos/` (excluida de Git) con su huella SHA-256. Se conservan
las últimas 14. **Contienen datos personales: guárdenlas en un lugar privado.**

Para programarla todos los días a las 11 p. m. en Windows (ajuste la ruta si el
proyecto no está en `C:\Proyectos\Coraleum`; la ruta no debe tener espacios):

```powershell
schtasks /Create /SC DAILY /ST 23:00 /TN "Coraleum respaldo" /TR "C:\Proyectos\Coraleum\.venv\Scripts\python.exe C:\Proyectos\Coraleum\scripts\respaldo_mongodb.py respaldar"
```

Docker Desktop debe estar abierto a esa hora. Para quitar la tarea:
`schtasks /Delete /TN "Coraleum respaldo" /F`.

## 10. Pruebas automáticas y revisión de seguridad

```bash
pip install -r requirements-dev.txt
pytest                                   # 48 pruebas; no necesitan Docker
pip install pip-audit bandit
pip-audit -r api/requirements.txt        # vulnerabilidades en librerías de Python
bandit -r api scripts -ll                # análisis estático del código
cd frontend && npm audit                 # vulnerabilidades en librerías del frontend
```

En GitLab, `.gitlab-ci.yml` ejecuta todo esto automáticamente en cada `push`, más
**Gitleaks** (busca contraseñas o claves subidas por error en todo el historial) y la
verificación SHA-256 del histórico.

## Nota sobre la clasificación

`Baja`, `Intermedia` y `Alta` siguen siendo la clasificación relativa que ya utilizaba el backend. No representan categorías oficiales de alerta de NOAA.
