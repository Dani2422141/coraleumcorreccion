// Iconos propios del recorrido educativo (trazo, 24×24).
const TRAZOS = {
  ojo: <><path d="M2.5 12s3.5-6.5 9.5-6.5S21.5 12 21.5 12s-3.5 6.5-9.5 6.5S2.5 12 2.5 12Z" /><circle cx="12" cy="12" r="3" /></>,
  coral: <><path d="M12 21v-7m0 0-4-4V6m4 8 4-4V5m-8 5L5 8m11 2 3-2M8 6 7 3m9 2 1-2" /><path d="M7 21h10" /></>,
  estrella: <path d="m12 3 2.6 5.6 6.1.7-4.5 4.2 1.2 6L12 16.6 6.6 19.5l1.2-6-4.5-4.2 6.1-.7L12 3Z" />,
  termometro: <><path d="M14 14.8V5a2 2 0 1 0-4 0v9.8a4 4 0 1 0 4 0Z" /><path d="M12 9v7" /></>,
  escudo: <><path d="M12 3 5 6v5c0 4.5 3 8.3 7 10 4-1.7 7-5.5 7-10V6l-7-3Z" /><path d="m9 12 2 2 4-4" /></>,
  ancla: <><circle cx="12" cy="5" r="2" /><path d="M12 7v14m-7-7a7 7 0 0 0 14 0M8 11h8" /></>,
  mano: <><path d="M8 13V5.5a1.5 1.5 0 0 1 3 0V12m0-1V4.5a1.5 1.5 0 0 1 3 0V12m0-6.5a1.5 1.5 0 0 1 3 0V14a7 7 0 0 1-7 7h-.5A6.5 6.5 0 0 1 4 17l-1.6-3.2a1.4 1.4 0 0 1 2.4-1.4L8 16" /></>,
  sol: <><circle cx="12" cy="12" r="4" /><path d="M12 2v2m0 16v2M4.9 4.9l1.4 1.4m11.4 11.4 1.4 1.4M2 12h2m16 0h2M4.9 19.1l1.4-1.4M17.7 6.3l1.4-1.4" /></>,
  bolsa: <><path d="M6 8h12l-1 13H7L6 8Z" /><path d="M9 8V6a3 3 0 0 1 6 0v2" /><path d="m4 4 16 16" /></>,
  pez: <><path d="M3 12c3-4 7-5 11-3l4-3v12l-4-3c-4 2-8 1-11-3Z" /><circle cx="8" cy="11" r=".8" fill="currentColor" /></>,
  foco: <><path d="M9 18h6m-5 3h4M12 3a6 6 0 0 0-3.5 10.9c.6.5 1 1.2 1 2V17h5v-1.1c0-.8.4-1.5 1-2A6 6 0 0 0 12 3Z" /></>,
  camara: <><path d="M4 8h3l2-3h6l2 3h3v11H4V8Z" /><circle cx="12" cy="13" r="3.5" /></>,
  compartir: <><circle cx="18" cy="5" r="2.5" /><circle cx="6" cy="12" r="2.5" /><circle cx="18" cy="19" r="2.5" /><path d="m8.2 10.8 7.6-4.4m-7.6 6.8 7.6 4.4" /></>,
  descargar: <><path d="M12 4v11m0 0-4-4m4 4 4-4M5 20h14" /></>,
  bus: <><rect x="5" y="3" width="14" height="15" rx="3" /><path d="M5 11h14M8 21v-3m8 3v-3" /><circle cx="8.5" cy="14.5" r=".8" fill="currentColor" /><circle cx="15.5" cy="14.5" r=".8" fill="currentColor" /></>,
};

export default function Icono({ nombre, size = 20, className = '' }) {
  return (
    <svg className={className} width={size} height={size} viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.6" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true">
      {TRAZOS[nombre]}
    </svg>
  );
}

/** Silueta de una colonia de coral ramificado; el color indica su estado. */
export function GlifoCoral({ color, size = 28 }) {
  return (
    <svg width={size} height={size} viewBox="0 0 32 32" aria-hidden="true">
      <path
        d="M16 30V19m0 0-5-5V8m5 11 5-6V6m-10 8-4-3V6m14 7 4-3V5M11 8 9.5 4M21 6l1.5-3.5M16 19V11"
        fill="none" stroke={color} strokeWidth="2.6" strokeLinecap="round" strokeLinejoin="round"
      />
      <path d="M10 30h12" stroke={color} strokeWidth="2.6" strokeLinecap="round" opacity=".55" />
    </svg>
  );
}
