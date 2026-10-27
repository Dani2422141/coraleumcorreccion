import { useEffect, useState } from 'react';
import { EVENTO_PROGRESO, INSIGNIAS } from './progreso';
import Icono from './Iconos';

/** Aviso breve cuando la persona gana una insignia. */
export default function AvisoInsignia({ onNavigate }) {
  const [insignia, setInsignia] = useState(null);

  useEffect(() => {
    function alGanar(e) {
      const ganada = INSIGNIAS.find((i) => i.id === e.detail?.id);
      if (ganada) setInsignia(ganada);
    }
    window.addEventListener(EVENTO_PROGRESO, alGanar);
    return () => window.removeEventListener(EVENTO_PROGRESO, alGanar);
  }, []);

  useEffect(() => {
    if (!insignia) return undefined;
    const t = setTimeout(() => setInsignia(null), 6000);
    return () => clearTimeout(t);
  }, [insignia]);

  if (!insignia) return null;
  return (
    <div className="edu-aviso-insignia" role="status">
      <span className="edu-insignia-medalla"><Icono nombre={insignia.icono} size={22} /></span>
      <span>
        <strong>Ganaste la insignia {insignia.nombre}</strong>
        <button type="button" onClick={() => { setInsignia(null); onNavigate('actua'); }}>Ver tu recorrido</button>
      </span>
    </div>
  );
}
