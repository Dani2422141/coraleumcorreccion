export const CLASSIFICATION_COLORS = {
  Baja: '#4ade80',
  Intermedia: '#fbbf24',
  Alta: '#ff6b47',
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

/** Renueva la sesión con el refresh token (cookie HttpOnly). Una sola a la vez. */
function renovarSesion() {
  if (!renovacionEnCurso) {
    renovacionEnCurso = fetch(`${API_BASE}${API_PREFIX}/auth/refresh`, {
      method: 'POST',
      credentials: API_BASE ? 'include' : 'same-origin',
      headers: { Accept: 'application/json', 'X-Requested-With': 'Coraleum' },
    })
      .then((r) => r.ok)
      .catch(() => false)
      .finally(() => { renovacionEnCurso = null; });
  }
  return renovacionEnCurso;
}

async function request(path, { method = 'GET', body, reintentar = true } = {}) {
  const headers = { Accept: 'application/json' };
  if (method !== 'GET') {
    // Encabezado exigido por el backend en peticiones que modifican datos (CSRF).
    headers['X-Requested-With'] = 'Coraleum';
  }
  if (body !== undefined) headers['Content-Type'] = 'application/json';

  const response = await fetch(`${API_BASE}${path}`, {
    method,
    headers,
    // Las cookies de sesión son HttpOnly: el navegador las envía solo.
    credentials: API_BASE ? 'include' : 'same-origin',
    body: body !== undefined ? JSON.stringify(body) : undefined,
  });

  // Token de acceso vencido: se renueva una vez y se repite la petición.
  if (response.status === 401 && reintentar && !path.includes('/auth/')) {
    if (await renovarSesion()) {
      return request(path, { method, body, reintentar: false });
    }
    window.dispatchEvent(new CustomEvent(EVENTO_SESION, { detail: { tipo: 'vencida' } }));
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

  return response.json();
}

// ------------------------------------------------------------
// Autenticación
// ------------------------------------------------------------

export const auth = {
  me: () => request(`${API_PREFIX}/auth/me`),
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
  solicitarInvestigador: (institucion, motivo) => request(`${API_PREFIX}/auth/solicitar-investigador`, {
    method: 'POST',
    body: { institucion, motivo },
  }),
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
  auditoria: (soloFallidos = false) => request(`${API_PREFIX}/admin/auditoria?limite=200${soloFallidos ? '&solo_fallidos=true' : ''}`),
};

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
