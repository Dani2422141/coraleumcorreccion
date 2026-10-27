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

  /**
   * Primer paso del inicio de sesión. Si la cuenta tiene verificación en dos
   * pasos, devuelve { requiere2fa, desafio } y la sesión aún no se abre.
   */
  const login = useCallback(async (email, password) => {
    const respuesta = await auth.login(email, password);
    if (respuesta.requiere_2fa) return { requiere2fa: true, desafio: respuesta.desafio };
    setUsuario(respuesta.usuario);
    setAviso('');
    return { usuario: respuesta.usuario };
  }, []);

  const verificar2fa = useCallback(async (desafio, codigo) => {
    const { usuario: u } = await auth.verificar2fa(desafio, codigo);
    setUsuario(u);
    setAviso('');
    return u;
  }, []);

  const registro = useCallback(async (nombre, email, password, aceptaPolitica) => {
    const { usuario: u } = await auth.registro(nombre, email, password, aceptaPolitica);
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
      verificar2fa,
      registro,
      logout,
      debeAceptarPolitica: Boolean(usuario?.politica_pendiente),
      recargar: cargarSesion,
      autenticado: Boolean(usuario),
      puedeVerDatos: rol === 'investigador' || rol === 'admin',
      esAdmin: rol === 'admin',
    };
  }, [usuario, cargando, aviso, login, verificar2fa, registro, logout, cargarSesion]);

  return <AuthContext.Provider value={valor}>{children}</AuthContext.Provider>;
}

export function useAuth() {
  const contexto = useContext(AuthContext);
  if (!contexto) throw new Error('useAuth debe usarse dentro de <AuthProvider>.');
  return contexto;
}
