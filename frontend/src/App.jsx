import React, { useCallback, useEffect, useMemo, useRef, useState } from 'react';
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
import ViewActua from './views/ViewActua';
import AvisoInsignia from './educacion/AvisoInsignia';
import AccesoRestringido from './components/AccesoRestringido';
import { useAuth, ROLES } from './auth/AuthContext';
import { admin as apiAdmin, getAreas, getEstadisticas, getFechas, getGeoJSON, normalizeArea } from './data/api';
import './styles/cuentas.css';
import './styles/educacion.css';
import './styles/tema-claro.css';
import './styles/marino.css';
import FondoMarino from './components/FondoMarino';

// Secciones que requieren una cuenta de investigador aprobada (o admin).
const VISTAS_DATOS = new Set(['explorador', 'resumen']);

const VISTAS = new Set(['inicio', 'corales', 'estres', 'indicadores', 'actua', 'explorador', 'resumen', 'metodologia', 'acceso', 'registro', 'cuenta', 'admin', 'privacidad']);

/**
 * Cada sección y cada consulta tienen su propia dirección, por ejemplo
 *   #/explorador?fecha=2026-10-20T00:00:00Z&area=12
 * La dirección NUNCA lleva datos de sesión (esos viajan en cookies HttpOnly):
 * copiarla a otra pestaña o navegador solo funciona si allí hay una sesión válida.
 */
function leerDireccion() {
  const [ruta, consulta = ''] = window.location.hash.replace(/^#\/?/, '').split('?');
  const params = new URLSearchParams(consulta);
  const area = Number(params.get('area'));
  return {
    vista: VISTAS.has(ruta) ? ruta : 'inicio',
    fecha: params.get('fecha') || null,
    area: Number.isInteger(area) && area >= 0 ? area : null,
  };
}

function construirDireccion(vista, fecha, area) {
  const params = new URLSearchParams();
  if (vista === 'explorador' && fecha) params.set('fecha', fecha);
  if (vista === 'explorador' && area !== null && area !== undefined) params.set('area', String(area));
  const consulta = params.toString();
  return `#/${vista}${consulta ? `?${consulta}` : ''}`;
}

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
  const { usuario, cargando: cargandoSesion, autenticado, puedeVerDatos, puedeVerHistorico, esAdmin, tienePermiso, logout, debeAceptarPolitica, aviso, notificacion, setNotificacion } = useAuth();
  const [view, setView] = useState(() => leerDireccion().vista);
  // Fecha y área pedidas en la dirección; se aplican cuando llegan los datos.
  const consultaPendiente = useRef({ fecha: leerDireccion().fecha, area: leerDireccion().area });
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
        const pedida = consultaPendiente.current.fecha;
        consultaPendiente.current.fecha = null;
        setSelectedDate(
          pedida && (dateResponse.fechas || []).includes(pedida)
            ? pedida
            : dateResponse.fecha_final || dateResponse.fechas?.at(-1) || null,
        );
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
        const areaPedida = consultaPendiente.current.area;
        if (areaPedida !== null) {
          consultaPendiente.current.area = null;
          const encontrada = normalized.find((a) => a.fid === areaPedida);
          if (encontrada) setSelectedArea(encontrada);
        }
      } catch (err) {
        if (!cancelled) setError(err.message || 'No fue posible obtener las áreas.');
      }
    }
    loadAreas();
    return () => { cancelled = true; };
  }, [selectedDate, geojson, datosHabilitados]);

  // Contador de solicitudes pendientes para el administrador.
  useEffect(() => {
    const puedeVerSolicitudes = tienePermiso('solicitudes.aprobar') || tienePermiso('usuarios.gestionar');
    if (!puedeVerSolicitudes || !usuario?.dos_pasos) { setPendientes(0); return; }
    apiAdmin.usuarios({ solicitud: 'pendiente' })
      .then((r) => setPendientes((tienePermiso('solicitudes.aprobar') ? r.pendientes : 0) + (tienePermiso('usuarios.gestionar') ? r.recuperaciones : 0)))
      .catch(() => {});
  }, [tienePermiso, usuario?.dos_pasos, view]);

  // Al cerrar sesión, salir de las vistas privadas.
  useEffect(() => {
    if (cargandoSesion) return;
    // Sesión cerrada por inactividad u otra causa: llevar al inicio de sesión con el aviso.
    if (!autenticado && aviso && view !== 'acceso') { setView('acceso'); return; }
    if (!autenticado && (view === 'cuenta' || view === 'admin')) setView('inicio');
    if (!esAdmin && view === 'admin') setView('inicio');
  }, [autenticado, esAdmin, cargandoSesion, view, aviso]);

  // La dirección del navegador refleja la sección y la consulta actuales.
  useEffect(() => {
    const destino = construirDireccion(view, selectedDate, selectedArea?.fid);
    if (window.location.hash === destino) return;
    const cambiaSeccion = leerDireccion().vista !== view;
    window.history[cambiaSeccion ? 'pushState' : 'replaceState'](null, '', destino);
  }, [view, selectedDate, selectedArea]);

  // Botones Atrás/Adelante o una dirección pegada a mano.
  useEffect(() => {
    function alCambiarDireccion() {
      const { vista, fecha, area } = leerDireccion();
      setView(vista);
      if (fecha && dates.includes(fecha)) setSelectedDate(fecha);
      if (area !== null) {
        const encontrada = areas.find((a) => a.fid === area);
        if (encontrada) setSelectedArea(encontrada);
      }
    }
    window.addEventListener('popstate', alCambiarDireccion);
    window.addEventListener('hashchange', alCambiarDireccion);
    return () => {
      window.removeEventListener('popstate', alCambiarDireccion);
      window.removeEventListener('hashchange', alCambiarDireccion);
    };
  }, [dates, areas]);

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
    actua: 'Cuida el arrecife',
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
            puedeVerHistorico={puedeVerHistorico}
          />
          </ViewErrorBoundary>
        );
      case 'resumen':
        return <ViewErrorBoundary><ViewResumen areas={areas} totalDates={dates.length} /></ViewErrorBoundary>;
      case 'actua':
        return <ViewErrorBoundary><ViewActua onNavigate={navigate} /></ViewErrorBoundary>;
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
      <div className="h-screen flex items-center justify-center zona-clara" style={{ background: 'var(--c-fondo)' }}>
        <LoadingState message="Cargando Coraleum..." />
      </div>
    );
  }

  // Contraseña temporal: nada más está disponible hasta cambiarla.
  if (usuario?.debe_cambiar_password) {
    return (
      <div className="zona-clara pantalla-completa">
        <CambioPasswordObligatorio />
      </div>
    );
  }

  // Cuentas sin la autorización vigente (Ley 1581): deben aceptarla primero.
  if (debeAceptarPolitica) {
    return (
      <div className="zona-clara pantalla-completa">
        <AceptarPoliticaObligatorio />
      </div>
    );
  }

  return (
    <div className="flex" data-zona="clara" style={{ height: '100dvh', width: '100vw', overflow: 'hidden', background: '#eef8f7' }}>
      <Sidebar active={view} onNavigate={navigate} collapsed={collapsed} autenticado={autenticado} puedeVerDatos={puedeVerDatos} esAdmin={esAdmin} pendientes={pendientes} />

      <div className="flex-1 flex flex-col min-w-0 overflow-hidden">
        <header
          className="app-header shrink-0 flex items-center gap-3 px-5"
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

        {autenticado && notificacion && (
          <div className="notificacion-sesion shrink-0" role="status">
            <span>{notificacion}</span>
            <button type="button" onClick={() => setNotificacion('')}>Entendido</button>
          </div>
        )}

        {error && puedeVerDatos && VISTAS_DATOS.has(view) && dates.length > 0 && (
          <div className="shrink-0 px-5 py-1.5 text-xs font-mono" style={{ background: 'rgba(255,107,71,0.08)', color: '#ff9b6b', borderBottom: '1px solid rgba(255,107,71,0.15)' }}>
            {error}
          </div>
        )}

        <main
          className={`flex-1 min-h-0 overflow-hidden transition-opacity duration-200 zona-clara`}
          style={{ background: 'linear-gradient(145deg, #eef8f7 0%, #e8f3f2 58%, #f6faf9 100%)' }}
          key={view}
        >
          {view !== 'inicio' && <FondoMarino />}
          {renderVista()}
        </main>
        <AvisoInsignia onNavigate={navigate} />
      </div>
    </div>
  );
}
