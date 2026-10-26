const STEPS = [
  { icon: '🛰️', label: 'NOAA CRW', sub: 'Satélites polares', color: '#40e0d0',
    desc: 'Los satélites de la NOAA miden temperatura infrarroja del océano dos veces por día con resolución aproximada de 5 km × 5 km.' },
  { icon: '📡', label: 'Datos diarios', sub: 'SST · SSTA · HS · DHW', color: '#00c4b4',
    desc: 'Para cada fecha se generan rasters con los cuatro indicadores. Disponibles vía OPeNDAP y ERDDAP. Frecuencia: diaria.' },
  { icon: '🗺️', label: '20 Píxeles NOAA', sub: 'Selección espacial', color: '#7fffd4',
    desc: 'Se identificaron 20 píxeles cuyos centroides caen dentro de los límites del PNN Corales del Rosario y San Bernardo.' },
  { icon: '⚡', label: 'Cruce espacial', sub: 'GIS · Intersección', color: '#fbbf24',
    desc: 'Mediante análisis de intersección espacial, cada píxel NOAA se asocia a las áreas coralinas del parque que cubre.' },
  { icon: '🪸', label: '47 Áreas coralinas', sub: 'FIDs del PNN', color: '#f97316',
    desc: 'El PNN tiene 47 áreas coralinas delimitadas. Cada área recibe los valores promedio de los píxeles que la intersectan.' },
  { icon: '🗄️', label: 'Base de datos', sub: 'MongoDB', color: '#ff6b47',
    desc: 'Los valores diarios por área se almacenan en una base de datos documental que crece automáticamente con nuevas fechas.' },
  { icon: '⚙️', label: 'API REST', sub: '/fechas · /areas · /historico', color: '#a8d4e0',
    desc: 'Una API expone los datos por área, fecha y como series temporales. Los datos crecen cuando llegan nuevas observaciones.' },
  { icon: '🌊', label: 'Visualización', sub: 'Esta experiencia', color: '#00c4b4',
    desc: 'El frontend consume la API para generar el mapa interactivo, gráficos temporales y esta experiencia educativa.' },
];

export default function ViewMetodologia() {
  return (
    <div className="h-full overflow-y-auto px-8 py-8">
      <div className="max-w-5xl mx-auto">
        <div className="mb-6">
          <span className="text-xs tracking-widest uppercase font-medium mb-2 block"
            style={{ color: 'rgba(0,196,180,0.65)' }}>Transparencia científica</span>
          <h2 className="font-display text-4xl font-light mb-2" style={{ color: '#e8f4f8' }}>
            <span className="text-gradient-ocean italic">Metodología</span>
          </h2>
          <p className="text-sm max-w-xl" style={{ color: 'rgba(168,212,224,0.52)', lineHeight: 1.7 }}>
            Del satélite a la pantalla: cómo los datos de temperatura satelital se convierten en indicadores
            para cada área coralina del parque.
          </p>
        </div>

        {/* Flow steps */}
        <div className="grid grid-cols-1 md:grid-cols-2 gap-3 mb-5">
          {STEPS.map((step, i) => (
            <div key={i} className="glass rounded-xl p-4 flex gap-4 card-hover"
              style={{ border: `1px solid ${step.color}14` }}>
              <div className="flex flex-col items-center gap-1.5 shrink-0">
                <div className="text-xl">{step.icon}</div>
                <div className="w-5 h-5 rounded-full flex items-center justify-center text-xs font-mono font-bold"
                  style={{ background: `${step.color}18`, color: step.color, border: `1px solid ${step.color}25` }}>
                  {i + 1}
                </div>
              </div>
              <div>
                <div className="font-display text-sm font-semibold mb-0.5 leading-tight" style={{ color: step.color }}>
                  {step.label}
                  <span className="font-body font-normal text-xs ml-2" style={{ color: 'rgba(168,212,224,0.32)' }}>{step.sub}</span>
                </div>
                <p className="text-xs leading-relaxed" style={{ color: 'rgba(168,212,224,0.58)', lineHeight: 1.65 }}>{step.desc}</p>
              </div>
            </div>
          ))}
        </div>

        {/* Flow diagram horizontal */}
        <div className="glass rounded-xl p-5 mb-5">
          <div className="text-xs mb-3 font-medium" style={{ color: 'rgba(168,212,224,0.5)' }}>Flujo de datos</div>
          <div className="flex items-center gap-1 flex-wrap">
            {STEPS.map((s, i) => (
              <div key={i} className="flex items-center gap-1">
                <div className="px-2.5 py-1 rounded-full text-xs font-medium"
                  style={{ background: `${s.color}12`, color: s.color, border: `1px solid ${s.color}25` }}>
                  {s.label}
                </div>
                {i < STEPS.length - 1 && (
                  <svg className="w-4 h-4 shrink-0" fill="none" viewBox="0 0 24 24" stroke="rgba(0,196,180,0.25)">
                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9 5l7 7-7 7" />
                  </svg>
                )}
              </div>
            ))}
          </div>
        </div>

        {/* Classification note */}
        <div className="glass rounded-xl p-5 flex gap-3"
          style={{ border: '1px solid rgba(255,107,71,0.18)' }}>
          <svg className="w-5 h-5 shrink-0 mt-0.5" fill="none" viewBox="0 0 24 24" stroke="#ff6b47">
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 9v2m0 4h.01M21 12a9 9 0 11-18 0 9 9 0 0118 0z" />
          </svg>
          <p className="text-sm" style={{ color: 'rgba(168,212,224,0.68)', lineHeight: 1.75 }}>
            <strong style={{ color: 'rgba(168,212,224,0.9)' }}>Nota sobre la clasificación:</strong>{' '}
            La clasificación de exposición térmica <strong>(Baja / Intermedia / Alta)</strong> utilizada en esta aplicación
            es <strong>relativa al conjunto de áreas analizadas</strong> y no corresponde a categorías oficiales de
            alerta NOAA Coral Reef Watch ni a ningún estándar internacional de monitoreo coralino.
          </p>
        </div>
      </div>
    </div>
  );
}
