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
import ViewAcceso from './views/ViewAcceso';
import ViewCuenta, { AceptarPoliticaObligatorio, CambioPasswordObligatorio } from './views/ViewCuenta';
import ViewPrivacidad from './views/ViewPrivacidad';
import ViewAdmin from './views/ViewAdmin';
import AccesoRestringido from './components/AccesoRestringido';
import { useAuth, ROLES } from './auth/AuthContext';
import { admin as apiAdmin, getAreas, getEstadisticas, getFechas, getGeoJSON, normalizeArea } from './data/api';
import './styles/cuentas.css';

// Secciones que requieren una cuenta de investigador aprobada (o admin).
const VISTAS_DATOS = new Set(['explorador', 'resumen']);

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
  const { usuario, cargando: cargandoSesion, autenticado, puedeVerDatos, esAdmin, logout, debeAceptarPolitica } = useAuth();
  const [view, setView] = useState('inicio');
  const [selectedArea, setSelectedArea] = useState(null);
  const [collapsed, setCollapsed] = useState(false);
  const [dates, setDates] = useState([]);
  const [selectedDate, setSelectedDate] = useState(null);
  const [areas, setAreas] = useState([]);
  const [geojson, setGeojson] = useState(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState('');
  const [estadisticas, setEstadisticas] = useState(null);
  const [pendientes, setPendientes] = useState(0);

  // Cifras públicas para la página de inicio (sin datos ambientales).
  useEffect(() => {
    getEstadisticas().then(setEstadisticas).catch(() => setEstadisticas(null));
  }, []);

  // Los datos ambientales solo se piden si el rol lo permite y la cuenta no
  // tiene una contraseña temporal pendiente; si el usuario cierra sesión o
  // pierde el permiso, se borran de la memoria.
  const datosHabilitados = puedeVerDatos && !usuario?.debe_cambiar_password && !debeAceptarPolitica;
  const usuarioId = usuario?.id || null;

  useEffect(() => {
    if (!datosHabilitados) {
      setDates([]); setSelectedDate(null); setAreas([]); setGeojson(null); setSelectedArea(null); setError('');
      return undefined;
    }
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
  }, [datosHabilitados, usuarioId]);

  useEffect(() => {
    if (!selectedDate || !datosHabilitados) return undefined;
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
  }, [selectedDate, geojson, datosHabilitados]);

  // Contador de solicitudes pendientes para el administrador.
  useEffect(() => {
    if (!esAdmin) { setPendientes(0); return; }
    apiAdmin.usuarios({ solicitud: 'pendiente' }).then((r) => setPendientes(r.pendientes)).catch(() => {});
  }, [esAdmin]);

  // Al cerrar sesión, salir de las vistas privadas.
  useEffect(() => {
    if (cargandoSesion) return;
    if (!autenticado && (view === 'cuenta' || view === 'admin')) setView('inicio');
    if (!esAdmin && view === 'admin') setView('inicio');
  }, [autenticado, esAdmin, cargandoSesion, view]);

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
    acceso: 'Iniciar sesión',
    registro: 'Crear cuenta',
    cuenta: 'Mi cuenta',
    admin: 'Administración',
    privacidad: 'Política de datos',
  };

  function alAcceder(u, modo) {
    if (u?.rol === 'investigador' || u?.rol === 'admin') setView(view === 'acceso' || view === 'registro' ? 'explorador' : view);
    else setView(modo === 'registro' ? 'cuenta' : 'inicio');
  }

  async function cerrarSesion() {
    await logout();
    setView('inicio');
  }

  function renderVista() {
    if (VISTAS_DATOS.has(view) && !puedeVerDatos) {
      return <AccesoRestringido seccion={VIEW_TITLES[view]} onNavigate={navigate} />;
    }
    if (VISTAS_DATOS.has(view) && loading) {
      return <LoadingState message="Cargando el territorio..." />;
    }
    if (VISTAS_DATOS.has(view) && error && !dates.length) {
      return <ErrorState message={error} />;
    }
    switch (view) {
      case 'inicio':
        return <ViewInicio onNavigate={navigate} areasCount={estadisticas?.total_areas || 47} pixelCount={estadisticas?.total_pixeles || 20} datesCount={estadisticas?.total_fechas || dates.length} selectedDate={selectedDate} />;
      case 'corales':
        return <ViewErrorBoundary><ViewCorales /></ViewErrorBoundary>;
      case 'estres':
        return <ViewEstres />;
      case 'indicadores':
        return <ViewIndicadores />;
      case 'explorador':
        return (
          <ViewErrorBoundary>
          <ViewExplorador
            areas={areas}
            dates={dates}
            selectedDate={selectedDate}
            onDateChange={setSelectedDate}
            geojson={geojson}
            selectedArea={selectedArea}
            onSelectArea={handleSelectArea}
          />
          </ViewErrorBoundary>
        );
      case 'resumen':
        return <ViewErrorBoundary><ViewResumen areas={areas} totalDates={dates.length} /></ViewErrorBoundary>;
      case 'metodologia':
        return <ViewMetodologia />;
      case 'acceso':
      case 'registro':
        return autenticado
          ? <ViewCuenta onNavigate={navigate} />
          : <ViewAcceso key={view} modoInicial={view === 'registro' ? 'registro' : 'login'} onExito={alAcceder} />;
      case 'cuenta':
        return autenticado ? <ViewCuenta onNavigate={navigate} /> : null;
      case 'privacidad':
        return <ViewPrivacidad />;
      case 'admin':
        return esAdmin ? <ViewErrorBoundary><ViewAdmin onPendientes={setPendientes} /></ViewErrorBoundary> : null;
      default:
        return null;
    }
  }

  if (cargandoSesion) {
    return (
      <div className="h-screen flex items-center justify-center" style={{ background: 'var(--ocean-900)' }}>
        <LoadingState message="Cargando Coraleum..." />
      </div>
    );
  }

  // Contraseña temporal: nada más está disponible hasta cambiarla.
  if (usuario?.debe_cambiar_password) {
    return (
      <div style={{ height: '100dvh', background: 'linear-gradient(145deg, #0f303a 0%, #123b45 100%)' }}>
        <CambioPasswordObligatorio />
      </div>
    );
  }

  // Cuentas sin la autorización vigente (Ley 1581): deben aceptarla primero.
  if (debeAceptarPolitica) {
    return (
      <div style={{ height: '100dvh', background: 'linear-gradient(145deg, #0f303a 0%, #123b45 100%)' }}>
        <AceptarPoliticaObligatorio />
      </div>
    );
  }

  return (
    <div className="flex" style={{ height: '100dvh', width: '100vw', overflow: 'hidden', background: '#eef8f7' }}>
      <Sidebar active={view} onNavigate={navigate} collapsed={collapsed} autenticado={autenticado} puedeVerDatos={puedeVerDatos} esAdmin={esAdmin} pendientes={pendientes} />

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
            {puedeVerDatos && (
              <>
                <div className="w-1.5 h-1.5 rounded-full bg-teal-400 animate-pulse" />
                <span className="text-xs font-mono hidden md:inline" style={{ color: 'rgba(10,143,139,0.70)' }}>{areas.length || '—'} áreas · {dates.length} fechas</span>
                <div className="header-date hidden md:flex"><span>▣</span>{selectedDate ? selectedDate.replace('T', ' ').slice(0, 16) : '—'}</div>
              </>
            )}
            {autenticado ? (
              <div className="sesion-chip">
                <span className="nombre" title={usuario.email}>{usuario.nombre}</span>
                <span className={`badge badge-${usuario.rol}`}>{ROLES[usuario.rol] || usuario.rol}</span>
                <button type="button" onClick={cerrarSesion}>Salir</button>
              </div>
            ) : (
              <button type="button" className="btn-entrar" onClick={() => navigate('acceso')}>Iniciar sesión</button>
            )}
          </div>
        </header>

        {error && puedeVerDatos && VISTAS_DATOS.has(view) && dates.length > 0 && (
          <div className="shrink-0 px-5 py-1.5 text-xs font-mono" style={{ background: 'rgba(255,107,71,0.08)', color: '#ff9b6b', borderBottom: '1px solid rgba(255,107,71,0.15)' }}>
            {error}
          </div>
        )}

        <main
          className="flex-1 min-h-0 overflow-hidden transition-opacity duration-200"
          style={{ background: 'linear-gradient(145deg, #eef8f7 0%, #e8f3f2 58%, #f6faf9 100%)' }}
          key={view}
        >
          {renderVista()}
        </main>
      </div>
    </div>
  );
}
