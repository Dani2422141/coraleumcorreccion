import { useEffect, useMemo, useRef, useState } from 'react';
import { getEstadoParque } from '../data/api';
import { NIVELES, NIVEL_POR_CLAVE, fechaCorta, fechaLarga, numero } from './niveles';
import { ganarInsignia } from './progreso';
import Icono, { GlifoCoral } from './Iconos';

/** Frase principal con el estado del parque, escrita para cualquier persona. */
function frase(datos) {
  const n = datos.niveles;
  const alertas = ['alerta_1', 'alerta_2', 'alerta_3', 'alerta_4', 'alerta_5'].reduce((s, k) => s + (n[k] || 0), 0);
  const graves = ['alerta_2', 'alerta_3', 'alerta_4', 'alerta_5'].reduce((s, k) => s + (n[k] || 0), 0);
  if (!alertas) {
    return { cifra: datos.total_areas, texto: `áreas coralinas del parque están hoy fuera de alerta de blanqueamiento.`, cola: '' };
  }
  if (alertas === datos.total_areas) {
    return {
      cifra: `Las ${alertas}`,
      texto: 'áreas coralinas del parque están en alerta de blanqueamiento.',
      cola: graves ? `${graves} ya están en nivel 2 o superior, donde se espera blanqueamiento severo y muerte de los corales más sensibles.` : '',
    };
  }
  return {
    cifra: alertas,
    texto: `de las ${datos.total_areas} áreas coralinas del parque están en alerta de blanqueamiento.`,
    cola: graves ? `${graves} ya están en nivel 2 o superior, donde se espera blanqueamiento severo y muerte de los corales más sensibles.` : '',
  };
}

function Grafica({ serie }) {
  const ancho = 760;
  const alto = 230;
  const m = { izq: 34, der: 92, arr: 14, aba: 30 };
  const maxY = Math.max(12, Math.ceil(Math.max(...serie.map((p) => p.dhw_maximo)) / 4) * 4);
  const x = (i) => m.izq + (i / Math.max(serie.length - 1, 1)) * (ancho - m.izq - m.der);
  const y = (v) => m.arr + (1 - v / maxY) * (alto - m.arr - m.aba);
  const linea = (clave) => serie.map((p, i) => `${i ? 'L' : 'M'}${x(i).toFixed(1)},${y(p[clave]).toFixed(1)}`).join(' ');
  const area = `${linea('dhw_maximo')} L${x(serie.length - 1)},${y(0)} L${x(0)},${y(0)} Z`;
  const bandas = [
    { desde: 0, hasta: 4, nivel: 'advertencia' },
    { desde: 4, hasta: 8, nivel: 'alerta_1' },
    { desde: 8, hasta: 12, nivel: 'alerta_2' },
    { desde: 12, hasta: 16, nivel: 'alerta_3' },
    { desde: 16, hasta: 20, nivel: 'alerta_4' },
  ].filter((b) => b.desde < maxY);
  const ultimo = serie[serie.length - 1];
  const marcas = [0, Math.floor((serie.length - 1) / 2), serie.length - 1];

  return (
    <svg className="edu-grafica" viewBox={`0 0 ${ancho} ${alto}`} role="img"
      aria-label={`Calor acumulado en el parque: de ${numero(serie[0].dhw_promedio)} a ${numero(ultimo.dhw_promedio)} °C-semana en promedio.`}>
      {bandas.map((b) => (
        <g key={b.nivel}>
          <rect x={m.izq} width={ancho - m.izq - m.der} y={y(Math.min(b.hasta, maxY))} height={y(b.desde) - y(Math.min(b.hasta, maxY))}
            fill={NIVEL_POR_CLAVE[b.nivel].color} opacity={0.09} />
          {b.desde > 0 && <line x1={m.izq} x2={ancho - m.der} y1={y(b.desde)} y2={y(b.desde)} stroke={NIVEL_POR_CLAVE[b.nivel].color} strokeOpacity=".45" strokeDasharray="3 5" />}
          {b.desde > 0 && <text className="edu-grafica-umbral" x={ancho - m.der - 8} y={(y(b.desde) + y(Math.min(b.hasta, maxY))) / 2 + 4} textAnchor="end" style={{ fill: NIVEL_POR_CLAVE[b.nivel].color }}>{NIVEL_POR_CLAVE[b.nivel].corto}</text>}
        </g>
      ))}
      {[0, 4, 8, 12, 16].filter((v) => v <= maxY).map((v) => (
        <text key={v} className="edu-grafica-eje" x={m.izq - 8} y={y(v) + 4} textAnchor="end">{v}</text>
      ))}
      {marcas.map((i) => (
        <text key={i} className="edu-grafica-eje" x={x(i)} y={alto - 8} textAnchor={i === 0 ? 'start' : i === serie.length - 1 ? 'end' : 'middle'}>{fechaCorta(serie[i].fecha)}</text>
      ))}
      <path d={area} fill="url(#edu-degradado)" opacity=".5" />
      <defs>
        <linearGradient id="edu-degradado" x1="0" x2="0" y1="0" y2="1">
          <stop offset="0" stopColor="#ef7f45" stopOpacity=".55" />
          <stop offset="1" stopColor="#ef7f45" stopOpacity="0" />
        </linearGradient>
      </defs>
      <path d={linea('dhw_maximo')} fill="none" stroke="#ff9b7a" strokeWidth="2" strokeDasharray="5 4" />
      <path d={linea('dhw_promedio')} fill="none" stroke="#f4fbf9" strokeWidth="3" strokeLinejoin="round" />
      <circle cx={x(serie.length - 1)} cy={y(ultimo.dhw_promedio)} r="5" fill="#f4fbf9" />
      <circle cx={x(serie.length - 1)} cy={y(ultimo.dhw_maximo)} r="4" fill="#ff9b7a" />
      <text className="edu-grafica-dato" x={x(serie.length - 1) + 10} y={y(ultimo.dhw_promedio) + 5}>Promedio {numero(ultimo.dhw_promedio)}</text>
      <text className="edu-grafica-dato edu-grafica-dato-max" x={x(serie.length - 1) + 10} y={y(ultimo.dhw_maximo) + 5}>Máximo {numero(ultimo.dhw_maximo)}</text>
    </svg>
  );
}

export default function ParqueHoy({ onNavigate }) {
  const [datos, setDatos] = useState(null);
  const [error, setError] = useState(false);
  const [nivelFoco, setNivelFoco] = useState(null);
  const ref = useRef(null);

  useEffect(() => {
    getEstadoParque().then(setDatos).catch(() => setError(true));
  }, []);

  // La insignia se gana al ver la sección, no solo al cargar la página.
  useEffect(() => {
    if (!datos?.disponible || !ref.current || typeof IntersectionObserver === 'undefined') return undefined;
    const observador = new IntersectionObserver((entradas) => {
      if (entradas.some((e) => e.isIntersecting)) {
        ganarInsignia('parque');
        observador.disconnect();
      }
    }, { threshold: 0.35 });
    observador.observe(ref.current);
    return () => observador.disconnect();
  }, [datos]);

  const teselas = useMemo(() => {
    if (!datos?.disponible) return [];
    return [...NIVELES].reverse().flatMap((nivel) => Array.from({ length: datos.niveles[nivel.clave] || 0 }, () => nivel));
  }, [datos]);

  if (error || (datos && !datos.disponible)) return null;
  if (!datos) return <section className="edu-parque edu-parque-cargando" aria-busy="true" />;

  const { cifra, texto, cola } = frase(datos);
  const serie = datos.serie || [];
  const inicio = serie[0];
  const presentes = NIVELES.filter((n) => datos.niveles[n.clave]);

  return (
    <section className="edu-parque" ref={ref} aria-labelledby="edu-parque-titulo">
      <div className="edu-parque-marco">
        <p className="edu-parque-fecha">
          <span className="edu-punto-vivo" aria-hidden="true" />
          Medición satelital de NOAA Coral Reef Watch del {fechaLarga(datos.fecha)}
        </p>

        <div className="edu-parque-principal">
          <h2 id="edu-parque-titulo" className="edu-parque-frase">
            <span className="edu-parque-cifra">{cifra}</span> {texto}
          </h2>
          <div className="edu-mosaico-bloque">
            <div className="edu-mosaico" role="img" aria-label={presentes.map((n) => `${datos.niveles[n.clave]} en ${n.nombre}`).join(', ')}>
              {teselas.map((nivel, i) => (
                <span
                  key={i}
                  className={`edu-tesela ${nivelFoco && nivelFoco !== nivel.clave ? 'is-apagada' : ''}`}
                  style={{ '--i': i, '--color': nivel.color }}
                  title={nivel.nombre}
                >
                  <GlifoCoral color={nivel.color} size={26} />
                </span>
              ))}
            </div>
            <ul className="edu-leyenda">
              {presentes.map((n) => (
                <li key={n.clave} onMouseEnter={() => setNivelFoco(n.clave)} onMouseLeave={() => setNivelFoco(null)}>
                  <span style={{ background: n.color }} />
                  <b>{datos.niveles[n.clave]}</b> {n.nombre}
                </li>
              ))}
            </ul>
          </div>
        </div>
        {cola && <p className="edu-parque-cola">{cola}</p>}

        {serie.length > 1 && (
          <figure className="edu-parque-grafica">
            <figcaption>
              <strong>El calor se acumula semana a semana.</strong> En {serie.length} días de mediciones, el calor acumulado
              (DHW) en el parque pasó de {numero(inicio.dhw_promedio)} a {numero(serie[serie.length - 1].dhw_promedio)} °C-semana
              en promedio. A partir de 8, NOAA espera blanqueamiento severo.
            </figcaption>
            <Grafica serie={serie} />
          </figure>
        )}

        <div className="edu-parque-acciones">
          <button type="button" className="edu-boton edu-boton-principal" onClick={() => onNavigate('estres')}>
            <Icono nombre="termometro" size={18} /> Simula el blanqueamiento
          </button>
          <button type="button" className="edu-boton" onClick={() => onNavigate('actua')}>
            <Icono nombre="escudo" size={18} /> Qué puedo hacer yo
          </button>
        </div>
        <p className="edu-nota">
            Niveles según la escala de alertas de NOAA Coral Reef Watch, calculados con el calor acumulado de cada área.
            El detalle por área está en el Explorador Térmico, para investigadores.
        </p>
      </div>
    </section>
  );
}
