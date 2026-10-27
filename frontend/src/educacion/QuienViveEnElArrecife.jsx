import { useState } from 'react';
import AnimalMarino from '../components/AnimalesMarinos';
import imgVivo from '../assets/arrecife/arrecife-vivo.webp';
import imgMuerto from '../assets/arrecife/arrecife-muerto.webp';

// Animales del Caribe que dependen del arrecife. Los datos específicos llevan fuente.
const ANIMALES = [
  {
    id: 'carey', icono: 'tortuga', color: '#b07a2e', nombre: 'Tortuga carey', cientifico: 'Eretmochelys imbricata',
    vive: 'Se alimenta sobre todo de esponjas que crecen en el arrecife; su pico estrecho alcanza las grietas.',
    sin: 'Pierde su principal fuente de alimento. Ya está en peligro crítico de extinción.',
    pos: { x: 14, y: 22 },
  },
  {
    id: 'loro', icono: 'pezLoro', color: '#139a91', nombre: 'Pez loro', cientifico: 'Familia Scaridae',
    vive: 'Raspa las algas que cubren el coral y produce arena blanca: un solo pez puede generar hasta 350 libras.',
    sin: 'Sin coral donde pastar, se va; las algas ganan terreno y al coral le cuesta más recuperarse.',
    pos: { x: 70, y: 16 },
  },
  {
    id: 'langosta', icono: 'langosta', color: '#c9572a', nombre: 'Langosta espinosa', cientifico: 'Panulirus argus',
    vive: 'Pasa el día escondida en las grietas del arrecife y sale de noche a buscar alimento.',
    sin: 'Se queda sin escondites; también se pierde una pesca de la que viven familias de la región.',
    pos: { x: 80, y: 66 },
  },
  {
    id: 'caballito', icono: 'caballito', color: '#c98a1c', nombre: 'Caballito de mar', cientifico: 'Hippocampus reidi',
    vive: 'Se sujeta con la cola a corales, esponjas y pastos marinos para que la corriente no lo arrastre.',
    sin: 'No tiene dónde anclarse ni esconderse de sus depredadores.',
    pos: { x: 8, y: 60 },
  },
  {
    id: 'cirujano', icono: 'pezCirujano', color: '#2f6fc4', nombre: 'Pez cirujano azul', cientifico: 'Acanthurus coeruleus',
    vive: 'Pasa el día pastando algas, y así deja espacio libre para que se fijen corales nuevos.',
    sin: 'Pierde su zona de alimentación y con él se va uno de los jardineros del arrecife.',
    pos: { x: 44, y: 8 },
  },
  {
    id: 'pulpo', icono: 'pulpo', color: '#b4466f', nombre: 'Pulpo de arrecife', cientifico: 'Octopus briareus',
    vive: 'Usa las grietas del arrecife como guarida y cambia de color para camuflarse entre el coral.',
    sin: 'Pierde su guarida, y su camuflaje deja de servirle sobre un fondo sin vida.',
    pos: { x: 58, y: 70 },
  },
];

export default function QuienViveEnElArrecife() {
  const [sano, setSano] = useState(true);

  return (
    <section className="eco" aria-labelledby="eco-titulo">
      <div className="eco-cabecera">
        <div>
          <h2 id="eco-titulo" className="edu-titulo-seccion">Quién vive gracias al arrecife</h2>
          <p>
            Los arrecifes ocupan apenas el 0,1 % del fondo marino, pero hasta el 25 % de los animales marinos dependen
            de ellos para sobrevivir (<a href="https://ocean.si.edu/ecosystems/coral-reefs/coral-comeback" target="_blank" rel="noreferrer">Smithsonian</a>).
            Cuando el coral muere, no se pierde una especie: se pierde un barrio entero.
          </p>
        </div>
        <div className="eco-interruptor" role="group" aria-label="Estado del arrecife">
          <button type="button" aria-pressed={sano} className={sano ? 'is-activo' : ''} onClick={() => setSano(true)}>Arrecife vivo</button>
          <button type="button" aria-pressed={!sano} className={!sano ? 'is-activo is-muerto' : ''} onClick={() => setSano(false)}>Arrecife muerto</button>
        </div>
      </div>

      <div className={`eco-escena ${sano ? '' : 'is-muerto'}`} aria-live="polite">
        {/* Las dos ilustraciones se superponen y se cruzan al cambiar de estado. */}
        <img className="eco-imagen eco-imagen-vivo" src={imgVivo} alt="Arrecife vivo y lleno de color, con peces, tortuga, rayas y corales." />
        <img className="eco-imagen eco-imagen-muerto" src={imgMuerto} alt="El mismo arrecife muerto: corales blancos cubiertos de algas y casi sin animales." />
        <p className="eco-escena-texto">
          {sano
            ? 'Un arrecife vivo es refugio, alimento y guardería para cientos de especies.'
            : 'Sin coral vivo, el arrecife se cubre de algas y los animales se van o desaparecen.'}
        </p>
      </div>

      <ul className="eco-lista">
        {ANIMALES.map((a) => (
          <li key={a.id} className={`eco-tarjeta ${sano ? '' : 'is-muerto'}`}>
            <span className="eco-tarjeta-icono" style={{ color: a.color, background: `${a.color}17` }}>
              <AnimalMarino nombre={a.icono} size={34} />
            </span>
            <div>
              <strong>{a.nombre}</strong>
              <em>{a.cientifico}</em>
              <p>{sano ? a.vive : a.sin}</p>
            </div>
          </li>
        ))}
      </ul>
      <p className="eco-fuentes">
        Fuentes: <a href="https://www.cccturtle.org/wp-content/uploads/2024/10/hawksbill-spanish.pdf" target="_blank" rel="noreferrer">Sea Turtle Conservancy (tortuga carey)</a>,{' '}
        <a href="https://www.eltiempo.com/vida/medio-ambiente/pez-loro-especie-amenazada-crucial-para-conservar-arrecifes-de-san-andres-741612" target="_blank" rel="noreferrer">El Tiempo (pez loro)</a>.
      </p>
    </section>
  );
}
