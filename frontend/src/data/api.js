export const CLASSIFICATION_COLORS = {
  Baja: '#4ade80',
  Intermedia: '#fbbf24',
  Alta: '#ff6b47',
};

export const CLASSIFICATIONS = ['Baja', 'Intermedia', 'Alta'];

const API_BASE = (import.meta.env.VITE_API_URL || '').replace(/\/$/, '');
const API_PREFIX = API_BASE ? '' : '/api';

async function request(path, options = {}) {
  const response = await fetch(`${API_BASE}${path}`, {
    headers: { Accept: 'application/json' },
    ...options,
  });

  if (!response.ok) {
    let detail = `Error HTTP ${response.status}`;
    try {
      const body = await response.json();
      detail = body.detail || detail;
    } catch (_) {
      // Keep the HTTP status when the response is not JSON.
    }
    throw new Error(detail);
  }

  return response.json();
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
