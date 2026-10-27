import { useEffect, useMemo, useState } from 'react';
import { getEstadoParque } from '../data/api';
import Icono from '../educacion/Iconos';
import { INSIGNIAS, ganarInsignia, reiniciarProgreso } from '../educacion/progreso';
import { useProgreso } from '../educacion/useProgreso';
import { fechaLarga, numero } from '../educacion/niveles';

const GRUPOS = [
  {
    titulo: 'En el agua',
    acciones: [
      { id: 'tocar', icono: 'mano', texto: 'No toco ni me paro sobre los corales', porque: 'Un roce rompe su tejido vivo y abre la puerta a infecciones.' },
      { id: 'fauna', icono: 'pez', texto: 'Observo la fauna sin alimentarla ni perseguirla', porque: 'Los peces herbívoros mantienen el arrecife libre de algas.' },
      { id: 'sol', icono: 'sol', texto: 'Nado con camiseta de protección solar', porque: 'Así necesito menos bloqueador y llega menos al agua.' },
    ],
  },
  {
    titulo: 'En la lancha y en la playa',
    acciones: [
      { id: 'ancla', icono: 'ancla', texto: 'Pido que la lancha use boya de amarre y no eche el ancla sobre el arrecife', porque: 'Un ancla destruye en segundos corales que tardaron siglos en crecer.' },
      { id: 'plastico', icono: 'bolsa', texto: 'No llevo plásticos de un solo uso a las islas', porque: 'El plástico termina en el mar y enreda o asfixia la vida marina.' },
      { id: 'souvenir', icono: 'coral', texto: 'No compro ni me llevo corales, conchas ni estrellas de mar', porque: 'Cada pieza es parte del arrecife o de un animal que lo habita.' },
    ],
  },
  {
    titulo: 'En mi vida diaria',
    acciones: [
      { id: 'carbono', icono: 'bus', texto: 'Camino, uso bicicleta o transporte público cuando puedo', porque: 'El calentamiento del océano es la principal causa del blanqueamiento.' },
      { id: 'energia', icono: 'foco', texto: 'Ahorro energía en casa', porque: 'Menos energía malgastada, menos gases que calientan el planeta.' },
      { id: 'reporte', icono: 'camara', texto: 'Si veo corales blancos, tomo una foto y aviso a los guardaparques', porque: 'Los reportes ayudan a detectar a tiempo un blanqueamiento.' },
      { id: 'contar', icono: 'compartir', texto: 'Le cuento a alguien lo que aprendí aquí', porque: 'Quien entiende el problema es quien cuida el arrecife.' },
    ],
  },
];
const ACCIONES = GRUPOS.flatMap((g) => g.acciones);
const CLAVE = 'coraleum-compromisos-v1';

function leerCompromisos() {
  try { return new Set(JSON.parse(localStorage.getItem(CLAVE) || '[]')); } catch (_) { return new Set(); }
}

// ------------------------------------------------------------
// Dibujo en canvas (tarjeta y certificado)
// ------------------------------------------------------------

function envolver(ctx, texto, x, y, ancho, alto) {
  const palabras = texto.split(' ');
  let linea = '';
  let yy = y;
  palabras.forEach((p, i) => {
    const prueba = linea ? `${linea} ${p}` : p;
    if (ctx.measureText(prueba).width > ancho && linea) {
      ctx.fillText(linea, x, yy);
      linea = p;
      yy += alto;
    } else {
      linea = prueba;
    }
    if (i === palabras.length - 1) ctx.fillText(linea, x, yy);
  });
  return yy + alto;
}

function dibujarCoral(ctx, x, y, escala, color) {
  ctx.save();
  ctx.translate(x, y);
  ctx.scale(escala, escala);
  ctx.strokeStyle = color;
  ctx.lineWidth = 2.6;
  ctx.lineCap = 'round';
  ctx.lineJoin = 'round';
  ctx.stroke(new Path2D('M16 30V19m0 0-5-5V8m5 11 5-6V6m-10 8-4-3V6m14 7 4-3V5M11 8 9.5 4M21 6l1.5-3.5M16 19V11M10 30h12'));
  ctx.restore();
}

async function fuentesListas() {
  try {
    await Promise.all([document.fonts.load('500 80px Fraunces'), document.fonts.load('400 30px Outfit'), document.fonts.load('600 30px Outfit')]);
  } catch (_) { /* se usa la fuente de respaldo */ }
}

function fondoOceano(ctx, w, h) {
  const g = ctx.createLinearGradient(0, 0, 0, h);
  g.addColorStop(0, '#174651');
  g.addColorStop(1, '#0b252e');
  ctx.fillStyle = g;
  ctx.fillRect(0, 0, w, h);
  const luz = ctx.createRadialGradient(w * 0.75, 0, 10, w * 0.75, 0, w);
  luz.addColorStop(0, 'rgba(97,222,210,.22)');
  luz.addColorStop(1, 'rgba(97,222,210,0)');
  ctx.fillStyle = luz;
  ctx.fillRect(0, 0, w, h);
}

async function dibujarTarjeta(lienzo, parque, compromiso) {
  await fuentesListas();
  const w = 1080;
  const h = 1350;
  lienzo.width = w;
  lienzo.height = h;
  const ctx = lienzo.getContext('2d');
  fondoOceano(ctx, w, h);

  const alertas = parque ? ['alerta_1', 'alerta_2', 'alerta_3', 'alerta_4', 'alerta_5'].reduce((s, k) => s + (parque.niveles[k] || 0), 0) : null;
  ctx.fillStyle = '#9debe3';
  ctx.font = '400 34px Outfit, sans-serif';
  ctx.fillText('Corales del Rosario y de San Bernardo', 90, 140);

  ctx.fillStyle = '#f4fbf9';
  ctx.font = '500 150px Fraunces, Georgia, serif';
  ctx.fillText(parque ? (alertas === parque.total_areas ? `Las ${alertas}` : `${alertas} de ${parque.total_areas}`) : 'Los corales', 84, 330);
  ctx.font = '400 54px Fraunces, Georgia, serif';
  let y = envolver(ctx, parque ? 'áreas coralinas del parque están en alerta de blanqueamiento.' : 'del Caribe colombiano necesitan que los cuidemos.', 90, 420, 900, 66);

  if (parque) {
    ctx.fillStyle = 'rgba(237,248,246,.72)';
    ctx.font = '400 32px Outfit, sans-serif';
    y = envolver(ctx, `Calor acumulado promedio: ${numero(parque.dhw_promedio)} °C-semana, medido por satélite el ${fechaLarga(parque.fecha)}.`, 90, y + 20, 900, 44);
  }

  // Fila de corales, uno por cada área.
  if (parque) {
    const colores = { alerta_5: '#5e1846', alerta_4: '#8c1d4a', alerta_3: '#b8263f', alerta_2: '#e0473f', alerta_1: '#ef7f45', advertencia: '#f5b452', vigilancia: '#f1e38a', sin_estres: '#8fd3e8' };
    const lista = Object.entries(colores).flatMap(([k, c]) => Array.from({ length: parque.niveles[k] || 0 }, () => c));
    lista.forEach((c, i) => dibujarCoral(ctx, 90 + (i % 12) * 76, y + 40 + Math.floor(i / 12) * 76, 2, c));
    y += 40 + Math.ceil(lista.length / 12) * 76;
  }

  ctx.fillStyle = 'rgba(97,222,210,.16)';
  ctx.fillRect(90, y + 30, 900, 2);
  ctx.fillStyle = '#61ded2';
  ctx.font = '600 30px Outfit, sans-serif';
  ctx.fillText('Mi compromiso', 90, y + 100);
  ctx.fillStyle = '#f4fbf9';
  ctx.font = '400 44px Fraunces, Georgia, serif';
  envolver(ctx, compromiso || 'Aprender y contarle a otros por qué importan los corales.', 90, y + 160, 900, 56);

  ctx.fillStyle = 'rgba(237,248,246,.55)';
  ctx.font = '400 26px Outfit, sans-serif';
  ctx.fillText('Coraleum, con datos satelitales de NOAA Coral Reef Watch', 90, h - 80);
  return lienzo.toDataURL('image/png');
}

async function dibujarCertificado(lienzo, nombre, fecha) {
  await fuentesListas();
  const w = 1600;
  const h = 1130;
  lienzo.width = w;
  lienzo.height = h;
  const ctx = lienzo.getContext('2d');
  fondoOceano(ctx, w, h);
  ctx.strokeStyle = 'rgba(157,235,227,.45)';
  ctx.lineWidth = 3;
  ctx.strokeRect(50, 50, w - 100, h - 100);
  ctx.strokeStyle = 'rgba(157,235,227,.18)';
  ctx.strokeRect(66, 66, w - 132, h - 132);

  ctx.textAlign = 'center';
  ctx.fillStyle = '#9debe3';
  ctx.font = '400 34px Outfit, sans-serif';
  ctx.fillText('Coraleum certifica que', w / 2, 250);
  ctx.fillStyle = '#f4fbf9';
  ctx.font = '500 104px Fraunces, Georgia, serif';
  ctx.fillText(nombre, w / 2, 400, w - 260);
  ctx.fillStyle = 'rgba(237,248,246,.8)';
  ctx.font = '400 36px Outfit, sans-serif';
  ctx.fillText('completó el recorrido educativo y es', w / 2, 490);
  ctx.fillStyle = '#ffb08f';
  ctx.font = 'italic 500 82px Fraunces, Georgia, serif';
  ctx.fillText('Guardián del arrecife', w / 2, 600);
  ctx.fillStyle = 'rgba(237,248,246,.72)';
  ctx.font = '400 30px Outfit, sans-serif';
  ctx.fillText('del Parque Nacional Natural Corales del Rosario y de San Bernardo', w / 2, 670);

  const colores = ['#8fd3e8', '#f5b452', '#ef7f45', '#e0473f', '#61ded2'];
  INSIGNIAS.forEach((ins, i) => {
    const x = w / 2 + (i - 2) * 235;
    ctx.beginPath();
    ctx.arc(x, 800, 52, 0, Math.PI * 2);
    ctx.fillStyle = 'rgba(97,222,210,.10)';
    ctx.fill();
    ctx.strokeStyle = colores[i];
    ctx.lineWidth = 3;
    ctx.stroke();
    dibujarCoral(ctx, x - 32, 768, 2, colores[i]);
    ctx.fillStyle = 'rgba(237,248,246,.7)';
    ctx.font = '400 19px Outfit, sans-serif';
    ctx.fillText(ins.nombre, x, 885, 220);
  });
  ctx.fillStyle = 'rgba(237,248,246,.6)';
  ctx.font = '400 26px Outfit, sans-serif';
  ctx.fillText(fecha, w / 2, 990);
  ctx.textAlign = 'left';
  return lienzo.toDataURL('image/png');
}

function descargar(url, nombre) {
  const a = document.createElement('a');
  a.href = url;
  a.download = nombre;
  a.click();
}

function dataUrlABlob(url) {
  const [cabecera, datos] = url.split(',');
  const bytes = atob(datos);
  const arreglo = new Uint8Array(bytes.length);
  for (let i = 0; i < bytes.length; i += 1) arreglo[i] = bytes.charCodeAt(i);
  return new Blob([arreglo], { type: cabecera.match(/:(.*?);/)[1] });
}

async function compartirImagen(url, nombre, texto) {
  const blob = dataUrlABlob(url);
  const archivo = new File([blob], nombre, { type: 'image/png' });
  if (navigator.canShare?.({ files: [archivo] })) {
    await navigator.share({ files: [archivo], text: texto });
    return true;
  }
  return false;
}

// ------------------------------------------------------------

export default function ViewActua({ onNavigate }) {
  const [elegidos, setElegidos] = useState(leerCompromisos);
  const [parque, setParque] = useState(null);
  const [tarjeta, setTarjeta] = useState('');
  const [aviso, setAviso] = useState('');
  const [nombre, setNombre] = useState('');
  const [certificado, setCertificado] = useState('');
  const progreso = useProgreso();

  useEffect(() => { getEstadoParque().then((d) => setParque(d.disponible ? d : null)).catch(() => setParque(null)); }, []);

  useEffect(() => {
    try { localStorage.setItem(CLAVE, JSON.stringify([...elegidos])); } catch (_) { /* sin almacenamiento */ }
    if (elegidos.size >= 3) ganarInsignia('compromiso');
  }, [elegidos]);

  const primerCompromiso = useMemo(() => ACCIONES.find((a) => elegidos.has(a.id))?.texto, [elegidos]);

  useEffect(() => {
    let vigente = true;
    dibujarTarjeta(document.createElement('canvas'), parque, primerCompromiso).then((url) => { if (vigente) setTarjeta(url); });
    return () => { vigente = false; };
  }, [parque, primerCompromiso]);

  const ganadas = INSIGNIAS.filter((i) => progreso[i.id]).length;
  const completo = ganadas === INSIGNIAS.length;

  function alternar(id) {
    setElegidos((actual) => {
      const nuevo = new Set(actual);
      if (nuevo.has(id)) nuevo.delete(id); else nuevo.add(id);
      return nuevo;
    });
  }

  async function compartir() {
    setAviso('');
    try {
      const ok = await compartirImagen(tarjeta, 'coraleum-mi-compromiso.png', 'Los corales del Rosario y San Bernardo están en alerta. Este es mi compromiso para cuidarlos.');
      if (!ok) {
        descargar(tarjeta, 'coraleum-mi-compromiso.png');
        setAviso('Tu navegador no permite compartir directamente: descargamos la imagen para que la publiques.');
      }
    } catch (_) { /* la persona canceló */ }
  }

  async function generarCertificado(evento) {
    evento.preventDefault();
    const limpio = nombre.trim().replace(/\s+/g, ' ').slice(0, 60);
    if (!limpio) return;
    const hoy = new Date().toLocaleDateString('es-CO', { day: 'numeric', month: 'long', year: 'numeric' });
    const url = await dibujarCertificado(document.createElement('canvas'), limpio, hoy);
    setCertificado(url);
    descargar(url, 'coraleum-certificado-guardian.png');
  }

  return (
    <div className="edu-actua">
      <div className="edu-actua-cabecera">
        <h1 className="edu-display">Cuida el arrecife</h1>
        <p>
          El calentamiento del océano no se resuelve en un día, pero muchas amenazas para los corales sí dependen de lo que
          hacemos al visitarlos y en casa. Elige tus compromisos: se convierten en una tarjeta para compartir.
        </p>
      </div>

      <div className="edu-actua-cuerpo">
        <div className="edu-compromisos">
          {GRUPOS.map((g) => (
            <fieldset key={g.titulo} className="edu-grupo">
              <legend>{g.titulo}</legend>
              {g.acciones.map((a) => {
                const marcado = elegidos.has(a.id);
                return (
                  <label key={a.id} className={`edu-compromiso ${marcado ? 'is-marcado' : ''}`}>
                    <input type="checkbox" checked={marcado} onChange={() => alternar(a.id)} />
                    <span className="edu-compromiso-icono"><Icono nombre={a.icono} size={22} /></span>
                    <span className="edu-compromiso-texto">
                      <strong>{a.texto}</strong>
                      <small>{a.porque}</small>
                    </span>
                    <span className="edu-compromiso-check" aria-hidden="true">
                      <svg viewBox="0 0 24 24" width="16" height="16"><path d="m5 12 5 5 9-10" fill="none" stroke="currentColor" strokeWidth="2.6" strokeLinecap="round" strokeLinejoin="round" /></svg>
                    </span>
                  </label>
                );
              })}
            </fieldset>
          ))}
        </div>

        <aside className="edu-tarjeta-panel">
          <h2 className="edu-titulo-seccion">Tu tarjeta</h2>
          <p className="edu-tarjeta-ayuda">
            {elegidos.size
              ? `Llevas ${elegidos.size} ${elegidos.size === 1 ? 'compromiso' : 'compromisos'}. La tarjeta muestra el primero y el estado real del parque.`
              : 'Elige un compromiso para ponerlo en tu tarjeta.'}
          </p>
          <div className="edu-tarjeta-vista">
            {tarjeta ? <img src={tarjeta} alt="Vista previa de la tarjeta para compartir" /> : <div className="edu-tarjeta-cargando" />}
          </div>
          <div className="edu-tarjeta-acciones">
            <button type="button" className="edu-boton edu-boton-principal" onClick={compartir} disabled={!tarjeta}>
              <Icono nombre="compartir" size={18} /> Compartir
            </button>
            <button type="button" className="edu-boton" onClick={() => descargar(tarjeta, 'coraleum-mi-compromiso.png')} disabled={!tarjeta}>
              <Icono nombre="descargar" size={18} /> Descargar imagen
            </button>
          </div>
          {aviso && <p className="edu-tarjeta-ayuda">{aviso}</p>}
        </aside>
      </div>

      <section className="edu-recorrido" aria-labelledby="edu-recorrido-titulo">
        <div className="edu-recorrido-cabecera">
          <h2 id="edu-recorrido-titulo" className="edu-titulo-seccion">Tu recorrido</h2>
          <p>{completo ? 'Ganaste las cinco insignias. Ya puedes descargar tu certificado.' : `Llevas ${ganadas} de ${INSIGNIAS.length} insignias. Gana todas para obtener el certificado de Guardián del arrecife.`}</p>
        </div>
        <ol className="edu-insignias">
          {INSIGNIAS.map((ins) => {
            const ganada = Boolean(progreso[ins.id]);
            return (
              <li key={ins.id} className={`edu-insignia ${ganada ? 'is-ganada' : ''}`}>
                <span className="edu-insignia-medalla"><Icono nombre={ins.icono} size={26} /></span>
                <strong>{ins.nombre}</strong>
                {ganada ? <small>Ganada</small> : (
                  <button type="button" className="edu-enlace" onClick={() => onNavigate(ins.vista)}>{ins.como}</button>
                )}
              </li>
            );
          })}
        </ol>

        <div className={`edu-certificado ${completo ? '' : 'is-bloqueado'}`}>
          {completo ? (
            <form onSubmit={generarCertificado}>
              <label>
                <span>Nombre para el certificado</span>
                <input value={nombre} onChange={(e) => setNombre(e.target.value)} maxLength={60} required placeholder="Escribe tu nombre" />
              </label>
              <button type="submit" className="edu-boton edu-boton-principal"><Icono nombre="descargar" size={18} /> Descargar certificado</button>
            </form>
          ) : (
            <p>El certificado se desbloquea con las cinco insignias. Tu nombre solo se usa para dibujarlo en tu navegador; no se envía a ningún servidor.</p>
          )}
          {certificado && <img className="edu-certificado-vista" src={certificado} alt={`Certificado de Guardián del arrecife para ${nombre}`} />}
        </div>
        {ganadas > 0 && (
          <button type="button" className="edu-enlace edu-reiniciar" onClick={reiniciarProgreso}>Reiniciar mi recorrido</button>
        )}
      </section>
    </div>
  );
}
