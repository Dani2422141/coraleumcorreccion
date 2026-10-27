import { createContext, useCallback, useContext, useEffect, useMemo, useRef, useState } from 'react';
import { auth, EVENTO_SESION } from '../data/api';

const AuthContext = createContext(null);

export const ROLES = {
  usuario: 'Usuario',
  investigador: 'Investigador',
  admin: 'Administrador',
};

// Permisos administrativos: cualquiera de ellos muestra "Administración".
export const PERMISOS_ADMIN = [
  'solicitudes.aprobar',
  'usuarios.gestionar',
  'roles.gestionar',
  'auditoria.ver',
  'configuracion.gestionar',
];

const MENSAJE_INACTIVIDAD = 'Tu sesión se cerró por inactividad. Inicia sesión de nuevo.';
const MENSAJE_OTRA_PESTANA = 'Cerraste sesión en otra pestaña o ventana.';
const SEGUNDOS_ENTRE_CONSULTAS = 15;

/**
 * Canal entre pestañas del MISMO navegador. Cerrar sesión (o iniciarla) en
 * una pestaña se refleja al instante en las demás. Usa BroadcastChannel y,
 * en navegadores antiguos, el evento "storage" de localStorage.
 */
const CANAL = 'coraleum-sesion';
function crearCanal(alRecibir) {
  if (typeof BroadcastChannel !== 'undefined') {
    const canal = new BroadcastChannel(CANAL);
    canal.onmessage = (e) => alRecibir(e.data);
    return { enviar: (m) => canal.postMessage(m), cerrar: () => canal.close() };
  }
  const alStorage = (e) => {
    if (e.key !== CANAL || !e.newValue) return;
    try { alRecibir(JSON.parse(e.newValue)); } catch (_) { /* mensaje inválido */ }
  };
  window.addEventListener('storage', alStorage);
  return {
    enviar: (m) => {
      try { localStorage.setItem(CANAL, JSON.stringify({ ...m, t: Date.now() })); localStorage.removeItem(CANAL); } catch (_) { /* sin almacenamiento */ }
    },
    cerrar: () => window.removeEventListener('storage', alStorage),
  };
}

/**
 * Estado de la sesión en el navegador.
 *
 * Importante: esto solo decide qué se MUESTRA. Quien protege los datos es
 * el backend, que vuelve a comprobar los permisos en cada petición.
 */
export function AuthProvider({ children }) {
  const [usuario, setUsuario] = useState(null);
  const [cargando, setCargando] = useState(true);
  const [aviso, setAviso] = useState('');
  // Mensaje informativo con la sesión abierta (p. ej., "se cerró tu sesión en Chrome").
  const [notificacion, setNotificacion] = useState('');
  const canal = useRef(null);
  const limiteInactividad = useRef(30 * 60);
  const ultimoAvisoActividad = useRef(0);

  const cargarSesion = useCallback(async () => {
    try {
      let { usuario: actual } = await auth.me();
      // El token de acceso es de corta duración; si venció, se intenta renovar.
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

  const cerrarEnPantalla = useCallback((mensaje) => {
    setUsuario(null);
    setNotificacion('');
    setAviso(mensaje || MENSAJE_INACTIVIDAD);
  }, []);

  // Sincronización entre pestañas.
  useEffect(() => {
    canal.current = crearCanal((mensaje) => {
      if (mensaje?.tipo === 'logout') cerrarEnPantalla(MENSAJE_OTRA_PESTANA);
      else if (mensaje?.tipo === 'login') { setAviso(''); cargarSesion(); }
      else if (mensaje?.tipo === 'actualizado') cargarSesion();
    });
    return () => canal.current?.cerrar();
  }, [cerrarEnPantalla, cargarSesion]);

  const avisarPestanas = useCallback((tipo) => canal.current?.enviar({ tipo }), []);

  useEffect(() => {
    function alAviso(evento) {
      if (evento.detail?.tipo === 'vencida') {
        cerrarEnPantalla(evento.detail.mensaje || 'Tu sesión venció. Inicia sesión de nuevo.');
      } else if (evento.detail?.tipo === 'cambiar-password') {
        setUsuario((u) => (u ? { ...u, debe_cambiar_password: true } : u));
      }
    }
    window.addEventListener(EVENTO_SESION, alAviso);
    return () => window.removeEventListener(EVENTO_SESION, alAviso);
  }, [cerrarEnPantalla]);

  const autenticado = Boolean(usuario);

  // Control de inactividad: se consulta el estado (sin contarlo como uso) y,
  // si la sesión venció en el servidor, se cierra también en pantalla.
  useEffect(() => {
    if (!autenticado) return undefined;
    let cancelado = false;
    async function consultar() {
      try {
        const estado = await auth.estado();
        if (cancelado) return;
        if (!estado.activa) cerrarEnPantalla(estado.mensaje);
        else limiteInactividad.current = estado.inactividad_segundos || limiteInactividad.current;
      } catch (_) { /* sin conexión: se reintenta en la próxima consulta */ }
    }
    consultar();
    const temporizador = setInterval(consultar, SEGUNDOS_ENTRE_CONSULTAS * 1000);
    // Al volver a una pestaña se comprueba enseguida (no espera 15 s).
    const alVolver = () => { if (document.visibilityState === 'visible') consultar(); };
    document.addEventListener('visibilitychange', alVolver);
    window.addEventListener('focus', alVolver);
    return () => {
      cancelado = true;
      clearInterval(temporizador);
      document.removeEventListener('visibilitychange', alVolver);
      window.removeEventListener('focus', alVolver);
    };
  }, [autenticado, cerrarEnPantalla]);

  // Uso real de la aplicación (clic, teclado, desplazamiento) renueva la
  // sesión, como máximo una vez por cada cuarto del límite de inactividad.
  useEffect(() => {
    if (!autenticado) return undefined;
    async function alUsar() {
      const ahora = Date.now();
      const intervalo = Math.max(10, limiteInactividad.current / 4) * 1000;
      if (ahora - ultimoAvisoActividad.current < intervalo) return;
      ultimoAvisoActividad.current = ahora;
      try {
        const estado = await auth.actividad();
        if (!estado.activa) cerrarEnPantalla(estado.mensaje);
      } catch (_) { /* se reintenta con el próximo uso */ }
    }
    const eventos = ['click', 'keydown', 'wheel', 'touchstart'];
    eventos.forEach((e) => window.addEventListener(e, alUsar, { passive: true }));
    return () => eventos.forEach((e) => window.removeEventListener(e, alUsar));
  }, [autenticado, cerrarEnPantalla]);

  /**
   * Primer paso del inicio de sesión. Si la cuenta tiene verificación en dos
   * pasos, devuelve { requiere2fa, desafio } y la sesión aún no se abre.
   */
  const login = useCallback(async (email, password) => {
    const respuesta = await auth.login(email, password);
    if (respuesta.requiere_2fa) return { requiere2fa: true, desafio: respuesta.desafio };
    abrirSesion(respuesta);
    return { usuario: respuesta.usuario };
  }, []); // eslint-disable-line react-hooks/exhaustive-deps

  function abrirSesion(respuesta) {
    ultimoAvisoActividad.current = Date.now();
    setUsuario(respuesta.usuario);
    setAviso('');
    const cerradas = respuesta.sesiones_cerradas || [];
    setNotificacion(cerradas.length
      ? `Se cerró la sesión que tenías abierta en ${cerradas.join(', ')}: Coraleum limita las sesiones simultáneas por cuenta. Si no fuiste tú, cambia tu contraseña.`
      : '');
    avisarPestanas('login');
  }

  const verificar2fa = useCallback(async (desafio, codigo) => {
    const respuesta = await auth.verificar2fa(desafio, codigo);
    abrirSesion(respuesta);
    return respuesta.usuario;
  }, []); // eslint-disable-line react-hooks/exhaustive-deps

  const registro = useCallback(async (nombre, email, password, aceptaPolitica) => {
    const respuesta = await auth.registro(nombre, email, password, aceptaPolitica);
    abrirSesion(respuesta);
    return respuesta.usuario;
  }, []); // eslint-disable-line react-hooks/exhaustive-deps

  const logout = useCallback(async () => {
    try { await auth.logout(); } catch (_) { /* la sesión local se borra igual */ }
    setUsuario(null);
    setNotificacion('');
    // Las demás pestañas de este navegador también salen de inmediato.
    avisarPestanas('logout');
  }, [avisarPestanas]);

  const valor = useMemo(() => {
    const permisos = new Set(usuario?.permisos || []);
    const tiene = (p) => permisos.has(p);
    return {
      usuario,
      setUsuario,
      cargando,
      aviso,
      setAviso,
      notificacion,
      setNotificacion,
      avisarPestanas,
      login,
      verificar2fa,
      registro,
      logout,
      debeAceptarPolitica: Boolean(usuario?.politica_pendiente),
      recargar: cargarSesion,
      autenticado: Boolean(usuario),
      tienePermiso: tiene,
      puedeVerDatos: tiene('datos.consultar'),
      puedeVerHistorico: tiene('datos.historico'),
      esAdmin: PERMISOS_ADMIN.some(tiene),
      esAdministradorTotal: (usuario?.roles || []).some((r) => r.clave === 'admin'),
    };
  }, [usuario, cargando, aviso, notificacion, login, verificar2fa, registro, logout, cargarSesion, avisarPestanas]);

  return <AuthContext.Provider value={valor}>{children}</AuthContext.Provider>;
}

export function useAuth() {
  const contexto = useContext(AuthContext);
  if (!contexto) throw new Error('useAuth debe usarse dentro de <AuthProvider>.');
  return contexto;
}
