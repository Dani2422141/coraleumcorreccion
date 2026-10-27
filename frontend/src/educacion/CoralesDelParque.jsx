import { useEffect, useState } from 'react';
import { ganarInsignia } from './progreso';
import imgPalmata from '../assets/arrecife/coral-palmata.webp';
import imgCervicornis from '../assets/arrecife/coral-cervicornis.webp';
import imgAnnularis from '../assets/arrecife/coral-annularis.webp';
import imgFaveolata from '../assets/arrecife/coral-faveolata.webp';
import imgCerebro from '../assets/arrecife/coral-cerebro.webp';

// Especies con presencia documentada en el PNN Corales del Rosario y de San Bernardo.
// Cada dato del parque lleva su fuente.
const ESPECIES = [
  {
    id: 'palmata',
    comun: 'Cuerno de alce',
    cientifico: 'Acropora palmata',
    estado: 'En peligro crítico',
    gravedad: 3,
    forma: 'ramas',
    rol: 'Sus ramas anchas y planas forman la cresta del arrecife: el muro que frena las olas antes de que lleguen a las islas.',
    parque: 'En la cresta arrecifal de Isla Grande, donde antes era la especie dominante, ya no quedan colonias vivas.',
    fuente: { nombre: 'Mongabay, junio de 2026', url: 'https://es.mongabay.com/2026/06/acroporas-primera-linea-corales-desapareciendo-caribe-colombiano/' },
  },
  {
    id: 'cervicornis',
    comun: 'Cacho de venado',
    cientifico: 'Acropora cervicornis',
    estado: 'En peligro crítico',
    gravedad: 3,
    forma: 'cachos',
    rol: 'Crece en matorrales de ramas delgadas que sirven de guardería a peces juveniles y langostas.',
    parque: 'En el Caribe colombiano sus formaciones cayeron en picada; en el Tayrona se redujeron un 99,3 % entre 2001 y 2018. Hoy se cultiva para restaurar arrecifes.',
    fuente: { nombre: 'Mongabay, junio de 2026', url: 'https://es.mongabay.com/2026/06/acroporas-primera-linea-corales-desapareciendo-caribe-colombiano/' },
  },
  {
    id: 'annularis',
    comun: 'Coral estrella lobulado',
    cientifico: 'Orbicella annularis',
    estado: 'En peligro',
    gravedad: 2,
    forma: 'lobulos',
    rol: 'Crece en columnas redondeadas y es uno de los grandes constructores del arrecife: aporta buena parte de su estructura.',
    parque: 'En septiembre de 2020 guardaparques grabaron su desove en Isla Grande, información clave para criar larvas y repoblar arrecifes dañados.',
    fuente: { nombre: 'El Heraldo, septiembre de 2020', url: 'https://www.elheraldo.co/medio-ambiente/investigadores-graban-reproduccion-de-corales-en-isla-grande-759117' },
  },
  {
    id: 'faveolata',
    comun: 'Coral estrella montañoso',
    cientifico: 'Orbicella faveolata',
    estado: 'En peligro',
    gravedad: 2,
    forma: 'montana',
    rol: 'Forma grandes montículos que pueden vivir siglos y dan refugio a cientos de especies.',
    parque: 'También se registró su desove en Isla Grande; su distribución ha disminuido en las últimas décadas.',
    fuente: { nombre: 'El Heraldo, septiembre de 2020', url: 'https://www.elheraldo.co/medio-ambiente/investigadores-graban-reproduccion-de-corales-en-isla-grande-759117' },
  },
  {
    id: 'cerebro',
    comun: 'Coral cerebro',
    cientifico: 'Diploria labyrinthiformis',
    estado: null,
    gravedad: 1,
    forma: 'cerebro',
    rol: 'Sus surcos parecen los de un cerebro. Crece despacio y forma cúpulas muy resistentes.',
    parque: 'En 2023 se trasplantaron colonias de coral cerebro en la barrera arrecifal de Isla Grande para restaurarla.',
    fuente: { nombre: 'Minambiente, 2023', url: 'https://www.minambiente.gov.co/corales-son-trasplantados-para-restaurar-arrecifes-en-isla-grande/' },
  },
];

// Ilustraciones de cada especie (fondo transparente).
const IMAGENES = { palmata: imgPalmata, cervicornis: imgCervicornis, annularis: imgAnnularis, faveolata: imgFaveolata, cerebro: imgCerebro };

export default function CoralesDelParque() {
  const [activa, setActiva] = useState(ESPECIES[0].id);
  const [vistas, setVistas] = useState(() => new Set([ESPECIES[0].id]));
  const especie = ESPECIES.find((e) => e.id === activa);

  useEffect(() => {
    if (vistas.size === ESPECIES.length) ganarInsignia('fichas');
  }, [vistas]);

  function elegir(id) {
    setActiva(id);
    setVistas((v) => new Set(v).add(id));
  }

  return (
    <section className="edu-especies" aria-labelledby="edu-especies-titulo">
      <div className="edu-especies-cabecera">
        <h2 id="edu-especies-titulo" className="edu-titulo-seccion">Los corales de nuestro parque</h2>
        <p>
          El parque guarda el 84 % de los arrecifes de la plataforma continental de Colombia
          (<a href="https://www.minambiente.gov.co/corales-son-trasplantados-para-restaurar-arrecifes-en-isla-grande/" target="_blank" rel="noreferrer">Minambiente</a>).
          Conoce a cinco de sus constructores. Has visto {vistas.size} de {ESPECIES.length}.
        </p>
      </div>

      <div className="edu-especies-cuerpo">
        <div className="edu-especies-lista" role="tablist" aria-label="Especies de coral">
          {ESPECIES.map((e) => (
            <button
              key={e.id}
              type="button"
              role="tab"
              aria-selected={activa === e.id}
              className={`edu-especie-boton ${activa === e.id ? 'is-activa' : ''} ${vistas.has(e.id) ? 'is-vista' : ''}`}
              onClick={() => elegir(e.id)}
              data-gravedad={e.gravedad}
            >
              <img src={IMAGENES[e.id]} alt="" loading="lazy" />
              <span>
                <strong>{e.comun}</strong>
                <em>{e.cientifico}</em>
              </span>
            </button>
          ))}
        </div>

        <article className="edu-ficha" role="tabpanel" key={especie.id} data-gravedad={especie.gravedad}>
          <div className="edu-ficha-dibujo">
            <img src={IMAGENES[especie.id]} alt={`Ilustración del ${especie.comun.toLowerCase()} (${especie.cientifico})`} />
          </div>
          <div className="edu-ficha-texto">
            <h3 className="edu-display">{especie.comun}</h3>
            <p className="edu-ficha-cientifico">{especie.cientifico}</p>
            {especie.estado && <span className="edu-estado-uicn">{especie.estado} según la UICN</span>}
            <h4>Qué hace en el arrecife</h4>
            <p>{especie.rol}</p>
            <h4>En el parque</h4>
            <p>{especie.parque}</p>
            <a className="edu-fuente" href={especie.fuente.url} target="_blank" rel="noreferrer">Fuente: {especie.fuente.nombre}</a>
          </div>
        </article>
      </div>
    </section>
  );
}
