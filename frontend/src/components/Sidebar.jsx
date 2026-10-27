import AnimalMarino from './AnimalesMarinos';
const NAV_ITEMS = [
  {
    id: 'inicio', label: 'Inicio',
    icon: <AnimalMarino nombre="tortuga" size={20} />,
  },
  {
    id: 'corales', label: 'Conoce los Corales', group: 'DESCUBRIR',
    icon: <AnimalMarino nombre="pezLoro" size={20} />,
  },
  {
    id: 'estres', label: 'Estrés Térmico', group: 'COMPRENDER',
    icon: <AnimalMarino nombre="caballito" size={20} />,
  },
  {
    id: 'indicadores', label: 'Indicadores NOAA', group: 'ENTENDER',
    icon: <AnimalMarino nombre="raya" size={20} />,
  },
  {
    id: 'actua', label: 'Cuida el arrecife', group: 'ACTUAR',
    icon: <AnimalMarino nombre="estrella" size={20} />,
  },
  {
    id: 'explorador', label: 'Explorador Térmico', group: 'EXPLORAR', protegido: true,
    icon: <AnimalMarino nombre="pulpo" size={20} />,
  },
  {
    id: 'resumen', label: 'Resumen', protegido: true,
    icon: <AnimalMarino nombre="banco" size={20} />,
  },
  {
    id: 'metodologia', label: 'Metodología',
    icon: <AnimalMarino nombre="cangrejo" size={20} />,
  },
];


const ITEM_CUENTA = {
  id: 'cuenta', label: 'Mi cuenta', group: 'CUENTA',
  icon: <AnimalMarino nombre="concha" size={20} />,
};

const ITEM_ADMIN = {
  id: 'admin', label: 'Administración', group: 'CUENTA',
  icon: <AnimalMarino nombre="tiburon" size={20} />,
};

const ITEM_ACCESO = {
  id: 'acceso', label: 'Iniciar sesión', group: 'CUENTA',
  icon: <AnimalMarino nombre="concha" size={20} />,
};

export default function Sidebar({ active, onNavigate, collapsed, autenticado = false, puedeVerDatos = false, esAdmin = false, pendientes = 0 }) {
  let lastGroup = '';
  const items = [
    ...NAV_ITEMS,
    ...(autenticado ? [ITEM_CUENTA] : [ITEM_ACCESO]),
    ...(esAdmin ? [ITEM_ADMIN] : []),
  ];

  return (
    <aside
      data-collapsed={collapsed ? "true" : "false"}
      aria-label="Navegación principal"
      className="h-full flex flex-col shrink-0 transition-all duration-300"
      style={{
        width: collapsed ? '64px' : '214px',
        background: 'rgba(13,45,55,.60)',
        borderRight: '1px solid rgba(218,246,242,.09)',
        backdropFilter: 'blur(24px) saturate(125%)',
      }}
    >
      {/* Logo */}
      <div className="px-4 py-5 flex items-center gap-3 shrink-0"
        style={{ borderBottom: '1px solid rgba(35,113,122,0.10)' }}>
        <div className="w-7 h-7 rounded-full flex items-center justify-center shrink-0"
          style={{ background: 'linear-gradient(135deg, #45d5ca, #82e9df)' }}>
          <svg viewBox="0 0 24 24" fill="none" className="w-3.5 h-3.5">
            <circle cx="12" cy="12" r="9" fill="rgba(255,255,255,0.75)" />
            <path d="M8 14c0-2.2 1.8-4 4-4s4 1.8 4 4" stroke="#0d6265" strokeWidth="1.5" strokeLinecap="round" />
            <circle cx="12" cy="10" r="1.5" fill="#0d6265" />
          </svg>
        </div>
        {!collapsed && (
          <div>
            <div className="font-semibold text-sm leading-tight text-gradient-ocean">PNN Corales</div>
            <div className="text-xs leading-tight" style={{ color: 'rgba(216,238,236,0.72)', fontSize: '10px' }}>del Rosario & San Bernardo</div>
          </div>
        )}
      </div>

      {/* Nav items */}
      <nav className="flex-1 overflow-y-auto py-3 px-2">
        {items.map((item) => {
          const showGroup = !collapsed && item.group && item.group !== lastGroup;
          if (item.group) lastGroup = item.group;
          const isActive = active === item.id || (item.id === 'acceso' && active === 'registro');
          const bloqueado = item.protegido && !puedeVerDatos;

          return (
            <div key={item.id}>
              {showGroup && (
                <div className="px-3 pt-3 pb-1">
                  <span className="text-xs tracking-widest font-medium"
                    style={{ color: 'rgba(143,226,217,0.78)', fontSize: '9px', letterSpacing: '0.14em' }}>
                    {item.group}
                  </span>
                </div>
              )}
              <button
                onClick={() => onNavigate(item.id)}
                title={collapsed ? item.label : bloqueado ? 'Requiere cuenta de investigador' : undefined}
                className={`nav-item w-full flex items-center gap-3 px-3 py-2.5 rounded-xl mb-0.5 transition-all duration-200 text-left ${isActive ? 'nav-item-active' : ''}`}
                style={{ color: isActive ? '#67e8dc' : undefined }}
                onMouseEnter={(e) => { e.currentTarget.classList.add('nav-item-hover'); }}
                onMouseLeave={(e) => { e.currentTarget.classList.remove('nav-item-hover'); }}
              >
                <span className="shrink-0">{item.icon}</span>
                {!collapsed && (
                  <span className="text-xs font-medium leading-tight truncate">{item.label}</span>
                )}
                {!collapsed && bloqueado && <span className="nav-candado" aria-label="Requiere acceso de investigador">🔒</span>}
                {!collapsed && item.id === 'admin' && pendientes > 0 && <span className="nav-contador" aria-label={`${pendientes} solicitudes pendientes`}>{pendientes}</span>}
                {!collapsed && isActive && !bloqueado && !(item.id === 'admin' && pendientes > 0) && (
                  <div className="ml-auto w-1 h-1 rounded-full shrink-0" style={{ background: '#0aa6a0' }} />
                )}
              </button>
            </div>
          );
        })}
      </nav>

      <div className="aside-arrecife" aria-hidden="true">
        <svg viewBox="0 0 214 150" preserveAspectRatio="xMidYMax slice" fill="currentColor">
          <path d="M0 150v-26c18-6 34 2 52-2s30-12 52-6 34 10 56 4 36-8 54-4v34Z" />
          <g fill="none" stroke="currentColor" strokeWidth="7" strokeLinecap="round">
            <path d="M40 128v-22m0 0-10-12V82m10 24 10-14V78" />
            <path d="M150 126v-26m0 0-12-12V72m12 28 12-16V68m-24 20-8-8" />
          </g>
          <ellipse cx="96" cy="126" rx="20" ry="13" />
          <ellipse cx="196" cy="128" rx="16" ry="11" />
          <g fill="none" stroke="currentColor" strokeWidth="3.5" strokeLinecap="round">
            <path d="M12 140c-5-12 5-18 0-32M20 140c4-11-4-18 2-30" />
          </g>
        </svg>
      </div>

      {/* Footer info */}
      {!collapsed && (
        <div className="px-4 py-3 shrink-0" style={{ borderTop: '1px solid rgba(35,113,122,0.10)' }}>
          <div className="text-xs leading-tight mb-0.5" style={{ color: 'rgba(143,226,217,0.9)' }}>NOAA Coral Reef Watch</div>
          <div className="text-xs" style={{ color: 'rgba(216,238,236,0.7)', fontSize: '10px' }}>
            47 áreas · 20 píxeles · 5 km
          </div>
          <button type="button" className="enlace" style={{ fontSize: '10.5px', marginTop: 6 }} onClick={() => onNavigate('privacidad')}>
            Política de datos personales
          </button>
        </div>
      )}
    </aside>
  );
}
