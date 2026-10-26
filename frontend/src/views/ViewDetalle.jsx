import { useEffect, useState } from 'react';
import { CLASSIFICATION_COLORS, getArea } from '../data/api';
import { LoadingState, ErrorState } from '../components/LoadingState';

function DHWSummary({ value }) {
  const numeric = Number(value);
  const safe = Number.isFinite(numeric) ? Math.max(0, numeric) : 0;
  const max = 8;
  const pct = Math.min(100, (safe / max) * 100);
  const color = safe < 3.57 ? '#4ade80' : safe < 4.74 ? '#fbbf24' : '#ff6b47';
  const label = safe < 3.57 ? 'Baja' : safe < 4.74 ? 'Intermedia' : 'Alta';

  return (
    <div className="dhw-summary" aria-label={`DHW promedio ${safe.toFixed(2)} grados Celsius semana`}>
      <div className="dhw-summary-heading">
        <div>
          <div className="dhw-summary-label">DHW PROMEDIO</div>
          <div className="dhw-summary-value" style={{ color }}>
            {safe.toFixed(2)} <span>°C-sem</span>
          </div>
        </div>
        <div className="dhw-summary-status" style={{ color, background: `${color}14`, borderColor: `${color}35` }}>
          {label}
        </div>
      </div>

      <div className="dhw-summary-track" role="img" aria-label={`Escala DHW: ${label}`}>
        <div className="dhw-summary-zone dhw-summary-zone-low" />
        <div className="dhw-summary-zone dhw-summary-zone-mid" />
        <div className="dhw-summary-zone dhw-summary-zone-high" />
        <div className="dhw-summary-marker" style={{ left: `${pct}%`, background: color, borderColor: '#eafaf7' }} />
      </div>

      <div className="dhw-summary-scale">
        <span>0</span><span>3.57</span><span>4.74</span><span>≥ 8</span>
      </div>
      <div className="dhw-summary-note">Carga térmica media del área en la fecha consultada.</div>
    </div>
  );
}

export default function ViewDetalle({ area, fecha = null, onGoHistorico, onBack, embedded = false }) {
  const [detail, setDetail] = useState(area);
  const [loading, setLoading] = useState(Boolean(area));
  const [error, setError] = useState('');

  useEffect(() => {
    let cancelled = false;
    if (!area?.fid) return;
    async function load() {
      try {
        setLoading(true);
        setError('');
        // Se envía la fecha seleccionada: antes el detalle mostraba siempre la última fecha.
        const raw = await getArea(area.fid, fecha);
        if (!cancelled) setDetail({ ...area, dhwAvg: Number(raw.dhw_promedio), dhwMax: Number(raw.dhw_max_asociado), sstAvg: Number(raw.sst_promedio), sstaAvg: Number(raw.ssta_promedio), hotspotAvg: Number(raw.hotspot_promedio), pixels: Number(raw.numero_pixeles), classification: raw.categoria_exposicion_relativa, fecha: raw.fecha });
      } catch (err) {
        if (!cancelled) setError(err.message || 'No fue posible cargar el detalle.');
      } finally {
        if (!cancelled) setLoading(false);
      }
    }
    load();
    return () => { cancelled = true; };
  }, [area?.fid, fecha]);

  if (!area) return null;
  if (loading && !detail) return <LoadingState message="Cargando ficha del área..." />;
  if (!detail) return <ErrorState message={error || 'Área no disponible.'} />;

  const catColor = CLASSIFICATION_COLORS[detail.classification] || '#00c4b4';
  const metrics = [
    { label: 'DHW Máximo', value: detail.dhwMax, unit: '°C-sem', color: '#ff6b47' },
    { label: 'Píxeles NOAA', value: detail.pixels, unit: 'px', color: '#00c4b4' },
    { label: 'SST Promedio', value: detail.sstAvg, unit: '°C', color: '#40e0d0' },
    { label: 'SSTA Promedio', value: detail.sstaAvg, unit: '°C', color: '#fbbf24' },
    { label: 'HotSpot Prom.', value: detail.hotspotAvg, unit: '°C', color: '#f97316' },
    { label: 'Clasificación', value: detail.classification, unit: '', color: catColor },
  ];

  return (
    <div className={embedded ? 'detail-embedded' : 'h-full overflow-y-auto px-8 py-6'}>
      <div className={embedded ? '' : 'max-w-4xl mx-auto'}>
        {!embedded && <button onClick={onBack} className="flex items-center gap-1.5 text-xs mb-3 transition-colors" style={{ color: 'rgba(0,196,180,0.55)' }}>← Explorador térmico</button>}
        <div className="flex items-start justify-between gap-4 mb-4 flex-wrap">
          <div>
            <span className="font-mono text-xs" style={{ color: 'rgba(194,231,231,.42)' }}>FID {detail.fid}</span>
            <h2 className={embedded ? 'font-display text-2xl md:text-3xl font-light mt-1' : 'font-display text-4xl font-light mt-1'} style={{ color: '#e8f4f8' }}>
              Área <span className="text-gradient-ocean italic">coralina</span>
            </h2>
            <p className="text-xs md:text-sm mt-1" style={{ color: 'rgba(194,231,231,.62)' }}>{detail.label || 'Áreas coralinas'} · datos {detail.fecha || '—'}</p>
          </div>
          <div className="px-3 py-1.5 rounded-full text-xs font-mono" style={{ color: catColor, background: `${catColor}12`, border: `1px solid ${catColor}35` }}>{detail.classification}</div>
        </div>

        {error && <div className="mb-4"><ErrorState message={error} /></div>}

        <div className="detail-main-card">
          <div className="detail-dhw-card">
            <DHWSummary value={detail.dhwAvg} />
          </div>
          <div className="detail-metric-grid">
            {metrics.map(({ label, value, unit, color }) => (
              <div key={label} className="detail-metric-card">
                <div className="text-xs mb-1" style={{ color: 'rgba(194,231,231,.58)' }}>{label}</div>
                <div className="font-mono text-base font-bold" style={{ color }}>
                  {typeof value === 'number' ? value.toFixed(2) : value}{unit && <span className="text-xs ml-1 font-normal" style={{ opacity: .65 }}>{unit}</span>}
                </div>
              </div>
            ))}
          </div>
        </div>

        <div className="detail-note">
          <svg className="w-4 h-4 shrink-0 mt-0.5" fill="none" viewBox="0 0 24 24" stroke="#00c4b4"><path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M13 16h-1v-4h-1m1-4h.01M21 12a9 9 0 11-18 0" /></svg>
          <p className="text-xs" style={{ color: 'rgba(194,231,231,.68)', lineHeight: 1.7 }}>La categoría <strong style={{ color: catColor }}>{detail.classification}</strong> es una clasificación <strong>relativa</strong> al conjunto de áreas analizadas y no corresponde a categorías oficiales de alerta NOAA.</p>
        </div>

        <button onClick={onGoHistorico} className="detail-history-button">Ver evolución histórica →</button>
      </div>
    </div>
  );
}
