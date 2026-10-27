// Insignias del recorrido educativo. Se guardan solo en este navegador
// (localStorage): no son datos personales ni viajan al servidor.
export const INSIGNIAS = [
  { id: 'parque', nombre: 'Observador del parque', como: 'Mira el estado del parque hoy en Inicio.', vista: 'inicio', icono: 'ojo' },
  { id: 'fichas', nombre: 'Conocedor de especies', como: 'Abre las cinco fichas de los corales del parque.', vista: 'corales', icono: 'coral' },
  { id: 'quiz', nombre: 'Memoria de arrecife', como: 'Responde todo el desafío de Conoce los Corales.', vista: 'corales', icono: 'estrella' },
  { id: 'simulador', nombre: 'Científico del calor', como: 'Lleva el simulador hasta una alerta de nivel 2 o más.', vista: 'estres', icono: 'termometro' },
  { id: 'compromiso', nombre: 'Guardián del arrecife', como: 'Elige al menos tres compromisos en Cuida el arrecife.', vista: 'actua', icono: 'escudo' },
];

const CLAVE = 'coraleum-insignias-v1';
let memoria = null;
export const EVENTO_PROGRESO = 'coraleum:progreso';

export function leerProgreso() {
  try {
    const valor = JSON.parse(localStorage.getItem(CLAVE) || '{}');
    return valor && typeof valor === 'object' ? valor : {};
  } catch (_) {
    return {};
  }
}

/** Marca una insignia como ganada (una sola vez) y avisa a la interfaz. */
export function ganarInsignia(id) {
  const actual = leerProgreso();
  if (actual[id]) return false;
  const nuevo = { ...actual, [id]: new Date().toISOString() };
  try { localStorage.setItem(CLAVE, JSON.stringify(nuevo)); } catch (_) { /* sin almacenamiento: dura la visita */ }
  memoria = nuevo;
  window.dispatchEvent(new CustomEvent(EVENTO_PROGRESO, { detail: { id, progreso: nuevo } }));
  return true;
}

export function progresoActual() {
  const guardado = leerProgreso();
  return Object.keys(guardado).length ? guardado : (memoria || {});
}

export function reiniciarProgreso() {
  try { localStorage.removeItem(CLAVE); } catch (_) { /* nada */ }
  memoria = {};
  window.dispatchEvent(new CustomEvent(EVENTO_PROGRESO, { detail: { progreso: {} } }));
}
