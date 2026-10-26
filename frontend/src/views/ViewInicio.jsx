
const BUBBLES = Array.from({ length: 24 }, (_, i) => ({
  left: `${5 + ((i * 37) % 90)}%`,
  size: `${6 + ((i * 11) % 15)}px`,
  delay: `${(i * 0.72) % 8}s`,
  duration: `${7 + ((i * 13) % 8)}s`,
  drift: `${-25 + ((i * 17) % 50)}px`,
  opacity: `${0.16 + ((i * 7) % 22) / 100}`,
}));

export default function ViewInicio({ onNavigate, areasCount = 47, pixelCount = 20, datesCount = 0 }) {
  const stats = [
    { icon:'🪸', value:areasCount, label:'Áreas coralinas' },
    { icon:'◈', value:pixelCount, label:'Píxeles NOAA' },
    { icon:'▣', value:datesCount, label:'Fechas disponibles' },
  ];
  return <div className="home-hero">
    <div className="home-photo" aria-hidden="true" />
    <div className="home-water-tint" />
    <div className="home-vignette" />
    <div className="home-glow home-glow-a" /><div className="home-glow home-glow-b" />
    <div className="bubble-field" aria-hidden="true">
      {BUBBLES.map((bubble, i) => <span key={i} className="bubble" style={{ left:bubble.left, width:bubble.size, height:bubble.size, animationDelay:bubble.delay, animationDuration:bubble.duration, '--drift':bubble.drift, opacity:bubble.opacity }} />)}
    </div>
    <div className="coral-silhouette coral-silhouette-left" aria-hidden="true"><i/><i/><i/><i/><i/></div>
    <div className="coral-silhouette coral-silhouette-right" aria-hidden="true"><i/><i/><i/><i/></div>
    <div className="home-content">
      <div className="home-kicker"><span className="status-dot" />Parque Nacional Natural · Colombia</div>
      <h1 className="home-title">Corales del<br /><span>Rosario</span> <em>&</em> <span>San Bernardo</span></h1>
      <p className="home-lead">Explora biodiversidad, conservación y estrés térmico en el Caribe colombiano. Conecta la información coralina del territorio con observaciones diarias de NOAA Coral Reef Watch.</p>
      <div className="home-actions">
        <button className="primary-action" onClick={() => onNavigate('explorador')}><span>◉</span> Explorar el arrecife <span>→</span></button>
        <button className="secondary-action" onClick={() => onNavigate('indicadores')}>Ver datos científicos</button>
      </div>
      <div className="home-stats">{stats.map(s => <div className="home-stat" key={s.label}><div className="home-stat-icon">{s.icon}</div><div><strong>{s.value}</strong><span>{s.label}</span></div></div>)}</div>
    </div>
  </div>;
}
