import React, { useCallback, useEffect, useMemo, useState } from 'react';
import Sidebar from './components/Sidebar';
import { ErrorState, LoadingState } from './components/LoadingState';
import ViewInicio from './views/ViewInicio';
import ViewCorales from './views/ViewCorales';
import ViewEstres from './views/ViewEstres';
import ViewIndicadores from './views/ViewIndicadores';
import ViewExplorador from './views/ViewExplorador';
import ViewDetalle from './views/ViewDetalle';
import ViewResumen from './views/ViewResumen';
import ViewMetodologia from './views/ViewMetodologia';
import { getAreas, getFechas, getGeoJSON, normalizeArea } from './data/api';

class ViewErrorBoundary extends React.Component {
  constructor(props) {
    super(props);
    this.state = { hasError: false };
  }

  static getDerivedStateFromError() {
    return { hasError: true };
  }

  render() {
    if (this.state.hasError) {
      return (
        <div className="view-error-fallback">
          <div className="view-error-card">
            <span>Esta vista no pudo cargarse.</span>
            <button type="button" onClick={() => window.location.reload()}>Recargar vista</button>
          </div>
        </div>
      );
    }
    return this.props.children;
  }
}

export default function App() {
  const [view, setView] = useState('inicio');
  const [selectedArea, setSelectedArea] = useState(null);
  const [collapsed, setCollapsed] = useState(false);
  const [dates, setDates] = useState([]);
  const [selectedDate, setSelectedDate] = useState(null);
  const [areas, setAreas] = useState([]);
  const [geojson, setGeojson] = useState(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');

  useEffect(() => {
    let cancelled = false;
    async function loadInitialData() {
      try {
        setLoading(true);
        setError('');
        const [dateResponse, geojsonResponse] = await Promise.all([getFechas(), getGeoJSON()]);
        if (cancelled) return;
        setDates(dateResponse.fechas || []);
        setSelectedDate(dateResponse.fecha_final || dateResponse.fechas?.at(-1) || null);
        setGeojson(geojsonResponse);
      } catch (err) {
        if (!cancelled) setError(err.message || 'No fue posible conectar con el backend.');
      } finally {
        if (!cancelled) setLoading(false);
      }
    }
    loadInitialData();
    return () => { cancelled = true; };
  }, []);

  useEffect(() => {
    if (!selectedDate) return;
    let cancelled = false;
    async function loadAreas() {
      try {
        setError('');
        const response = await getAreas(selectedDate);
        if (cancelled) return;
        const features = new Map((geojson?.features || []).map((feature) => [Number(feature.properties.FID), feature]));
        const normalized = (response.areas || []).map((raw) => normalizeArea(raw, features.get(Number(raw.fid_area_coralina))));
        setAreas(normalized);
      } catch (err) {
        if (!cancelled) setError(err.message || 'No fue posible obtener las áreas.');
      }
    }
    loadAreas();
    return () => { cancelled = true; };
  }, [selectedDate, geojson]);

  const featureByFid = useMemo(
    () => new Map((geojson?.features || []).map((feature) => [Number(feature.properties.FID), feature])),
    [geojson],
  );

  const navigate = useCallback((id) => setView(id), []);

  const handleSelectArea = useCallback((area) => {
    setSelectedArea(area);
    // El detalle vive dentro del Explorador Térmico; no cambia de sección.
    setView('explorador');
  }, []);

  const VIEW_TITLES = {
    inicio: 'Inicio',
    corales: 'Conoce los Corales',
    estres: 'Estrés Térmico',
    indicadores: 'Indicadores NOAA',
    explorador: 'Explorador Térmico',
    resumen: 'Resumen del Territorio',
    metodologia: 'Metodología',
  };

  if (loading) {
    return (
      <div className="h-screen flex items-center justify-center" style={{ background: '#eef8f7' }}>
        <LoadingState message="Conectando con el backend y cargando el territorio..." />
      </div>
    );
  }

  if (error && !dates.length) {
    return (
      <div className="h-screen flex flex-col items-center justify-center px-8" style={{ background: '#eef8f7' }}>
        <ErrorState message={error} />
        <p className="text-xs mt-2 font-mono" style={{ color: 'rgba(57,91,101,0.68)' }}>
          Verifica que Docker tenga activos MongoDB y FastAPI y que el frontend pueda acceder a /api.
        </p>
      </div>
    );
  }

  return (
    <div className="flex" style={{ height: '100dvh', width: '100vw', overflow: 'hidden', background: '#eef8f7' }}>
      <Sidebar active={view} onNavigate={navigate} collapsed={collapsed} />

      <div className="flex-1 flex flex-col min-w-0 overflow-hidden">
        <header
          className="shrink-0 flex items-center gap-3 px-5"
          style={{ height: '52px', borderBottom: '1px solid rgba(35,113,122,0.12)', background: 'rgba(255,255,255,0.72)', backdropFilter: 'blur(12px)' }}
        >
          <button
            onClick={() => setCollapsed(!collapsed)}
            className="w-7 h-7 flex flex-col items-center justify-center gap-1 rounded-lg transition-all duration-200 shrink-0"
            style={{ border: '1px solid rgba(35,113,122,0.14)', background: 'rgba(255,255,255,0.54)' }}
            onMouseEnter={(e) => { e.currentTarget.style.borderColor = 'rgba(10,166,160,0.34)'; }}
            onMouseLeave={(e) => { e.currentTarget.style.borderColor = 'rgba(35,113,122,0.14)'; }}
          >
            {[0, 1, 2].map((i) => (
              <div key={i} className="rounded-full transition-all duration-200" style={{ width: i === 1 && !collapsed ? '10px' : '14px', height: '1.5px', background: 'rgba(0,196,180,0.5)' }} />
            ))}
          </button>

          <div className="flex items-center gap-2 text-xs min-w-0">
            <span style={{ color: 'rgba(57,91,101,0.68)' }}>PNN Corales</span>
            <span style={{ color: 'rgba(10,143,139,0.40)' }}>/</span>
            <span className="font-medium truncate" style={{ color: 'rgba(36,79,93,0.86)' }}>{VIEW_TITLES[view]}</span>
          </div>

          <div className="flex-1" />
          <div className="flex items-center gap-2 shrink-0">
            <div className="w-1.5 h-1.5 rounded-full bg-teal-400 animate-pulse" />
            <span className="text-xs font-mono" style={{ color: 'rgba(10,143,139,0.70)' }}>{areas.length || '—'} áreas · {dates.length} fechas</span>
            <div className="header-date"><span>▣</span>{selectedDate ? selectedDate.replace('T', ' ').slice(0, 16) : '—'}</div>
          </div>
        </header>

        {error && (
          <div className="shrink-0 px-5 py-1.5 text-xs font-mono" style={{ background: 'rgba(255,107,71,0.08)', color: '#ff9b6b', borderBottom: '1px solid rgba(255,107,71,0.15)' }}>
            {error}
          </div>
        )}

        <main
          className="flex-1 min-h-0 overflow-hidden transition-opacity duration-200"
          style={{ background: 'linear-gradient(145deg, #eef8f7 0%, #e8f3f2 58%, #f6faf9 100%)' }}
          key={view}
        >
          {view === 'inicio' && <ViewInicio onNavigate={navigate} areasCount={areas.length || 47} pixelCount={20} datesCount={dates.length} selectedDate={selectedDate} />}
          {view === 'corales' && <ViewErrorBoundary><ViewCorales /></ViewErrorBoundary>}
          {view === 'estres' && <ViewEstres />}
          {view === 'indicadores' && <ViewIndicadores />}
          {view === 'explorador' && (
            <ViewExplorador
              areas={areas}
              dates={dates}
              selectedDate={selectedDate}
              onDateChange={setSelectedDate}
              geojson={geojson}
              selectedArea={selectedArea}
              onSelectArea={handleSelectArea}
            />
          )}
          {view === 'resumen' && <ViewResumen areas={areas} totalDates={dates.length} />}
          {view === 'metodologia' && <ViewMetodologia />}
        </main>
      </div>
    </div>
  );
}
