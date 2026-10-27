// Escala de alertas de blanqueamiento de NOAA Coral Reef Watch (dic. 2023).
// Los colores siguen la progresión del mapa oficial: azul → amarillo → rojo → vino.
export const NIVELES = [
  { clave: 'sin_estres', nombre: 'Sin estrés', corto: 'Sin estrés', color: '#8fd3e8', desde: null,
    efecto: 'El agua está dentro de lo normal para el arrecife.' },
  { clave: 'vigilancia', nombre: 'Vigilancia', corto: 'Vigilancia', color: '#f1e38a', desde: null,
    efecto: 'El agua empieza a estar más caliente que el verano normal.' },
  { clave: 'advertencia', nombre: 'Advertencia', corto: 'Advertencia', color: '#f5b452', desde: 0,
    efecto: 'El calor se acumula: el blanqueamiento es posible.' },
  { clave: 'alerta_1', nombre: 'Alerta nivel 1', corto: 'Alerta 1', color: '#ef7f45', desde: 4,
    efecto: 'Blanqueamiento significativo probable.' },
  { clave: 'alerta_2', nombre: 'Alerta nivel 2', corto: 'Alerta 2', color: '#e0473f', desde: 8,
    efecto: 'Blanqueamiento severo y muerte de corales sensibles.' },
  { clave: 'alerta_3', nombre: 'Alerta nivel 3', corto: 'Alerta 3', color: '#b8263f', desde: 12,
    efecto: 'Riesgo de muerte de muchas especies de coral.' },
  { clave: 'alerta_4', nombre: 'Alerta nivel 4', corto: 'Alerta 4', color: '#8c1d4a', desde: 16,
    efecto: 'Riesgo de muerte severa: más de la mitad de los corales.' },
  { clave: 'alerta_5', nombre: 'Alerta nivel 5', corto: 'Alerta 5', color: '#5e1846', desde: 20,
    efecto: 'Riesgo de muerte casi total: más del 80 % de los corales.' },
];

export const NIVEL_POR_CLAVE = Object.fromEntries(NIVELES.map((n) => [n.clave, n]));

/** Mismo criterio que el backend (api/rutas_datos.py → nivel_noaa). */
export function nivelNoaa(hotspot, dhw) {
  if (dhw >= 20) return NIVEL_POR_CLAVE.alerta_5;
  if (dhw >= 16) return NIVEL_POR_CLAVE.alerta_4;
  if (dhw >= 12) return NIVEL_POR_CLAVE.alerta_3;
  if (dhw >= 8) return NIVEL_POR_CLAVE.alerta_2;
  if (dhw >= 4) return NIVEL_POR_CLAVE.alerta_1;
  if (hotspot >= 1) return NIVEL_POR_CLAVE.advertencia;
  if (hotspot > 0) return NIVEL_POR_CLAVE.vigilancia;
  return NIVEL_POR_CLAVE.sin_estres;
}

const MESES = ['enero', 'febrero', 'marzo', 'abril', 'mayo', 'junio', 'julio', 'agosto', 'septiembre', 'octubre', 'noviembre', 'diciembre'];

/** "2026-09-29 17:00:00" → "29 de septiembre de 2026" */
export function fechaLarga(texto) {
  if (!texto) return '';
  const [a, m, d] = texto.slice(0, 10).split('-').map(Number);
  return `${d} de ${MESES[m - 1]} de ${a}`;
}

export function fechaCorta(texto) {
  if (!texto) return '';
  const [, m, d] = texto.slice(0, 10).split('-').map(Number);
  return `${d} ${MESES[m - 1].slice(0, 3)}`;
}

export const numero = (v, dec = 1) => Number(v || 0).toLocaleString('es-CO', { minimumFractionDigits: dec, maximumFractionDigits: dec });
