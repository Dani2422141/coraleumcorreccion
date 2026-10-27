export const CLASSIFICATION_COLORS = {
  Baja: '#4ade80',
  Intermedia: '#fbbf24',
  Alta: '#ff6b47',
};

// Versión oscura de cada color para TEXTO sobre fondo claro (contraste WCAG AA).
export const CLASSIFICATION_TEXT = {
  Baja: '#15803d',
  Intermedia: '#8a5f00',
  Alta: '#c2410c',
};

export const CLASSIFICATIONS = ['Baja', 'Intermedia', 'Alta'];

const API_BASE = (import.meta.env.VITE_API_URL || '').replace(/\/$/, '');
const API_PREFIX = API_BASE ? '' : '/api';

/** Error de la API con el código HTTP y la acción sugerida por el backend. */
export class ApiError extends Error {
  constructor(message, status, accion = null) {
    super(message);
    this.status = status;
    this.accion = accion;
  }
}

// Aviso global cuando la sesión venció o el backend exige otra acción.
export const EVENTO_SESION = 'coraleum:sesion';

let renovacionEnCurso = null;

let ultimoMotivoVencimiento = '';

async function pedirRenovacion() {
  const r = await fetch(`${API_BASE}${API_PREFIX}/auth/refresh`, {
    method: 'POST',
    credentials: API_BASE ? 'include' : 'same-origin',
    headers: { Accept: 'application/json', 'X-Requested-With': 'Coraleum' },
  });
  if (r.ok) return true;
  let datos = {};
  try { datos = await r.json(); } catch (_) { /* respuesta sin JSON */ }
  // Otra pestaña renovó la sesión en el mismo instante: la cookie nueva ya está.
  if (r.status === 409 && datos.accion === 'reintentar') return true;
  // Motivo del cierre (inactividad, otro navegador…) para mostrarlo en pantalla.
  ultimoMotivoVencimiento = datos.detail || '';
  return false;
}

/**
 * Renueva la sesión con el refresh token (cookie HttpOnly). Una sola a la vez
 * en esta pestaña y, con Web Locks, una sola a la vez entre pestañas.
 */
function renovarSesion() {
  if (!renovacionEnCurso) {
    const bloqueo = typeof navigator !== 'undefined' && navigator.locks?.request
      ? navigator.locks.request('coraleum-renovacion', pedirRenovacion)
      : pedirRenovacion();
    renovacionEnCurso = Promise.resolve(bloqueo)
      .catch(() => false)
      .finally(() => { renovacionEnCurso = null; });
  }
  return renovacionEnCurso;
}

async function request(path, { method = 'GET', body, archivo, comoBlob = false, reintentar = true } = {}) {
  const headers = { Accept: comoBlob ? '*/*' : 'application/json' };
  if (method !== 'GET') {
    // Encabezado exigido por el backend en peticiones que modifican datos (CSRF).
    headers['X-Requested-With'] = 'Coraleum';
  }
  if (body !== undefined) headers['Content-Type'] = 'application/json';
  if (archivo) {
    // El archivo viaja tal cual; el servidor revisa su contenido real.
    headers['Content-Type'] = archivo.type || 'application/octet-stream';
    headers['X-Nombre-Archivo'] = encodeURIComponent(archivo.name);
  }

  const response = await fetch(`${API_BASE}${path}`, {
    method,
    headers,
    // Las cookies de sesión son HttpOnly: el navegador las envía solo.
    credentials: API_BASE ? 'include' : 'same-origin',
    body: archivo || (body !== undefined ? JSON.stringify(body) : undefined),
  });

  // Token de acceso vencido: se renueva una vez y se repite la petición.
  const rutaDeSesion = /\/auth\/(me|estado|actividad|login|registro|refresh|logout|2fa\/verificar|olvide-password)$/.test(path);
  if (response.status === 401 && reintentar && !rutaDeSesion) {
    if (await renovarSesion()) {
      return request(path, { method, body, archivo, comoBlob, reintentar: false });
    }
    window.dispatchEvent(new CustomEvent(EVENTO_SESION, { detail: { tipo: 'vencida', mensaje: ultimoMotivoVencimiento } }));
  }

  if (!response.ok) {
    let detail = `Error HTTP ${response.status}`;
    let accion = null;
    try {
      const data = await response.json();
      detail = data.detail || detail;
      accion = data.accion || null;
    } catch (_) {
      // Se conserva el código HTTP cuando la respuesta no es JSON.
    }
    if (accion === 'cambiar-password') {
      window.dispatchEvent(new CustomEvent(EVENTO_SESION, { detail: { tipo: 'cambiar-password' } }));
    }
    throw new ApiError(detail, response.status, accion);
  }

  return comoBlob ? response.blob() : response.json();
}

// ------------------------------------------------------------
// Autenticación
// ------------------------------------------------------------

export const auth = {
  me: () => request(`${API_PREFIX}/auth/me`),
  // Estado de la sesión sin contarlo como actividad, y aviso de actividad real.
  estado: () => request(`${API_PREFIX}/auth/estado`),
  actividad: () => request(`${API_PREFIX}/auth/actividad`, { method: 'POST' }),
  olvidePassword: (email) => request(`${API_PREFIX}/auth/olvide-password`, { method: 'POST', body: { email } }),
  renovar: renovarSesion,
  login: (email, password) => request(`${API_PREFIX}/auth/login`, { method: 'POST', body: { email, password } }),
  registro: (nombre, email, password, aceptaPolitica) => request(`${API_PREFIX}/auth/registro`, {
    method: 'POST',
    body: { nombre, email, password, acepta_politica: aceptaPolitica },
  }),
  verificar2fa: (desafio, codigo) => request(`${API_PREFIX}/auth/2fa/verificar`, { method: 'POST', body: { desafio, codigo } }),
  iniciar2fa: (password) => request(`${API_PREFIX}/auth/2fa/iniciar`, { method: 'POST', body: { password } }),
  activar2fa: (codigo) => request(`${API_PREFIX}/auth/2fa/activar`, { method: 'POST', body: { codigo } }),
  desactivar2fa: (password, codigo) => request(`${API_PREFIX}/auth/2fa/desactivar`, { method: 'POST', body: { password, codigo } }),
  regenerarCodigos: (password, codigo) => request(`${API_PREFIX}/auth/2fa/regenerar-codigos`, { method: 'POST', body: { password, codigo } }),
  aceptarPolitica: () => request(`${API_PREFIX}/auth/aceptar-politica`, { method: 'POST' }),
  misDatos: () => request(`${API_PREFIX}/auth/mis-datos`),
  eliminarCuenta: (password, codigo) => request(`${API_PREFIX}/auth/eliminar-cuenta`, {
    method: 'POST',
    body: { password, confirmacion: 'ELIMINAR', codigo: codigo || null },
  }),
  logout: () => request(`${API_PREFIX}/auth/logout`, { method: 'POST' }),
  cambiarPassword: (passwordActual, passwordNueva) => request(`${API_PREFIX}/auth/cambiar-password`, {
    method: 'POST',
    body: { password_actual: passwordActual, password_nueva: passwordNueva },
  }),
  solicitarInvestigador: (institucion, motivo, soporteId) => request(`${API_PREFIX}/auth/solicitar-investigador`, {
    method: 'POST',
    body: { institucion, motivo, soporte_id: soporteId || null },
  }),
  subirSoporte: (archivo) => request(`${API_PREFIX}/auth/solicitud/soporte`, { method: 'POST', archivo }),
  cambiarEmail: (emailNuevo, password, codigo) => request(`${API_PREFIX}/auth/cambiar-email`, {
    method: 'POST',
    body: { email_nuevo: emailNuevo, password, codigo: codigo || null },
  }),
  sesiones: () => request(`${API_PREFIX}/auth/sesiones`),
  cerrarSesionRemota: (id) => request(`${API_PREFIX}/auth/sesiones/${encodeURIComponent(id)}/cerrar`, { method: 'POST' }),
  cerrarOtrasSesiones: () => request(`${API_PREFIX}/auth/sesiones/cerrar-otras`, { method: 'POST' }),
};

// ------------------------------------------------------------
// Administración
// ------------------------------------------------------------

export const admin = {
  usuarios: (filtros = {}) => {
    const params = new URLSearchParams(Object.entries(filtros).filter(([, v]) => v));
    const query = params.toString() ? `?${params}` : '';
    return request(`${API_PREFIX}/admin/usuarios${query}`);
  },
  actualizar: (id, cambios) => request(`${API_PREFIX}/admin/usuarios/${encodeURIComponent(id)}`, { method: 'PATCH', body: cambios }),
  decidirSolicitud: (id, decision, comentario) => request(`${API_PREFIX}/admin/usuarios/${encodeURIComponent(id)}/solicitud`, {
    method: 'POST',
    body: { decision, comentario: comentario || null },
  }),
  restablecerPassword: (id) => request(`${API_PREFIX}/admin/usuarios/${encodeURIComponent(id)}/restablecer-password`, { method: 'POST' }),
  restablecer2fa: (id) => request(`${API_PREFIX}/admin/usuarios/${encodeURIComponent(id)}/restablecer-2fa`, { method: 'POST' }),
  establecerPassword: (id, password) => request(`${API_PREFIX}/admin/usuarios/${encodeURIComponent(id)}/establecer-password`, { method: 'POST', body: { password } }),
  descartarRecuperacion: (id) => request(`${API_PREFIX}/admin/usuarios/${encodeURIComponent(id)}/descartar-recuperacion`, { method: 'POST' }),
  permisos: () => request(`${API_PREFIX}/admin/permisos`),
  roles: () => request(`${API_PREFIX}/admin/roles`),
  crearRol: (datos) => request(`${API_PREFIX}/admin/roles`, { method: 'POST', body: datos }),
  actualizarRol: (clave, cambios) => request(`${API_PREFIX}/admin/roles/${encodeURIComponent(clave)}`, { method: 'PATCH', body: cambios }),
  eliminarRol: (clave) => request(`${API_PREFIX}/admin/roles/${encodeURIComponent(clave)}`, { method: 'DELETE' }),
  configuracion: () => request(`${API_PREFIX}/admin/configuracion/sesion`),
  guardarConfiguracion: (cambios) => request(`${API_PREFIX}/admin/configuracion/sesion`, { method: 'PATCH', body: cambios }),
  errores: () => request(`${API_PREFIX}/admin/errores?limite=100`),
  simularError: () => request(`${API_PREFIX}/admin/errores/simular`, { method: 'POST' }),
  descargarSoporte: (id) => request(`${API_PREFIX}/admin/usuarios/${encodeURIComponent(id)}/soporte`, { comoBlob: true }),
  auditoria: (soloFallidos = false) => request(`${API_PREFIX}/admin/auditoria?limite=200${soloFallidos ? '&solo_fallidos=true' : ''}`),
};

export function getEstadoParque() {
  return request(`${API_PREFIX}/estado-parque`);
}

export function getEstadisticas() {
  return request(`${API_PREFIX}/estadisticas`);
}

export function getFechas() {
  return request(`${API_PREFIX}/fechas`);
}

export function getResumen() {
  return request(`${API_PREFIX}/resumen`);
}

export function getAreas(fecha) {
  const query = fecha ? `?fecha=${encodeURIComponent(fecha)}` : '';
  return request(`${API_PREFIX}/areas${query}`);
}

export function getArea(fid, fecha) {
  // La fecha es necesaria para que el detalle coincida con la fecha elegida en el mapa.
  const query = fecha ? `?fecha=${encodeURIComponent(fecha)}` : '';
  return request(`${API_PREFIX}/areas/${encodeURIComponent(fid)}${query}`);
}

export function getHistorico(fid) {
  return request(`${API_PREFIX}/areas/${encodeURIComponent(fid)}/historico`);
}

export function getGeoJSON() {
  return request(`${API_PREFIX}/geojson`);
}

export function normalizeArea(raw, feature = null) {
  const fid = Number(raw.fid_area_coralina);
  const properties = feature?.properties || {};
  return {
    fid,
    name: properties.ETIQUETA ? `${properties.ETIQUETA} · FID ${fid}` : `Área coralina · FID ${fid}`,
    label: properties.ETIQUETA || 'Áreas coralinas',
    pixels: Number(raw.numero_pixeles || 0),
    dhwAvg: Number(raw.dhw_promedio || 0),
    dhwMax: Number(raw.dhw_max_asociado || 0),
    sstAvg: Number(raw.sst_promedio || 0),
    sstaAvg: Number(raw.ssta_promedio || 0),
    hotspotAvg: Number(raw.hotspot_promedio || 0),
    classification: raw.categoria_exposicion_relativa || 'Baja',
    fecha: raw.fecha || null,
    fechaInicial: raw.fecha_inicial || null,
    fechaFinal: raw.fecha_final || null,
    geometry: feature?.geometry || null,
  };
}

export function getClassificationStats(areas) {
  return CLASSIFICATIONS.reduce((acc, classification) => {
    acc[classification] = areas.filter((area) => area.classification === classification).length;
    return acc;
  }, { Baja: 0, Intermedia: 0, Alta: 0 });
}

export function formatDateTime(value) {
  if (!value) return '—';
  return value.replace('T', ' ').slice(0, 16);
}

export function formatDate(value) {
  if (!value) return '—';
  return value.slice(0, 10);
}
