import { useState } from 'react';

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

/** Campo de contraseña con botón para mostrar u ocultar. */
export function CampoPassword({ etiqueta, valor, onCambio, autoComplete = 'current-password', pista, pistaOk, autoFocus = false }) {
  const [visible, setVisible] = useState(false);
  return (
    <Campo etiqueta={etiqueta} pista={pista} pistaOk={pistaOk}>
      <div className="campo-password">
        <input
          type={visible ? 'text' : 'password'}
          value={valor}
          onChange={(e) => onCambio(e.target.value)}
          autoComplete={autoComplete}
          maxLength={128}
          required
          autoFocus={autoFocus}
        />
        <button type="button" onClick={() => setVisible((v) => !v)} aria-label={visible ? 'Ocultar contraseña' : 'Mostrar contraseña'}>
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

export function BadgeRol({ rol }) {
  const nombres = { usuario: 'Usuario', investigador: 'Investigador', admin: 'Administrador' };
  return <span className={`badge badge-${rol}`}>{nombres[rol] || rol}</span>;
}

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
