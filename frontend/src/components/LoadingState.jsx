export function LoadingState({ message = 'Cargando datos...' }) {
  return (
    <div className="flex flex-col items-center justify-center gap-4 py-16">
      <div className="relative w-10 h-10">
        <div className="absolute inset-0 rounded-full border-2 border-transparent animate-spin" style={{ borderTopColor: '#00c4b4' }} />
        <div className="absolute inset-1 rounded-full border-2 border-transparent animate-spin" style={{ borderBottomColor: 'rgba(0,196,180,0.4)', animationDuration: '1.4s' }} />
      </div>
      <p className="text-sm font-mono" style={{ color: 'rgba(0,196,180,0.6)' }}>{message}</p>
    </div>
  );
}

export function ErrorState({ message = 'No fue posible obtener los datos.' }) {
  return (
    <div className="flex flex-col items-center justify-center gap-3 py-12 text-center">
      <div className="w-10 h-10 rounded-full flex items-center justify-center" style={{ background: 'rgba(255,107,71,0.1)', border: '1px solid rgba(255,107,71,0.3)' }}>
        <svg className="w-5 h-5" fill="none" viewBox="0 0 24 24" stroke="currentColor" style={{ color: '#ff6b47' }}>
          <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 9v2m0 4h.01M21 12a9 9 0 11-18 0 9 9 0 0118 0z" />
        </svg>
      </div>
      <p className="text-sm" style={{ color: 'rgba(255,107,71,0.8)' }}>{message}</p>
    </div>
  );
}

export function EmptyState({ message = 'Sin datos disponibles' }) {
  return (
    <div className="flex flex-col items-center justify-center gap-3 py-12 text-center">
      <div className="w-10 h-10 rounded-full flex items-center justify-center" style={{ background: 'rgba(0,196,180,0.06)', border: '1px solid rgba(0,196,180,0.15)' }}>
        <svg className="w-5 h-5" fill="none" viewBox="0 0 24 24" stroke="currentColor" style={{ color: 'rgba(0,196,180,0.4)' }}>
          <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.5} d="M20 13V6a2 2 0 00-2-2H6a2 2 0 00-2 2v7m16 0v5a2 2 0 01-2 2H6a2 2 0 01-2-2v-5m16 0h-2.586a1 1 0 00-.707.293l-2.414 2.414a1 1 0 01-.707.293h-3.172a1 1 0 01-.707-.293l-2.414-2.414A1 1 0 006.586 13H4" />
        </svg>
      </div>
      <p className="text-sm" style={{ color: 'rgba(168,212,224,0.5)' }}>{message}</p>
    </div>
  );
}
