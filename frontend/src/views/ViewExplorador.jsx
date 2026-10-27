import { useEffect, useMemo, useRef } from 'react';
// Leaflet instalado con npm (antes se cargaba desde unpkg sin verificación de integridad).
import L from 'leaflet';
import 'leaflet/dist/leaflet.css';
import { CLASSIFICATIONS, CLASSIFICATION_COLORS, CLASSIFICATION_TEXT, formatDateTime } from '../data/api';
import ViewDetalle from './ViewDetalle';
import ViewHistorico from './ViewHistorico';

const CENTER = [10.12, -75.76];

function popup(area, fid) {
  if (!area) return `<div class="coral-popup"><strong>FID ${fid}</strong><p>Sin datos para esta fecha.</p></div>`;
  return `<div class="coral-popup"><div class="coral-popup-kicker">ÁREA CORALINA</div><strong>FID ${area.fid}</strong><div class="coral-popup-grid">
    <span>DHW</span><b>${Number(area.dhwAvg || 0).toFixed(2)}</b>
    <span>SST</span><b>${Number(area.sstAvg || 0).toFixed(2)} °C</b>
    <span>SSTA</span><b>${Number(area.sstaAvg || 0).toFixed(2)} °C</b>
    <span>HotSpot</span><b>${Number(area.hotspotAvg || 0).toFixed(2)} °C</b>
  </div><div class="coral-popup-status">${area.classification} · ${area.pixels} píxel(es) NOAA</div></div>`;
}

export default function ViewExplorador({
  areas,
  dates,
  selectedDate,
  onDateChange,
  geojson,
  selectedArea,
  onSelectArea,
  puedeVerHistorico = true,
}) {
  const scrollRef = useRef(null);
  const nodeRef = useRef(null);
  const mapRef = useRef(null);
  const layerRef = useRef(null);
  const resizeObserverRef = useRef(null);
  const detailRef = useRef(null);
  const historyRef = useRef(null);
  const areasByFid = useMemo(() => new Map(areas.map((a) => [a.fid, a])), [areas]);

  const stats = CLASSIFICATIONS.reduce((acc, c) => {
    acc[c] = areas.filter((a) => a.classification === c).length;
    return acc;
  }, { Baja: 0, Intermedia: 0, Alta: 0 });
  const total = areas.length || 1;

  useEffect(() => {
    if (!nodeRef.current || mapRef.current) return;
    const map = L.map(nodeRef.current, {
      zoomControl: false,
      preferCanvas: true,
      minZoom: 9,
      maxZoom: 19,
      zoomSnap: 0.5,
      zoomDelta: 0.5,
    }).setView(CENTER, 10.8);

    L.control.zoom({ position: 'bottomright' }).addTo(map);

    L.tileLayer('https://services.arcgisonline.com/ArcGIS/rest/services/World_Imagery/MapServer/tile/{z}/{y}/{x}', {
      maxZoom: 19,
      attribution: 'Tiles © Esri — Source: Esri, Maxar, Earthstar Geographics and the GIS User Community',
    }).addTo(map);

    L.tileLayer('https://services.arcgisonline.com/ArcGIS/rest/services/Reference/World_Boundaries_and_Places/MapServer/tile/{z}/{y}/{x}', {
      maxZoom: 19,
      opacity: 0.72,
      attribution: 'Labels © Esri',
      pane: 'overlayPane',
    }).addTo(map);

    mapRef.current = map;

    const invalidate = () => requestAnimationFrame(() => map.invalidateSize({ pan: false }));
    resizeObserverRef.current = new ResizeObserver(invalidate);
    resizeObserverRef.current.observe(nodeRef.current);
    window.addEventListener('resize', invalidate);
    const timer = setTimeout(invalidate, 200);

    return () => {
      clearTimeout(timer);
      window.removeEventListener('resize', invalidate);
      resizeObserverRef.current?.disconnect();
      resizeObserverRef.current = null;
      map.remove();
      mapRef.current = null;
    };
  }, []);

  useEffect(() => {
    const map = mapRef.current;
    if (!map || !geojson) return;
    if (layerRef.current) layerRef.current.remove();

    const layer = L.geoJSON(geojson, {
      style: (feature) => {
        const fid = Number(feature?.properties?.FID);
        const area = areasByFid.get(fid);
        const color = area ? CLASSIFICATION_COLORS[area.classification] : '#7ce5d9';
        return {
          color: area ? color : '#b8fff6',
          weight: area ? 2 : 1,
          opacity: 0.95,
          fillColor: color,
          fillOpacity: area ? 0.34 : 0.08,
        };
      },
      onEachFeature: (feature, item) => {
        const fid = Number(feature?.properties?.FID);
        const area = areasByFid.get(fid);
        item.bindPopup(popup(area, fid), { className: 'coral-map-popup', maxWidth: 290 });
        item.on({
          mouseover: (e) => {
            e.target.setStyle({ weight: 3, color: '#ffffff', fillOpacity: area ? 0.60 : 0.18 });
            e.target.bringToFront();
          },
          mouseout: (e) => layer.resetStyle(e.target),
          click: () => area && onSelectArea(area),
        });
      },
    }).addTo(map);
    layerRef.current = layer;

    map.setView(CENTER, 10.8, { animate: false });
    requestAnimationFrame(() => map.invalidateSize({ pan: false }));
    return () => layer.remove();
  }, [geojson, areasByFid, onSelectArea]);

  useEffect(() => {
    if (!selectedArea || !detailRef.current || !scrollRef.current) return;
    const timer = setTimeout(() => {
      const scroller = scrollRef.current;
      const target = detailRef.current;
      const top = Math.max(0, target.offsetTop - 14);
      scroller.scrollTo({ top, behavior: 'smooth' });
    }, 220);
    return () => clearTimeout(timer);
  }, [selectedArea?.fid]);

  return (
    <div ref={scrollRef} className="explorer-page h-full flex flex-col overflow-y-auto px-5 py-5" style={{ gap: 14 }}>
      <div className="flex items-end justify-between gap-4 shrink-0 flex-wrap">
        <div>
          <span className="text-xs tracking-widest uppercase font-medium block mb-1" style={{ color: 'var(--c-acento)' }}>Exploración geoespacial</span>
          <h2 className="font-display text-3xl md:text-4xl font-light" style={{ color: 'var(--c-texto)' }}>Explorador <span className="text-gradient-ocean italic">Térmico</span></h2>
        </div>
        <div className="glass rounded-full px-3 py-2 text-xs flex items-center gap-2"><span className="status-dot" />{areas.length} áreas · <span className="font-mono">{formatDateTime(selectedDate)}</span></div>
      </div>

      <div className="glass explorer-date-panel rounded-2xl p-3 shrink-0 flex items-center gap-3 flex-wrap">
        <div className="date-control"><span>FECHA</span><strong>{formatDateTime(selectedDate)}</strong></div>
        <div className="date-strip">{dates.map((date) => <button key={date} onClick={() => onDateChange(date)} className={`date-chip ${selectedDate === date ? 'active' : ''}`}>{date.slice(0, 10)}</button>)}</div>
        <div className="ml-auto hidden xl:flex items-center gap-3 text-xs">{CLASSIFICATIONS.map((c) => <div key={c} className="flex items-center gap-1.5" style={{ color: 'var(--c-texto-2)' }}><span className="legend-dot" style={{ background: CLASSIFICATION_COLORS[c] }} />{c} {stats[c]}</div>)}</div>
      </div>

      <div className="explorer-main-grid shrink-0">
        <section className="explorer-map-card rounded-2xl min-h-0 flex flex-col">
          <div className="flex items-center justify-between gap-3 px-1 pb-2">
            <div>
              <div className="text-xs font-medium" style={{ color: 'var(--c-texto)' }}>PNN Corales del Rosario y San Bernardo</div>
              <div className="text-[10px] mt-0.5" style={{ color: 'var(--c-texto-2)' }}>Imagen satelital · 47 áreas coralinas · GeoJSON del proyecto</div>
            </div>
            <div className="map-selection-hint">Selecciona una zona directamente en el mapa</div>
          </div>
          <div className="relative rounded-xl overflow-hidden map-shell explorer-map-shell">
            <div ref={nodeRef} className="absolute inset-0 z-0" />
            <div className="map-overlay map-overlay-bottom">Haz clic en un área coralina para consultar sus indicadores</div>
          </div>
        </section>

        <aside className="glass rounded-2xl p-4 flex flex-col">
          <div className="mb-4"><div className="text-xs tracking-widest uppercase" style={{ color: 'var(--c-acento)' }}>Estado territorial</div><h3 className="font-display text-xl font-light mt-1" style={{ color: 'var(--c-texto)' }}>Distribución</h3></div>
          <div className="space-y-4 flex-1">{CLASSIFICATIONS.map((c) => { const count = stats[c]; const pct = Math.round(count / total * 100); return <div key={c}><div className="flex justify-between items-center mb-1.5"><div className="flex items-center gap-2"><span className="legend-dot" style={{ background: CLASSIFICATION_COLORS[c] }} /><span className="text-xs" style={{ color: 'var(--c-texto)' }}>{c}</span></div><span className="font-mono text-sm font-bold" style={{ color: CLASSIFICATION_TEXT[c] }}>{count}</span></div><div className="h-1.5 rounded-full" style={{ background: 'var(--c-superficie-2)' }}><div className="h-full rounded-full" style={{ width: `${pct}%`, background: CLASSIFICATION_COLORS[c] }} /></div></div>; })}</div>
          <div className="metric-card"><div className="metric-label">Píxeles NOAA</div><div className="metric-value">20</div><div className="metric-sub">Resolución aproximada 5 km</div></div>
          <div className="metric-card"><div className="metric-label">Fecha consultada</div><div className="metric-date">{selectedDate ? selectedDate.slice(0, 10) : '—'}</div><div className="metric-sub">UTC · datos diarios</div></div>
          <div className="text-[10px] mt-3 leading-relaxed" style={{ color: 'var(--c-texto-3)' }}>La clasificación mostrada es relativa al conjunto de áreas analizadas y no corresponde a una alerta oficial de NOAA Coral Reef Watch.</div>
        </aside>
      </div>

      <section ref={detailRef} className="explorer-detail-section glass rounded-2xl p-4 md:p-5 shrink-0" aria-live="polite">
        <div className="detail-section-heading flex items-center justify-between gap-3 mb-4">
          <div>
            <div className="text-xs tracking-widest uppercase" style={{ color: 'var(--c-acento)' }}>Análisis del área seleccionada</div>
            <h3 className="font-display text-2xl font-light" style={{ color: 'var(--c-texto)' }}>Detalle integrado</h3>
          </div>
          {selectedArea && <div className="glass rounded-full px-3 py-1.5 text-xs" style={{ color: 'var(--c-acento)' }}>FID {selectedArea.fid}</div>}
        </div>
        {selectedArea ? (
          <ViewDetalle area={selectedArea} fecha={selectedDate} embedded onGoHistorico={puedeVerHistorico ? () => historyRef.current?.scrollIntoView({ behavior: 'smooth', block: 'start' }) : null} onBack={() => {}} />
        ) : (
          <div className="detail-empty-state">
            <div className="detail-empty-icon">⌖</div>
            <div>
              <div className="text-sm font-medium" style={{ color: 'var(--c-texto)' }}>Selecciona un área coralina en el mapa</div>
              <div className="text-xs mt-1" style={{ color: 'var(--c-texto-2)' }}>El detalle aparecerá aquí sin salir del Explorador Térmico.</div>
            </div>
          </div>
        )}
      </section>

      {selectedArea && puedeVerHistorico && (
        <>
        <div className="explorer-flow-divider"><span>evolución histórica del área seleccionada</span></div>
        <section ref={historyRef} className="explorer-history-section glass rounded-2xl p-4 md:p-5 shrink-0" aria-live="polite">
          <ViewHistorico area={selectedArea} embedded onBack={() => {}} />
        </section>
        </>
      )}
      {selectedArea && !puedeVerHistorico && (
        <div className="detail-empty-state" style={{ marginTop: 12 }}>
          <div className="detail-empty-icon">🔒</div>
          <div className="text-xs" style={{ color: 'var(--c-texto-2)' }}>Tu rol no incluye el registro histórico. Un administrador puede asignarte el permiso.</div>
        </div>
      )}
    </div>
  );
}
