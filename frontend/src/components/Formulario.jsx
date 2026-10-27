import { useEffect, useState } from 'react';

/** Campo de formulario con etiqueta accesible. */
export function Campo({ etiqueta, pista, pistaOk = false, children }) {
  return (
    <label className="campo">
      <span>{etiqueta}</span>
      {children}
      {pista && <small className={`pista ${pistaOk ? 'ok' : ''}`}>{pista}</small>}
    </label>
  );
}

/**
 * Campo de contraseña.
 * - Siempre se muestra enmascarado (••••); "Mostrar" lo revela 20 s como máximo.
 * - No se puede COPIAR, CORTAR ni ARRASTRAR su contenido, ni siquiera visible:
 *   así la contraseña no termina en el portapapeles (donde otras aplicaciones
 *   la pueden leer). Pegar SÍ se permite, para usar gestores de contraseñas
 *   (recomendación NIST SP 800-63B).
 * - Sin corrector ortográfico: algunos navegadores envían el texto a servicios
 *   externos de corrección.
 */
export function CampoPassword({ etiqueta, valor, onCambio, autoComplete = 'current-password', pista, pistaOk, autoFocus = false }) {
  const [visible, setVisible] = useState(false);
  const [bloqueado, setBloqueado] = useState(false);

  useEffect(() => {
    if (!visible) return undefined;
    const t = setTimeout(() => setVisible(false), 20000);
    return () => clearTimeout(t);
  }, [visible]);

  useEffect(() => {
    if (!bloqueado) return undefined;
    const t = setTimeout(() => setBloqueado(false), 4000);
    return () => clearTimeout(t);
  }, [bloqueado]);

  function impedir(e) {
    e.preventDefault();
    if (e.clipboardData) e.clipboardData.setData('text/plain', '');
    setBloqueado(true);
  }

  return (
    <Campo
      etiqueta={etiqueta}
      pista={bloqueado ? 'Por seguridad, la contraseña no se puede copiar ni cortar.' : pista}
      pistaOk={bloqueado ? false : pistaOk}
    >
      <div className="campo-password">
        <input
          type={visible ? 'text' : 'password'}
          value={valor}
          onChange={(e) => onCambio(e.target.value)}
          onCopy={impedir}
          onCut={impedir}
          onDragStart={impedir}
          onBlur={() => setVisible(false)}
          autoComplete={autoComplete}
          spellCheck={false}
          autoCorrect="off"
          autoCapitalize="off"
          data-campo-password="true"
          maxLength={128}
          required
          autoFocus={autoFocus}
        />
        <button
          type="button"
          onMouseDown={(e) => e.preventDefault()}
          onClick={() => setVisible((v) => !v)}
          aria-label={visible ? 'Ocultar contraseña' : 'Mostrar contraseña'}
        >
          {visible ? 'Ocultar' : 'Mostrar'}
        </button>
      </div>
    </Campo>
  );
}

export function Mensaje({ tipo = 'info', children }) {
  if (!children) return null;
  return <div className={`msg msg-${tipo}`} role={tipo === 'error' ? 'alert' : 'status'}>{children}</div>;
}

/** Pistas de la política de contraseñas (la validación real la hace el backend). */
export function pistaPassword(password) {
  if (!password) return { texto: 'Mínimo 10 caracteres. Una frase fácil de recordar es más segura que una palabra con símbolos.', ok: false };
  if (password.length < 10) return { texto: `Faltan ${10 - password.length} caracteres.`, ok: false };
  return { texto: 'Longitud adecuada.', ok: true };
}

export function BadgeRol({ rol, nombre }) {
  const nombres = { usuario: 'Usuario', investigador: 'Investigador', admin: 'Administrador' };
  const clase = nombres[rol] ? `badge-${rol}` : 'badge-personalizado';
  return <span className={`badge ${clase}`}>{nombre || nombres[rol] || rol}</span>;
}

/** Todas las insignias de roles de un usuario. */
export function BadgesRoles({ roles = [] }) {
  return <span className="badges-roles">{roles.map((r) => <BadgeRol key={r.clave} rol={r.clave} nombre={r.nombre} />)}</span>;
}

export const NOMBRES_PERMISOS = {
  'datos.consultar': 'Explorador y Resumen',
  'datos.historico': 'Histórico',
  'solicitudes.aprobar': 'Aprobar solicitudes',
  'usuarios.gestionar': 'Gestionar usuarios',
  'roles.gestionar': 'Gestionar roles',
  'auditoria.ver': 'Ver auditoría',
  'configuracion.gestionar': 'Configurar sesiones',
};

export function BadgeSolicitud({ estado }) {
  const nombres = { pendiente: 'Pendiente', aprobada: 'Aprobada', rechazada: 'Rechazada' };
  if (!estado) return null;
  return <span className={`badge badge-${estado}`}>{nombres[estado] || estado}</span>;
}

export function formatearFecha(iso) {
  if (!iso) return '—';
  const fecha = new Date(iso);
  if (Number.isNaN(fecha.getTime())) return '—';
  return fecha.toLocaleString('es-CO', { dateStyle: 'medium', timeStyle: 'short' });
}
