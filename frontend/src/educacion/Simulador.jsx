import { useEffect, useMemo, useState } from 'react';
import { NIVELES, nivelNoaa, numero } from './niveles';
import { ganarInsignia } from './progreso';
import imgSano from '../assets/arrecife/sim-sano.webp';
import imgPalido from '../assets/arrecife/sim-palido.webp';
import imgBlanqueado from '../assets/arrecife/sim-blanqueado.webp';
import imgAlgas from '../assets/arrecife/sim-algas.webp';

// Etapas de la ilustración: el coral pierde color, se blanquea (y los peces se
// van) y finalmente se cubre de algas. Las capas se funden según el DHW.
const ETAPAS = [
  { src: imgSano, opacidad: () => 1 },
  { src: imgPalido, opacidad: (d) => clamp((d - 2) / 4) },
  { src: imgBlanqueado, opacidad: (d) => clamp((d - 6) / 3) },
  { src: imgAlgas, opacidad: (d) => clamp((d - 12) / 6) },
];

function clamp(x) {
  return Math.min(1, Math.max(0, x));
}

const ESCENARIOS = [
  { nombre: 'Un verano normal', calor: 0.6, semanas: 8 },
  { nombre: 'Una ola de calor', calor: 1.4, semanas: 4 },
  { nombre: 'Lo que vivió el parque en 2026', calor: 1.4, semanas: 6 },
  { nombre: 'Ola de calor extrema', calor: 2.5, semanas: 9 },
];

export function CoralSimulado({ dhw, calor }) {
  const descripcion = dhw >= 12
    ? 'Coral muerto, cubierto de algas, y casi sin animales.'
    : dhw >= 8
      ? 'Coral blanqueado; los peces y la tortuga se fueron.'
      : dhw >= 4
        ? 'Coral pálido, perdiendo su color.'
        : 'Coral sano, color café dorado, rodeado de peces, una tortuga y otros animales.';
  return (
    <div className="edu-sim-imagen" role="img" aria-label={descripcion}>
      {ETAPAS.map((e, i) => (
        <img key={i} src={e.src} alt="" style={{ opacity: e.opacidad(dhw) }} draggable="false" />
      ))}
      <div className="edu-sim-calor" style={{ opacity: Math.min(calor / 3, 1) * 0.55 }} />
    </div>
  );
}

export default function Simulador({ compacto = false }) {
  const [calor, setCalor] = useState(1.4);
  const [semanas, setSemanas] = useState(2);

  const hotspot = calor;
  const acumula = hotspot >= 1;
  const dhw = acumula ? Math.round(hotspot * semanas * 10) / 10 : 0;
  const nivel = nivelNoaa(hotspot, dhw);
  const indice = NIVELES.indexOf(nivel);

  useEffect(() => {
    if (indice >= NIVELES.findIndex((n) => n.clave === 'alerta_2')) ganarInsignia('simulador');
  }, [indice]);

  const posicion = useMemo(() => `${Math.min(dhw / 20, 1) * 100}%`, [dhw]);

  const escalas = NIVELES.filter((n) => n.desde !== null);

  return (
    <section className={`edu-sim ${compacto ? 'is-compacto' : ''}`} aria-labelledby="edu-sim-titulo">
      <div className="edu-sim-cabecera">
        <h2 id="edu-sim-titulo" className="edu-titulo-seccion">Simula el blanqueamiento</h2>
        <p>
          El coral no se blanquea por un día caluroso, sino por el calor que se acumula durante semanas.
          Mueve los controles y mira qué le pasa.
        </p>
      </div>

      <div className="edu-sim-cuerpo">
        <div className="edu-sim-escena" style={{ '--nivel': nivel.color }}>
          <CoralSimulado dhw={dhw} calor={calor} />
          <div className="edu-sim-chips" aria-hidden="true">
            <span>Agua +{numero(calor)} °C</span>
            <span>{semanas} {semanas === 1 ? 'semana' : 'semanas'}</span>
            <span>DHW {numero(dhw)}</span>
          </div>
          <div className="edu-sim-estado" aria-live="polite">
            <span className="edu-sim-pastilla" style={{ background: nivel.color, color: indice >= 5 ? '#fff4f2' : '#1b1410' }}>{nivel.nombre}</span>
            <p>{nivel.efecto}</p>
          </div>
        </div>

        <div className="edu-sim-controles">
          <div className="edu-sim-escenarios" role="group" aria-label="Escenarios">
            {ESCENARIOS.map((e) => {
              const activo = e.calor === calor && e.semanas === semanas;
              return (
                <button key={e.nombre} type="button" className={activo ? 'is-activo' : ''} aria-pressed={activo}
                  onClick={() => { setCalor(e.calor); setSemanas(e.semanas); }}>
                  {e.nombre}
                </button>
              );
            })}
          </div>

          <label className="edu-control">
            <span className="edu-control-titulo">
              Grados por encima del verano más caliente normal
              <b>+{numero(calor)} °C</b>
            </span>
            <input type="range" min="0" max="3" step="0.1" value={calor} onChange={(e) => setCalor(Number(e.target.value))}
              style={{ '--avance': `${(calor / 3) * 100}%` }} />
            <small>{acumula ? 'Suficiente para estresar al coral: el calor empieza a acumularse.' : 'Por debajo de 1 °C extra el coral lo tolera y el calor no se acumula.'}</small>
          </label>

          <label className="edu-control">
            <span className="edu-control-titulo">
              Semanas con el agua así de caliente
              <b>{semanas} {semanas === 1 ? 'semana' : 'semanas'}</b>
            </span>
            <input type="range" min="0" max="12" step="1" value={semanas} onChange={(e) => setSemanas(Number(e.target.value))}
              style={{ '--avance': `${(semanas / 12) * 100}%` }} />
            <small>NOAA suma el calor de las últimas 12 semanas.</small>
          </label>

          <div className="edu-sim-resultado">
            <div className="edu-sim-cuenta">
              <span>Calor acumulado (DHW)</span>
              <strong className="edu-display">{numero(dhw)}<small> °C-semana</small></strong>
              <em>{acumula ? `${numero(calor)} °C × ${semanas} ${semanas === 1 ? 'semana' : 'semanas'}` : 'Menos de 1 °C extra: no suma'}</em>
            </div>
            <div className="edu-medidor" aria-hidden="true">
              <div className="edu-medidor-barra">
                {escalas.map((n, i) => {
                  const hasta = escalas[i + 1]?.desde ?? 24;
                  return <span key={n.clave} style={{ background: n.color, flex: Math.min(hasta, 20) - Math.min(n.desde, 20) || 0.0001 }} />;
                })}
              </div>
              <i className="edu-medidor-marca" style={{ left: posicion }} />
              <div className="edu-medidor-numeros"><span>0</span><span>4</span><span>8</span><span>12</span><span>16</span><span>20+</span></div>
            </div>
          </div>
        </div>
      </div>
    </section>
  );
}
