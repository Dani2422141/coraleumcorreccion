import { createContext, useCallback, useContext, useEffect, useMemo, useState } from 'react';
import { auth, EVENTO_SESION } from '../data/api';

const AuthContext = createContext(null);

export const ROLES = {
  usuario: 'Usuario',
  investigador: 'Investigador',
  admin: 'Administrador',
};

/**
 * Estado de la sesión en el navegador.
 *
 * Importante: esto solo decide qué se MUESTRA. Quien protege los datos es
 * el backend, que vuelve a comprobar el rol en cada petición.
 */
export function AuthProvider({ children }) {
  const [usuario, setUsuario] = useState(null);
  const [cargando, setCargando] = useState(true);
  const [aviso, setAviso] = useState('');

  const cargarSesion = useCallback(async () => {
    try {
      let { usuario: actual } = await auth.me();
      // El token de acceso dura 15 min; si venció, se intenta renovar.
      if (!actual && (await auth.renovar())) {
        ({ usuario: actual } = await auth.me());
      }
      setUsuario(actual);
    } catch (_) {
      setUsuario(null);
    } finally {
      setCargando(false);
    }
  }, []);

  useEffect(() => { cargarSesion(); }, [cargarSesion]);

  useEffect(() => {
    function alAviso(evento) {
      if (evento.detail?.tipo === 'vencida') {
        setUsuario(null);
        setAviso('Tu sesión venció. Inicia sesión de nuevo.');
      } else if (evento.detail?.tipo === 'cambiar-password') {
        setUsuario((u) => (u ? { ...u, debe_cambiar_password: true } : u));
      }
    }
    window.addEventListener(EVENTO_SESION, alAviso);
    return () => window.removeEventListener(EVENTO_SESION, alAviso);
  }, []);

  const login = useCallback(async (email, password) => {
    const { usuario: u } = await auth.login(email, password);
    setUsuario(u);
    setAviso('');
    return u;
  }, []);

  const registro = useCallback(async (nombre, email, password) => {
    const { usuario: u } = await auth.registro(nombre, email, password);
    setUsuario(u);
    setAviso('');
    return u;
  }, []);

  const logout = useCallback(async () => {
    try { await auth.logout(); } catch (_) { /* la sesión local se borra igual */ }
    setUsuario(null);
  }, []);

  const valor = useMemo(() => {
    const rol = usuario?.rol || null;
    return {
      usuario,
      setUsuario,
      cargando,
      aviso,
      setAviso,
      login,
      registro,
      logout,
      recargar: cargarSesion,
      autenticado: Boolean(usuario),
      puedeVerDatos: rol === 'investigador' || rol === 'admin',
      esAdmin: rol === 'admin',
    };
  }, [usuario, cargando, aviso, login, registro, logout, cargarSesion]);

  return <AuthContext.Provider value={valor}>{children}</AuthContext.Provider>;
}

export function useAuth() {
  const contexto = useContext(AuthContext);
  if (!contexto) throw new Error('useAuth debe usarse dentro de <AuthProvider>.');
  return contexto;
}
