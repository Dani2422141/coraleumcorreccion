import { useEffect, useState } from 'react';
import { EVENTO_PROGRESO, progresoActual } from './progreso';

export function useProgreso() {
  const [progreso, setProgreso] = useState(progresoActual);
  useEffect(() => {
    const alCambiar = () => setProgreso(progresoActual());
    window.addEventListener(EVENTO_PROGRESO, alCambiar);
    window.addEventListener('storage', alCambiar);
    return () => {
      window.removeEventListener(EVENTO_PROGRESO, alCambiar);
      window.removeEventListener('storage', alCambiar);
    };
  }, []);
  return progreso;
}
