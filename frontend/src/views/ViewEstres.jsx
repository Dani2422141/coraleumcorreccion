import { useState } from 'react';

const STAGES = [
  { label: 'Condiciones normales', temp: '28°C', tempColor: '#40e0d0', coralColor: '#ff6b47',
    description: 'El arrecife en equilibrio: agua a 28°C, zooxantelas fotosintéticas activas. Las algas simbióticas producen el 90% de la energía del coral.' },
  { label: 'Aumento de temperatura', temp: '30°C', tempColor: '#fbbf24', coralColor: '#ffaa44',
    description: 'La temperatura sube 1–2°C sobre el promedio histórico durante semanas. El pólipo empieza a estresarse y las zooxantelas producen radicales libres.' },
  { label: 'Estrés térmico', temp: '31°C', tempColor: '#f97316', coralColor: '#ffddaa',
    description: 'Con DHW > 4°C-semanas el coral expulsa activamente a sus algas simbióticas. Es un mecanismo de defensa, pero queda sin su fuente principal de energía.' },
  { label: 'Blanqueamiento', temp: '32°C+', tempColor: '#ff6b47', coralColor: '#e8e8e8',
    description: 'Sin zooxantelas, el tejido se vuelve transparente revelando el esqueleto blanco. Si el estrés persiste el coral muere; si bajan las temperaturas a tiempo, puede recuperarse.' },
];

function CoralPolyp({ color, pulseColor }) {
  return (
    <div className="relative flex items-center justify-center w-36 h-36">
      <div className="absolute inset-0 rounded-full animate-ping opacity-10" style={{ background: pulseColor }} />
      <svg viewBox="0 0 100 100" className="w-28 h-28 relative z-10">
        <ellipse cx="50" cy="76" rx="28" ry="12" fill={color} opacity="0.4" />
        <ellipse cx="50" cy="56" rx="16" ry="22" fill={color} opacity="0.78" />
        {Array.from({ length: 8 }, (_, i) => {
          const a = (i / 8) * Math.PI * 2;
          return <line key={i} x1="50" y1="34" x2={50 + Math.cos(a) * 21} y2={34 + Math.sin(a) * 11}
            stroke={color} strokeWidth="2.5" strokeLinecap="round" opacity="0.65" />;
        })}
        <circle cx="50" cy="34" r="5" fill={color} opacity="0.9" />
        {color !== '#e8e8e8' && [41, 44, 47, 50, 53, 56].map((x, i) => (
          <circle key={i} cx={x} cy={52 + (i % 2) * 4} r="2"
            fill="#40e0d0" opacity={color === '#ffddaa' ? 0.25 : 0.65} />
        ))}
      </svg>
    </div>
  );
}

export default function ViewEstres() {
  const [active, setActive] = useState(0);
  const stage = STAGES[active];

  return (
    <div className="h-full overflow-y-auto px-8 py-8">
      <div className="max-w-5xl mx-auto">
        <div className="mb-6">
          <span className="text-xs tracking-widest uppercase font-medium mb-2 block"
            style={{ color: 'rgba(249,115,22,0.75)' }}>Ciencia del cambio climático</span>
          <h2 className="font-display text-4xl font-light mb-2" style={{ color: '#e8f4f8' }}>
            El <span className="italic" style={{ color: '#f97316' }}>Estrés Térmico</span> en el arrecife
          </h2>
          <p className="text-sm max-w-xl" style={{ color: 'rgba(168,212,224,0.55)', lineHeight: 1.7 }}>
            Selecciona cada etapa para ver cómo el aumento de temperatura transforma un arrecife vivo en un cementerio de esqueletos blancos.
          </p>
        </div>

        <div className="flex gap-5">
          {/* Stage buttons */}
          <div className="flex flex-col gap-2 shrink-0">
            {STAGES.map((s, i) => (
              <button
                key={i}
                onClick={() => setActive(i)}
                className="flex items-center gap-3 px-4 py-3 rounded-xl text-left transition-all duration-200"
                style={{
                  background: active === i ? `${s.tempColor}12` : 'rgba(4,22,40,0.55)',
                  border: `1px solid ${active === i ? s.tempColor + '40' : 'rgba(0,196,180,0.08)'}`,
                  minWidth: '175px',
                }}
              >
                <div className="w-2.5 h-2.5 rounded-full shrink-0"
                  style={{ background: s.tempColor, opacity: active === i ? 1 : 0.35 }} />
                <div>
                  <div className="text-xs font-medium leading-tight"
                    style={{ color: active === i ? s.tempColor : 'rgba(168,212,224,0.5)' }}>{s.label}</div>
                  <div className="font-mono text-xs mt-0.5"
                    style={{ color: active === i ? s.tempColor : 'rgba(168,212,224,0.28)' }}>{s.temp}</div>
                </div>
              </button>
            ))}
          </div>

          {/* Main stage panel */}
          <div className="flex-1 glass rounded-2xl p-6 flex flex-col md:flex-row items-center gap-6"
            style={{ border: `1px solid ${stage.tempColor}20` }}>
            <CoralPolyp color={stage.coralColor} pulseColor={stage.tempColor} />
            <div>
              <div className="font-mono text-5xl font-bold mb-1" style={{ color: stage.tempColor }}>
                {stage.temp}
              </div>
              <h3 className="font-display text-xl font-semibold mb-3" style={{ color: '#e8f4f8' }}>{stage.label}</h3>
              <p className="text-sm leading-relaxed" style={{ color: 'rgba(168,212,224,0.8)', lineHeight: 1.8 }}>
                {stage.description}
              </p>
              {/* Progress */}
              <div className="mt-5 flex gap-1">
                {STAGES.map((_, i) => (
                  <div key={i} className="flex-1 h-1 rounded-full transition-all duration-300"
                    style={{ background: i <= active ? stage.tempColor : 'rgba(0,196,180,0.1)' }} />
                ))}
              </div>
              <div className="flex justify-between text-xs mt-1 font-mono" style={{ color: 'rgba(168,212,224,0.3)' }}>
                <span>Normal</span><span>Blanqueamiento</span>
              </div>
            </div>
          </div>
        </div>

        {/* DHW scale */}
        <div className="glass rounded-xl p-4 mt-5">
          <div className="text-xs mb-2 font-medium" style={{ color: 'rgba(168,212,224,0.5)' }}>
            Escala DHW — Degree Heating Weeks
          </div>
          <div className="flex rounded-md overflow-hidden h-2 mb-1.5">
            {['#40e0d0','#7fffd4','#fbbf24','#f97316','#ff6b47','#dc2626'].map((c, i) => (
              <div key={i} className="flex-1" style={{ background: c }} />
            ))}
          </div>
          <div className="flex justify-between text-xs font-mono" style={{ color: 'rgba(168,212,224,0.3)' }}>
            <span>0</span><span>2</span><span>4</span><span>6</span><span>8</span><span>12+ °C-sem</span>
          </div>
          <div className="flex justify-between text-xs mt-1" style={{ color: 'rgba(168,212,224,0.25)' }}>
            <span>Sin estrés</span><span>Blanqueamiento posible</span><span>Mortalidad masiva</span>
          </div>
        </div>
      </div>
    </div>
  );
}
