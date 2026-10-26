import { useEffect, useRef, useState } from 'react';
import { CLASSIFICATIONS, CLASSIFICATION_COLORS, getResumen } from '../data/api';
import { ErrorState, LoadingState } from '../components/LoadingState';

function AnimCount({ target }) {
  const [value, setValue] = useState(0);
  const ref = useRef(null);
  useEffect(() => {
    const node = ref.current;
    if (!node) return undefined;
    let frame;
    let start = null;
    const observer = new IntersectionObserver(([entry]) => {
      if (!entry.isIntersecting) return;
      const tick = (timestamp) => {
        if (start === null) start = timestamp;
        const progress = Math.min((timestamp - start) / 700, 1);
        setValue(Math.round((1 - Math.pow(1 - progress, 3)) * target));
        if (progress < 1) frame = requestAnimationFrame(tick);
      };
      frame = requestAnimationFrame(tick);
      observer.disconnect();
    }, { threshold: 0.2 });
    observer.observe(node);
    return () => { observer.disconnect(); if (frame) cancelAnimationFrame(frame); };
  }, [target]);
  return <div ref={ref}>{value}</div>;
}

export default function ViewResumen({ areas, totalDates }) {
  const [summary, setSummary] = useState(null);
  const [error, setError] = useState('');

  useEffect(() => {
    let cancelled = false;
    getResumen().then((data) => { if (!cancelled) setSummary(data); }).catch((err) => { if (!cancelled) setError(err.message || 'No fue posible obtener el resumen.'); });
    return () => { cancelled = true; };
  }, [areas.length, totalDates]);

  if (!summary && !error) return <LoadingState message="Calculando resumen desde MongoDB..." />;
  if (error) return <div className="h-full flex items-center justify-center"><ErrorState message={error} /></div>;

  const total = summary.total_areas || areas.length || 1;
  const stats = summary.clasificacion || { Baja: 0, Intermedia: 0, Alta: 0 };
  const averages = summary.promedios || {};
  const cards = [
    { icon: '🪸', value: summary.total_areas, label: 'Áreas coralinas', color: '#00c4b4' },
    { icon: '🛰️', value: summary.total_pixeles, label: 'Píxeles NOAA', color: '#40e0d0' },
    { icon: '📅', value: summary.total_fechas, label: 'Fechas disponibles', color: '#7fffd4' },
    { icon: '🌡️', value: summary.dhw_max, label: 'DHW máx registrado', color: '#ff6b47', unit: '°C-sem' },
  ];

  return (
    <div className="h-full overflow-y-auto px-8 py-8">
      <div className="max-w-5xl mx-auto">
        <div className="mb-6"><span className="text-xs tracking-widest uppercase font-medium mb-2 block" style={{ color: 'rgba(0,196,180,0.65)' }}>Visión general</span><h2 className="font-display text-4xl font-light mb-1" style={{ color: '#e8f4f8' }}>Resumen del <span className="text-gradient-ocean italic">Territorio</span></h2><p className="text-xs font-mono" style={{ color: 'rgba(168,212,224,0.35)' }}>Última fecha: {summary.fecha_final || '—'}</p></div>

        <div className="grid grid-cols-2 md:grid-cols-4 gap-4 mb-6">
          {cards.map(({ icon, value, label, color, unit }) => <div key={label} className="glass rounded-2xl p-5 text-center card-hover"><div className="text-2xl mb-2">{icon}</div><div className="font-display text-3xl font-light mb-0.5" style={{ color }}><AnimCount target={Math.round(Number(value) || 0)} /></div>{unit && <div className="font-mono text-xs mb-0.5" style={{ color: `${color}60` }}>{unit}</div>}<div className="text-xs" style={{ color: 'rgba(168,212,224,0.42)' }}>{label}</div></div>)}
        </div>

        <div className="grid grid-cols-1 md:grid-cols-2 gap-5 mb-5">
          <div className="glass rounded-2xl p-5"><h3 className="font-display text-base font-semibold mb-4" style={{ color: '#e8f4f8' }}>Distribución por clasificación relativa</h3><div className="space-y-3">{CLASSIFICATIONS.map((classification) => { const count = stats[classification] || 0; const pct = Math.round((count / total) * 100); return <div key={classification}><div className="flex justify-between items-center mb-1.5"><div className="flex items-center gap-2"><div className="w-3 h-3 rounded-full" style={{ background: CLASSIFICATION_COLORS[classification] }} /><span className="text-sm" style={{ color: '#e8f4f8' }}>{classification}</span></div><div className="flex gap-2 items-baseline"><span className="font-mono font-bold" style={{ color: CLASSIFICATION_COLORS[classification] }}>{count}</span><span className="font-mono text-xs" style={{ color: 'rgba(168,212,224,0.32)' }}>{pct}%</span></div></div><div className="h-2 rounded-full" style={{ background: 'rgba(2,12,22,0.6)' }}><div className="h-full rounded-full" style={{ width: `${pct}%`, background: CLASSIFICATION_COLORS[classification] }} /></div></div>; })}</div><div className="flex rounded-lg overflow-hidden mt-4" style={{ height: '7px' }}>{CLASSIFICATIONS.map((classification) => <div key={classification} style={{ width: `${((stats[classification] || 0) / total) * 100}%`, background: CLASSIFICATION_COLORS[classification] }} />)}</div></div>

          <div className="glass rounded-2xl p-5"><h3 className="font-display text-base font-semibold mb-4" style={{ color: '#e8f4f8' }}>Indicadores térmicos promedio</h3><div className="space-y-2.5">{[
            { label: 'SST Promedio territorial', value: averages.sst, unit: '°C', color: '#40e0d0' },
            { label: 'SSTA Promedio territorial', value: averages.ssta, unit: '°C', color: '#fbbf24' },
            { label: 'HotSpot Promedio territorial', value: averages.hotspot, unit: '°C', color: '#f97316' },
            { label: 'DHW Promedio territorial', value: averages.dhw, unit: '°C-sem', color: '#ff6b47' },
          ].map(({ label, value, unit, color }) => <div key={label} className="flex items-center justify-between p-3 rounded-xl" style={{ background: 'rgba(2,12,22,0.5)', border: '1px solid rgba(0,196,180,0.06)' }}><span className="text-xs" style={{ color: 'rgba(168,212,224,0.72)' }}>{label}</span><span className="font-mono font-bold text-base" style={{ color }}>{Number(value || 0).toFixed(2)}<span className="text-xs ml-1 font-normal opacity-50">{unit}</span></span></div>)}</div></div>
        </div>

        <div className="glass rounded-xl p-4"><div className="grid grid-cols-1 md:grid-cols-3 gap-4 text-xs"><div><div style={{ color: 'rgba(168,212,224,0.35)' }}>Periodo</div><div className="font-mono mt-1" style={{ color: '#e8f4f8' }}>{summary.fecha_inicial || '—'} → {summary.fecha_final || '—'}</div></div><div><div style={{ color: 'rgba(168,212,224,0.35)' }}>Áreas con datos en la última fecha</div><div className="font-mono mt-1" style={{ color: '#00c4b4' }}>{summary.areas_con_datos} / {summary.total_areas}</div></div><div><div style={{ color: 'rgba(168,212,224,0.35)' }}>Fechas cargadas en MongoDB</div><div className="font-mono mt-1" style={{ color: '#40e0d0' }}>{summary.total_fechas}</div></div></div></div>
      </div>
    </div>
  );
}
