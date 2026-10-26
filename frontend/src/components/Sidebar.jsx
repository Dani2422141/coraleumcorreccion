const NAV_ITEMS = [
  {
    id: 'inicio', label: 'Inicio',
    icon: (
      <svg viewBox="0 0 20 20" fill="currentColor" className="w-4 h-4">
        <path d="M10.707 2.293a1 1 0 00-1.414 0l-7 7a1 1 0 001.414 1.414L4 10.414V17a1 1 0 001 1h2a1 1 0 001-1v-2a1 1 0 011-1h2a1 1 0 011 1v2a1 1 0 001 1h2a1 1 0 001-1v-6.586l.293.293a1 1 0 001.414-1.414l-7-7z" />
      </svg>
    ),
  },
  {
    id: 'corales', label: 'Conoce los Corales', group: 'DESCUBRIR',
    icon: (
      <svg viewBox="0 0 20 20" fill="none" stroke="currentColor" className="w-4 h-4">
        <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.5} d="M5 3v4M3 5h4M6 17v4m-2-2h4m5-16l2.286 6.857L21 12l-5.714 2.143L13 21l-2.286-6.857L5 12l5.714-2.143L13 3z" />
      </svg>
    ),
  },
  {
    id: 'estres', label: 'Estrés Térmico', group: 'COMPRENDER',
    icon: (
      <svg viewBox="0 0 20 20" fill="none" stroke="currentColor" className="w-4 h-4">
        <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.5} d="M13 10V3L4 14h7v7l9-11h-7z" />
      </svg>
    ),
  },
  {
    id: 'indicadores', label: 'Indicadores NOAA', group: 'ENTENDER',
    icon: (
      <svg viewBox="0 0 20 20" fill="none" stroke="currentColor" className="w-4 h-4">
        <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.5} d="M9 19v-6a2 2 0 00-2-2H5a2 2 0 00-2 2v6a2 2 0 002 2h2a2 2 0 002-2zm0 0V9a2 2 0 012-2h2a2 2 0 012 2v10m-6 0a2 2 0 002 2h2a2 2 0 002-2m0 0V5a2 2 0 012-2h2a2 2 0 012 2v14a2 2 0 01-2 2h-2a2 2 0 01-2-2z" />
      </svg>
    ),
  },
  {
    id: 'explorador', label: 'Explorador Térmico', group: 'EXPLORAR',
    icon: (
      <svg viewBox="0 0 20 20" fill="none" stroke="currentColor" className="w-4 h-4">
        <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.5} d="M9 20l-5.447-2.724A1 1 0 013 16.382V5.618a1 1 0 011.447-.894L9 7m0 13l6-3m-6 3V7m6 10l4.553 2.276A1 1 0 0021 18.382V7.618a1 1 0 00-.553-.894L15 4m0 13V4m0 0L9 7" />
      </svg>
    ),
  },
  {
    id: 'resumen', label: 'Resumen',
    icon: (
      <svg viewBox="0 0 20 20" fill="none" stroke="currentColor" className="w-4 h-4">
        <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.5} d="M11 3.055A9.001 9.001 0 1020.945 13H11V3.055z" />
        <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.5} d="M20.488 9H15V3.512A9.025 9.025 0 0120.488 9z" />
      </svg>
    ),
  },
  {
    id: 'metodologia', label: 'Metodología',
    icon: (
      <svg viewBox="0 0 20 20" fill="none" stroke="currentColor" className="w-4 h-4">
        <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.5} d="M19.428 15.428a2 2 0 00-1.022-.547l-2.387-.477a6 6 0 00-3.86.517l-.318.158a6 6 0 01-3.86.517L6.05 15.21a2 2 0 00-1.806.547M8 4h8l-1 1v5.172a2 2 0 00.586 1.414l5 5c1.26 1.26.367 3.414-1.415 3.414H4.828c-1.782 0-2.674-2.154-1.414-3.414l5-5A2 2 0 009 10.172V5L8 4z" />
      </svg>
    ),
  },
];


export default function Sidebar({ active, onNavigate, collapsed }) {
  let lastGroup = '';

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
            <div className="text-xs leading-tight" style={{ color: 'rgba(57,91,101,0.68)', fontSize: '10px' }}>del Rosario & San Bernardo</div>
          </div>
        )}
      </div>

      {/* Nav items */}
      <nav className="flex-1 overflow-y-auto py-3 px-2">
        {NAV_ITEMS.map((item) => {
          const showGroup = !collapsed && item.group && item.group !== lastGroup;
          if (item.group) lastGroup = item.group;
          const isActive = active === item.id;

          return (
            <div key={item.id}>
              {showGroup && (
                <div className="px-3 pt-3 pb-1">
                  <span className="text-xs tracking-widest font-medium"
                    style={{ color: 'rgba(10,143,139,0.62)', fontSize: '9px', letterSpacing: '0.14em' }}>
                    {item.group}
                  </span>
                </div>
              )}
              <button
                onClick={() => onNavigate(item.id)}
                title={collapsed ? item.label : undefined}
                className={`nav-item w-full flex items-center gap-3 px-3 py-2.5 rounded-xl mb-0.5 transition-all duration-200 text-left ${isActive ? 'nav-item-active' : ''}`}
                style={{ color: isActive ? '#67e8dc' : undefined }}
                onMouseEnter={(e) => { e.currentTarget.classList.add('nav-item-hover'); }}
                onMouseLeave={(e) => { e.currentTarget.classList.remove('nav-item-hover'); }}
              >
                <span className="shrink-0">{item.icon}</span>
                {!collapsed && (
                  <span className="text-xs font-medium leading-tight truncate">{item.label}</span>
                )}
                {!collapsed && isActive && (
                  <div className="ml-auto w-1 h-1 rounded-full shrink-0" style={{ background: '#0aa6a0' }} />
                )}
              </button>
            </div>
          );
        })}
      </nav>

      {/* Footer info */}
      {!collapsed && (
        <div className="px-4 py-3 shrink-0" style={{ borderTop: '1px solid rgba(35,113,122,0.10)' }}>
          <div className="text-xs leading-tight mb-0.5" style={{ color: 'rgba(10,143,139,0.70)' }}>NOAA Coral Reef Watch</div>
          <div className="text-xs" style={{ color: 'rgba(57,91,101,0.62)', fontSize: '10px' }}>
            47 áreas · 20 píxeles · 5 km
          </div>
        </div>
      )}
    </aside>
  );
}
