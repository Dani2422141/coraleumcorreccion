import { useEffect, useState } from 'react';
import { LineChart, Line, XAxis, YAxis, CartesianGrid, Tooltip, ResponsiveContainer, ReferenceLine } from 'recharts';
import { getHistorico } from '../data/api';
import { ErrorState, LoadingState } from '../components/LoadingState';

const METRICS = [
  { key: 'dhw', label: 'DHW', color: '#b42318', unit: '°C-sem' },
  { key: 'sst', label: 'SST', color: '#0a7f86', unit: '°C' },
  { key: 'ssta', label: 'SSTA', color: '#8a5f00', unit: '°C' },
  { key: 'hotspot', label: 'HotSpot', color: '#c2410c', unit: '°C' },
];

function CustomTooltip({ active, payload, label }) {
  if (!active || !payload?.length) return null;
  return <div className="glass rounded-xl p-3 text-xs" style={{ minWidth: '140px' }}><div className="font-mono mb-1.5" style={{ color: 'var(--c-texto-2)' }}>{label}</div>{payload.map((p) => <div key={p.dataKey} className="flex justify-between gap-3 mb-0.5"><span style={{ color: p.color }}>{p.name}</span><span className="font-mono font-bold" style={{ color: p.color }}>{Number(p.value).toFixed(2)}</span></div>)}</div>;
}

export default function ViewHistorico({ area, onBack, embedded = false }) {
  const [active, setActive] = useState(new Set(['dhw', 'sst']));
  const [data, setData] = useState([]);
  const [loading, setLoading] = useState(Boolean(area));
  const [error, setError] = useState('');

  useEffect(() => {
    let cancelled = false;
    if (!area?.fid) return;
    async function load() {
      try {
        setLoading(true);
        setError('');
        const response = await getHistorico(area.fid);
        if (!cancelled) setData((response.historico || []).map((r) => ({ ...r, dhw: Number(r.dhw_promedio), sst: Number(r.sst_promedio), ssta: Number(r.ssta_promedio), hotspot: Number(r.hotspot_promedio), date: (r.fecha || '').slice(0, 10) })));
      } catch (err) {
        if (!cancelled) setError(err.message || 'No fue posible cargar el histórico.');
      } finally {
        if (!cancelled) setLoading(false);
      }
    }
    load();
    return () => { cancelled = true; };
  }, [area?.fid]);

  const toggle = (metric) => setActive((prev) => {
    const next = new Set(prev);
    if (next.has(metric) && next.size > 1) next.delete(metric); else next.add(metric);
    return next;
  });

  if (!area) return <div className={embedded ? 'embedded-history-empty' : 'h-full flex items-center justify-center'}><div className="text-center"><p className="font-display text-xl" style={{ color: 'var(--c-texto-2)' }}>Selecciona un área coralina primero</p>{!embedded && <button onClick={onBack} className="mt-4 text-sm" style={{ color: 'var(--c-acento)' }}>← Volver</button>}</div></div>;
  if (loading) return <div className={embedded ? 'embedded-history-state' : 'h-full flex items-center justify-center'}><LoadingState message={`Cargando histórico del FID ${area.fid}...`} /></div>;
  if (error) return <div className={embedded ? 'embedded-history-state' : 'h-full flex items-center justify-center'}><ErrorState message={error} /></div>;
  if (!data.length) return <div className={embedded ? 'embedded-history-state' : 'h-full flex items-center justify-center'}><ErrorState message="MongoDB no tiene registros históricos para esta área." /></div>;

  return (
    <div className={embedded ? 'history-embedded' : 'h-full flex flex-col overflow-hidden px-6 py-6'} style={embedded ? { gap: '12px' } : { gap: '12px' }}>
      <div className="flex items-start justify-between gap-4 shrink-0 flex-wrap">
        <div>
          {!embedded && <button onClick={onBack} className="flex items-center gap-1.5 text-xs mb-2" style={{ color: 'var(--c-acento)' }}>← Explorador térmico</button>}
          <h2 className={embedded ? 'font-display text-2xl font-light' : 'font-display text-3xl font-light'} style={{ color: 'var(--c-texto)' }}>Evolución <span className="text-gradient-ocean italic">Histórica</span></h2>
          <p className="text-xs mt-1" style={{ color: 'var(--c-texto-2)' }}>FID {area.fid} · {data.length} registros · derivado del área seleccionada</p>
        </div>
        <div className="flex items-center gap-2 px-3 py-1.5 rounded-full glass text-sm"><div className="w-2 h-2 rounded-full bg-teal-400 animate-pulse" /><span style={{ color: 'var(--c-acento)' }}>FID {area.fid}</span><span className="font-mono text-xs" style={{ color: 'var(--c-texto-3)' }}>{data.length} registros</span></div>
      </div>

      <div className="history-chart-card glass rounded-2xl p-5 flex flex-col min-h-0">
        <div className="flex flex-wrap gap-2 mb-4 shrink-0">
          {METRICS.map((m) => <button key={m.key} onClick={() => toggle(m.key)} className="flex items-center gap-2 px-3 py-1.5 rounded-full text-xs font-medium font-mono transition-all duration-200" style={{ background: active.has(m.key) ? `${m.color}14` : 'var(--c-fondo)', border: `1px solid ${active.has(m.key) ? m.color + '45' : 'var(--c-linea)'}`, color: active.has(m.key) ? m.color : 'var(--c-texto-3)' }}><div className="w-1.5 h-1.5 rounded-full" style={{ background: m.color, opacity: active.has(m.key) ? 1 : 0.3 }} />{m.label} <span style={{ opacity: 0.5 }}>({m.unit})</span></button>)}
        </div>
        <div className="history-chart-area flex-1 min-h-0" style={{ minHeight: embedded ? '280px' : '180px' }}>
          <ResponsiveContainer width="100%" height="100%">
            <LineChart data={data} margin={{ top: 8, right: 16, left: 0, bottom: 5 }}>
              <CartesianGrid strokeDasharray="3 3" stroke="rgba(15,52,64,0.08)" vertical={false} />
              <XAxis dataKey="date" tick={{ fontSize: 10, fontFamily: 'JetBrains Mono', fill: 'var(--c-texto-3)' }} tickLine={false} axisLine={false} interval={Math.max(0, Math.floor(data.length / 9) - 1)} />
              <YAxis tick={{ fontSize: 10, fontFamily: 'JetBrains Mono', fill: 'var(--c-texto-3)' }} tickLine={false} axisLine={false} width={35} />
              <Tooltip content={<CustomTooltip />} />
              <ReferenceLine y={4} stroke="rgba(138,95,0,0.45)" strokeDasharray="4 2" />
              <ReferenceLine y={8} stroke="rgba(180,35,24,0.45)" strokeDasharray="4 2" />
              {METRICS.map((m) => active.has(m.key) ? <Line key={m.key} type="monotone" dataKey={m.key} name={m.label} stroke={m.color} strokeWidth={2} dot={false} activeDot={{ r: 3, fill: m.color }} /> : null)}
            </LineChart>
          </ResponsiveContainer>
        </div>
        <div className="grid grid-cols-4 gap-3 mt-3 pt-3 shrink-0" style={{ borderTop: '1px solid var(--c-linea)' }}>
          {METRICS.map((m) => { const vals = data.map((r) => Number(r[m.key])); return <div key={m.key} className="text-center"><div className="font-mono text-xs mb-0.5" style={{ color: m.color }}>{m.label}</div><div className="font-mono text-sm font-bold" style={{ color: m.color }}>{Math.max(...vals).toFixed(2)}</div><div className="text-xs" style={{ color: 'var(--c-texto-3)' }}>prom {(vals.reduce((a, b) => a + b, 0) / vals.length).toFixed(2)}</div></div>; })}
        </div>
      </div>
    </div>
  );
}
