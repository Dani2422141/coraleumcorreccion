import AnimalMarino from './AnimalesMarinos';

const BANCO = [
  { x: 0, y: 0, s: 26 }, { x: 34, y: -14, s: 20 }, { x: 40, y: 18, s: 22 }, { x: 72, y: 2, s: 18 },
  { x: 76, y: 30, s: 16 }, { x: 104, y: -8, s: 15 }, { x: 14, y: 34, s: 17 },
];

/**
 * Capa decorativa de las páginas claras: luz del agua, un banco de peces,
 * una tortuga y una raya que nadan muy despacio, y la silueta del arrecife.
 * Es tenue a propósito (no compite con el texto) y no recibe clics.
 */
export default function FondoMarino() {
  return (
    <div className="fondo-marino" aria-hidden="true">
      <div className="fm-luz" />
      <div className="fm-banco">
        {BANCO.map((p, i) => (
          <span key={i} style={{ left: p.x, top: p.y, '--d': `${i * 0.6}s` }}>
            <AnimalMarino nombre="pez" size={p.s} />
          </span>
        ))}
      </div>
      <div className="fm-tortuga"><AnimalMarino nombre="tortuga" size={110} /></div>
      <div className="fm-raya"><AnimalMarino nombre="raya" size={90} /></div>
      <svg className="fm-arrecife" viewBox="0 0 1200 120" preserveAspectRatio="none">
        <path d="M0 120V92c60-12 110 8 170-4s90-26 160-12 110 20 180 6 120-24 190-10 110 18 170 8 100-14 160-6 60 8 70 8v38Z" />
        <g fill="none" strokeLinecap="round" strokeWidth="10">
          <path d="M120 96V70m0 0-12-14V44m12 26 14-16V40" />
          <path d="M420 92V62m0 0-16-16V30m16 32 16-20V26" />
          <path d="M760 94V66m0 0-14-12V38m14 28 14-18V34" />
          <path d="M1060 92V64m0 0-12-14V36m12 28 14-16V30" />
        </g>
        <g>
          <ellipse cx="260" cy="92" rx="40" ry="24" />
          <ellipse cx="600" cy="94" rx="34" ry="20" />
          <ellipse cx="920" cy="92" rx="44" ry="26" />
        </g>
      </svg>
    </div>
  );
}
