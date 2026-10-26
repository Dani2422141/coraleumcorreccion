# Correcciones de seguridad y funcionamiento (octubre 2026)

Resumen de los problemas encontrados en la revisión del código y de cómo se corrigieron.
Sirve como registro para el equipo y como insumo para los apartados 2.5 (Seguridad)
y 2.6 (Pruebas) del documento.

## Seguridad

| # | Problema | Riesgo | Corrección |
|---|---|---|---|
| S1 | MongoDB arrancaba **sin autenticación** y con el puerto 27017 publicado a la red | Cualquiera en la red podía leer, modificar o borrar la base | Autenticación activada desde `.env`; puerto publicado solo en `127.0.0.1`; imagen fija `mongo:8.0` |
| S2 | La API usaba una cadena de conexión sin credenciales | Contradecía RS03 | La API usa un **usuario propio** con permisos `readWrite` solo sobre `proyecto_noaa` (`mongo-init/`); nunca el administrador |
| S3 | Backend publicado directamente en el puerto 8000 | Superficie expuesta innecesaria | Sin puerto publicado; solo accesible por Nginx en `/api` |
| S4 | `/health` devolvía el texto del error interno | Fuga de información (RS05) | Respuesta genérica; el detalle va al log |
| S5 | Errores no controlados podían exponer trazas | Fuga de información (RS05) | Manejadores globales de errores con mensajes genéricos |
| S6 | `/docs` y `/openapi.json` siempre públicos | Exposición de la API | Desactivados por defecto (`ENABLE_DOCS`) |
| S7 | Nginx sin cabeceras de seguridad | Clickjacking, *MIME sniffing* | `X-Frame-Options`, `nosniff`, `Referrer-Policy`, `Permissions-Policy`, CSP en modo reporte, `server_tokens off` |
| S8 | Leaflet cargado desde unpkg sin verificación de integridad | Inyección de código si el CDN se compromete | Leaflet instalado con npm y empaquetado por Vite |
| S9 | Contenedor del backend ejecutado como root | Mayor impacto ante una vulnerabilidad | Usuario sin privilegios en `api/Dockerfile` |
| S10 | `.env.example` ausente; `__pycache__` en el repositorio | Configuración insegura por desconocimiento | `.env.example` restaurado; `.gitignore` y `.dockerignore` completos |

## Datos e integridad

| # | Problema | Corrección |
|---|---|---|
| D1 | `backfill_noaa.py` guardaba la **respuesta cruda de NOAA** (texto) en vez del valor numérico. 520 de 700 filas (26 de 35 fechas) estaban corruptas | Error corregido en el script. Datos recuperados con `scripts/reparar_historico.py`, que verifica fecha, latitud y longitud de cada valor antes de aceptarlo |
| D2 | La migración no validaba que los valores fueran numéricos | `migrar_csv_mongodb.py` ahora rechaza valores no numéricos |
| D3 | La migración exigía "exactamente 40 registros" y "2 fechas" (valores de la primera carga) | Ahora valida que la serie esté completa: píxeles × fechas |
| D4 | El SHA-256 cambiaba según el sistema operativo (saltos de línea CRLF/LF): la verificación fallaba en Linux, Mac y Docker | El hash se calcula con saltos de línea normalizados en los tres scripts |
| D5 | `verificar_integridad.py` comparaba la línea completa del `.sha256`, pero `backfill_noaa.py` escribe `hash  archivo`: la verificación fallaba tras cada backfill | Se compara solo el hash |

## Funcionamiento

| # | Problema | Corrección |
|---|---|---|
| F1 | El detalle de un área mostraba siempre la **última fecha**, aunque en el mapa se eligiera otra | `/areas/{fid}?fecha=...` y el frontend envía la fecha seleccionada |
| F2 | `/areas/{fid}/historico` hacía 35 consultas (una por fecha) | Una sola consulta agregada; mismos resultados |
| F3 | Título y descripción de la página con caracteres dañados (`EstrÃ©s`) | `index.html` guardado en UTF-8 |
| F4 | `App.jsx` navegaba a una vista `historico` inexistente | Código muerto eliminado |

## Verificación realizada

- Las respuestas de `/fechas`, `/areas`, `/areas/{fid}`, `/areas/{fid}/historico` y `/resumen`
  son **idénticas** a las de la versión anterior para las 47 áreas y las 35 fechas
  (salvo F1, que es la corrección buscada).
- `verificar_integridad.py --check` confirma el histórico reparado y detecta la alteración de un solo valor.
- `migrar_csv_mongodb.py` carga 700 documentos numéricos y rechaza el CSV corrupto original.
- `npm run build` compila el frontend sin errores.

## Autenticación y roles (nuevo)

| Control | Implementación |
|---|---|
| Almacenamiento de contraseñas | Argon2id (`argon2-cffi`), rehash automático si cambian los parámetros |
| Política de contraseñas | Mínimo 10 caracteres, máximo 128, rechazo de comunes y de las que contienen el correo o el nombre (NIST SP 800-63B) |
| Sesión | JWT HS256 de 15 min + refresh token opaco de 7 días; ambos en cookies HttpOnly, SameSite=Strict (`Secure` con HTTPS) |
| Rotación de sesión | Cada renovación invalida el refresh token anterior; reutilizarlo revoca toda la familia (detección de robo) |
| Revocación | `token_version` por usuario: cambio de contraseña, restablecimiento o desactivación cierran todas las sesiones |
| CSRF | Encabezado obligatorio `X-Requested-With` + validación de `Origin` + SameSite=Strict |
| Fuerza bruta | Bloqueo 15 min tras 5 fallos; límite por IP (login 10/5 min, registro 5/h) |
| Enumeración de cuentas | Mismo mensaje y tiempo de respuesta para correo inexistente y contraseña incorrecta |
| Autorización | Dependencias de FastAPI por rol en el backend; rol leído de la BD en cada petición |
| Mínimo privilegio | Registro solo crea "usuario"; investigador requiere aprobación; no se puede auto-asignar rol (campos extra rechazados) |
| Protección del administrador | No puede quitarse su rol ni desactivarse; siempre queda al menos un admin activo |
| Auditoría | `auditoria_accesos`: registros, inicios de sesión (exitosos y fallidos), bloqueos, cambios de rol, solicitudes, restablecimientos, accesos denegados. Sin contraseñas ni tokens. Caduca a los 180 días |
| Validación de entradas | Modelos Pydantic estrictos (`extra=forbid`), `EmailStr`, longitudes máximas; búsqueda con `re.escape` (sin inyección de regex) |

### Propuesta de requisitos para el documento (sección 2.2)

| Código | Requisito |
|---|---|
| RF14 | El sistema debe permitir el registro de usuarios con nombre, correo y contraseña. |
| RF15 | El sistema debe permitir iniciar y cerrar sesión. |
| RF16 | El sistema debe permitir a un usuario registrado solicitar acceso como investigador indicando institución y motivo. |
| RF17 | El sistema debe permitir al administrador aprobar o rechazar solicitudes, cambiar roles, activar o desactivar cuentas y restablecer contraseñas. |
| RF18 | El sistema debe restringir el Explorador Térmico, el detalle por área y el histórico a los roles investigador y administrador. |
| RF19 | El sistema debe permitir al administrador consultar el registro de auditoría de accesos. |
| RS09 | Las contraseñas deben almacenarse con una función de derivación resistente (Argon2id). |
| RS10 | Las sesiones deben gestionarse con cookies HttpOnly y SameSite, con expiración y revocación. |
| RS11 | La autorización debe validarse en el backend según el rol en cada petición. |
| RS12 | El sistema debe limitar los intentos de inicio de sesión y bloquear temporalmente la cuenta. |
| RS13 | El sistema debe proteger las operaciones que modifican datos contra CSRF. |
| RS14 | El sistema debe registrar los eventos de seguridad sin almacenar secretos. |

Pruebas: `tests/test_auth.py` (28 casos) verifica cada uno de estos controles.
