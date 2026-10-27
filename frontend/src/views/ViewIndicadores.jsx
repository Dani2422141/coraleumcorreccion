const INDICATORS = [
  {
    code: 'SST', name: 'Sea Surface Temperature', unit: '°C', typical: '26 – 30 °C',
    color: '#0e8f88', role: 'Línea base térmica del ecosistema coralino.',
    description: 'Medición directa de la temperatura del agua en la superficie oceánica. NOAA la obtiene mediante satélites de órbita polar que miden la radiación infrarroja emitida por el mar con resolución aproximada de 5 km.',
    icon: (
      <svg viewBox="0 0 56 56" className="w-full h-full" fill="none">
        <circle cx="28" cy="28" r="18" stroke="#0e8f88" strokeWidth="1.2" opacity="0.2" />
        <circle cx="28" cy="28" r="11" stroke="#0e8f88" strokeWidth="1" opacity="0.4" />
        {[0,90,180,270].map((deg, i) => {
          const r = Math.PI * deg / 180;
          return <line key={i} x1={28+Math.cos(r)*13} y1={28+Math.sin(r)*13} x2={28+Math.cos(r)*18} y2={28+Math.sin(r)*18}
            stroke="#0e8f88" strokeWidth="1.8" strokeLinecap="round" />;
        })}
        <circle cx="28" cy="28" r="5" fill="#0e8f88" opacity="0.8" />
      </svg>
    ),
  },
  {
    code: 'SSTA', name: 'Sea Surface Temperature Anomaly', unit: '°C sobre normal', typical: '-1 a +2 °C',
    color: '#b7791f', role: 'Primer indicador de estrés potencial cuando supera +1°C.',
    description: 'Diferencia entre la SST observada y la climatología histórica para esa fecha y ubicación. Un valor positivo indica temperatura superior a lo normal.',
    icon: (
      <svg viewBox="0 0 56 56" className="w-full h-full" fill="none">
        <path d="M6 33 L16 23 L24 30 L34 16 L42 24 L50 18" stroke="#b7791f" strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round" />
        <line x1="6" y1="33" x2="50" y2="33" stroke="#b7791f" strokeWidth="1" strokeDasharray="3,3" opacity="0.3" />
        <circle cx="42" cy="24" r="3" fill="#b7791f" opacity="0.8" />
      </svg>
    ),
  },
  {
    code: 'HotSpot', name: 'Indicador de Exceso Térmico', unit: '°C sobre umbral', typical: '0 – 2 °C',
    color: '#d0611c', role: 'Activa el riesgo de blanqueamiento cuando supera 0°C.',
    description: 'Calculado como SSTA cuando este supera 1°C. Cuando HotSpot > 0, existe riesgo activo de blanqueamiento. Se acumula semana a semana para generar el DHW.',
    icon: (
      <svg viewBox="0 0 56 56" className="w-full h-full" fill="none">
        <circle cx="28" cy="20" r="9" stroke="#d0611c" strokeWidth="1.2" opacity="0.35" />
        <circle cx="28" cy="20" r="5.5" fill="#d0611c" opacity="0.6" />
        <path d="M24 29 L22 45 Q28 49 34 45 L32 29" fill="#d0611c" opacity="0.4" />
        <path d="M25 12 L28 6 L31 12" stroke="#d0611c" strokeWidth="1.5" fill="none" strokeLinecap="round" opacity="0.55" />
      </svg>
    ),
  },
  {
    code: 'DHW', name: 'Degree Heating Weeks', unit: '°C-semanas', typical: '0 – 12 °C-sem',
    color: '#c8452c', role: 'Indicador principal de riesgo de blanqueamiento y mortalidad.',
    description: 'Acumulación de HotSpots durante las últimas 12 semanas. DHW > 4 indica blanqueamiento severo probable. DHW > 8 indica mortalidad masiva probable.',
    icon: (
      <svg viewBox="0 0 56 56" className="w-full h-full" fill="none">
        {Array.from({ length: 12 }, (_, i) => {
          const a = (i / 12) * Math.PI * 2 - Math.PI / 2;
          const r = i < 8 ? 19 : 13;
          return <circle key={i} cx={28+Math.cos(a)*r} cy={28+Math.sin(a)*r} r={i < 8 ? 2.5 : 1.5}
            fill="#c8452c" opacity={0.15 + (i/11)*0.75} />;
        })}
        <text x="21" y="32" fontSize="11" fontWeight="bold" fill="#c8452c" opacity="0.85" fontFamily="JetBrains Mono">DHW</text>
      </svg>
    ),
  },
];

export default function ViewIndicadores() {
  return (
    <div className="h-full overflow-y-auto px-8 py-8">
      <div className="max-w-5xl mx-auto">
        <div className="mb-6">
          <span className="text-xs tracking-widest uppercase font-medium mb-2 block"
            style={{ color: 'var(--c-acento)' }}>NOAA Coral Reef Watch</span>
          <h2 className="font-display text-4xl font-light mb-2" style={{ color: 'var(--c-texto)' }}>
            Indicadores <span className="text-gradient-ocean italic">Científicos</span>
          </h2>
          <p className="text-sm max-w-xl" style={{ color: 'var(--c-texto-2)', lineHeight: 1.7 }}>
            Cuatro métricas satelitales con resolución ~5 km que permiten monitorear el riesgo de blanqueamiento en tiempo casi real.
          </p>
        </div>

        <div className="grid grid-cols-1 md:grid-cols-2 gap-4 mb-4">
          {INDICATORS.map((ind) => (
            <div key={ind.code} className="glass rounded-2xl p-5 card-hover flex gap-4"
              style={{ border: `1px solid ${ind.color}18` }}>
              <div className="w-12 h-12 shrink-0">{ind.icon}</div>
              <div className="flex-1 min-w-0">
                <div className="font-mono text-lg font-bold mb-0.5" style={{ color: ind.color }}>{ind.code}</div>
                <div className="font-display text-sm font-semibold mb-1.5 leading-snug" style={{ color: 'var(--c-texto)', opacity: 0.9 }}>
                  {ind.name}
                </div>
                <p className="text-xs leading-relaxed mb-2" style={{ color: 'var(--c-texto-2)', lineHeight: 1.7 }}>
                  {ind.description}
                </p>
                <div className="flex flex-wrap gap-3 pt-2.5" style={{ borderTop: `1px solid ${ind.color}12` }}>
                  <div className="text-xs">
                    <span style={{ color: 'var(--c-texto-3)' }}>Unidad · </span>
                    <span className="font-mono" style={{ color: ind.color }}>{ind.unit}</span>
                  </div>
                  <div className="text-xs">
                    <span style={{ color: 'var(--c-texto-3)' }}>Rango · </span>
                    <span className="font-mono" style={{ color: ind.color, opacity: 0.7 }}>{ind.typical}</span>
                  </div>
                </div>
                <p className="text-xs mt-1.5 italic" style={{ color: 'var(--c-texto-3)' }}>{ind.role}</p>
              </div>
            </div>
          ))}
        </div>

        <div className="glass rounded-xl p-4 flex gap-3">
          <svg className="w-4 h-4 shrink-0 mt-0.5" fill="none" viewBox="0 0 24 24" stroke="#0b8f87">
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M13 16h-1v-4h-1m1-4h.01M21 12a9 9 0 11-18 0 9 9 0 0118 0z" />
          </svg>
          <p className="text-xs" style={{ color: 'var(--c-texto-3)', lineHeight: 1.7 }}>
            Fuente: <strong style={{ color: 'var(--c-texto)' }}>NOAA Coral Reef Watch</strong>.
            La clasificación Baja / Intermedia / Alta es{' '}
            <strong style={{ color: 'var(--c-texto)' }}>relativa entre las áreas de este proyecto</strong> y no corresponde a categorías oficiales de alerta NOAA.
          </p>
        </div>
      </div>
    </div>
  );
}
