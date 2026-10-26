import { useState } from 'react';
import { useAuth } from '../auth/AuthContext';
import { auth } from '../data/api';
import { BadgeRol, BadgeSolicitud, Campo, CampoPassword, Mensaje, formatearFecha, pistaPassword } from '../components/Formulario';

function SolicitudInvestigador() {
  const { usuario, setUsuario } = useAuth();
  const [institucion, setInstitucion] = useState('');
  const [motivo, setMotivo] = useState('');
  const [error, setError] = useState('');
  const [enviando, setEnviando] = useState(false);
  const solicitud = usuario.solicitud;

  if (usuario.rol !== 'usuario') {
    return (
      <div className="cuenta-card">
        <h3>Acceso de investigación</h3>
        <p className="ayuda" style={{ marginBottom: 0 }}>
          Tu cuenta tiene acceso al Explorador Térmico, al detalle por área y al registro histórico.
        </p>
      </div>
    );
  }

  async function enviar(evento) {
    evento.preventDefault();
    setError('');
    setEnviando(true);
    try {
      const { usuario: actualizado } = await auth.solicitarInvestigador(institucion.trim(), motivo.trim());
      setUsuario(actualizado);
    } catch (err) {
      setError(err.message);
    } finally {
      setEnviando(false);
    }
  }

  return (
    <div className="cuenta-card">
      <h3>Solicitar acceso de investigador</h3>
      <p className="ayuda">
        El Explorador Térmico y el registro histórico están dirigidos a investigadores, estudiantes y profesionales.
        Un administrador revisará tu solicitud.
      </p>

      {solicitud?.estado === 'pendiente' ? (
        <Mensaje tipo="info">
          Tu solicitud ({solicitud.institucion}) está <strong>pendiente de revisión</strong> desde {formatearFecha(solicitud.fecha)}.
        </Mensaje>
      ) : (
        <>
          {solicitud?.estado === 'rechazada' && (
            <Mensaje tipo="error">
              Tu solicitud anterior fue rechazada{solicitud.comentario_admin ? `: ${solicitud.comentario_admin}` : '.'} Puedes enviar una nueva.
            </Mensaje>
          )}
          <Mensaje tipo="error">{error}</Mensaje>
          <form onSubmit={enviar}>
            <Campo etiqueta="Institución u organización">
              <input value={institucion} onChange={(e) => setInstitucion(e.target.value)} minLength={2} maxLength={120} required placeholder="Ej.: Universidad de San Buenaventura" />
            </Campo>
            <Campo etiqueta="¿Para qué necesitas los datos?" pista={`${motivo.length}/500 · mínimo 10 caracteres`}>
              <textarea value={motivo} onChange={(e) => setMotivo(e.target.value)} minLength={10} maxLength={500} required placeholder="Ej.: Análisis del DHW en las áreas de Barú para mi trabajo de grado." />
            </Campo>
            <button className="btn btn-primario" type="submit" disabled={enviando}>{enviando ? 'Enviando…' : 'Enviar solicitud'}</button>
          </form>
        </>
      )}
    </div>
  );
}

export function FormularioCambioPassword({ obligatorio = false, onListo }) {
  const { setUsuario } = useAuth();
  const [actual, setActual] = useState('');
  const [nueva, setNueva] = useState('');
  const [confirmacion, setConfirmacion] = useState('');
  const [error, setError] = useState('');
  const [ok, setOk] = useState('');
  const [enviando, setEnviando] = useState(false);

  async function enviar(evento) {
    evento.preventDefault();
    setError('');
    setOk('');
    if (nueva !== confirmacion) {
      setError('Las contraseñas nuevas no coinciden.');
      return;
    }
    setEnviando(true);
    try {
      const { usuario: actualizado } = await auth.cambiarPassword(actual, nueva);
      setUsuario(actualizado);
      setActual(''); setNueva(''); setConfirmacion('');
      setOk('Contraseña actualizada. Se cerraron tus otras sesiones abiertas.');
      onListo?.();
    } catch (err) {
      setError(err.message);
    } finally {
      setEnviando(false);
    }
  }

  const pista = pistaPassword(nueva);
  return (
    <form onSubmit={enviar}>
      <Mensaje tipo="error">{error}</Mensaje>
      <Mensaje tipo="ok">{ok}</Mensaje>
      <CampoPassword etiqueta={obligatorio ? 'Contraseña temporal' : 'Contraseña actual'} valor={actual} onCambio={setActual} autoFocus={obligatorio} />
      <CampoPassword etiqueta="Nueva contraseña" valor={nueva} onCambio={setNueva} autoComplete="new-password" pista={pista.texto} pistaOk={pista.ok} />
      <CampoPassword
        etiqueta="Repite la nueva contraseña"
        valor={confirmacion}
        onCambio={setConfirmacion}
        autoComplete="new-password"
        pista={confirmacion && confirmacion !== nueva ? 'No coincide.' : undefined}
      />
      <button className={`btn btn-primario ${obligatorio ? 'btn-bloque' : ''}`} type="submit" disabled={enviando}>
        {enviando ? 'Guardando…' : 'Cambiar contraseña'}
      </button>
    </form>
  );
}

/** Pantalla obligatoria cuando el administrador restableció la contraseña. */
export function CambioPasswordObligatorio() {
  const { usuario, logout } = useAuth();
  return (
    <div className="cuenta-page">
      <div className="cuenta-wrap estrecho">
        <span className="cuenta-kicker">Seguridad de la cuenta</span>
        <h2 className="cuenta-titulo">Crea tu nueva contraseña</h2>
        <p className="cuenta-sub">
          {usuario?.nombre}, iniciaste sesión con una contraseña temporal. Debes reemplazarla antes de continuar.
        </p>
        <div className="cuenta-card">
          <FormularioCambioPassword obligatorio />
          <button type="button" className="btn btn-secundario btn-bloque" style={{ marginTop: 10 }} onClick={logout}>Cerrar sesión</button>
        </div>
      </div>
    </div>
  );
}

export default function ViewCuenta() {
  const { usuario, logout } = useAuth();
  if (!usuario) return null;

  return (
    <div className="cuenta-page">
      <div className="cuenta-wrap">
        <span className="cuenta-kicker">Mi cuenta</span>
        <h2 className="cuenta-titulo">{usuario.nombre}</h2>
        <p className="cuenta-sub">Gestiona tu acceso a Coraleum.</p>

        <div className="cuenta-grid">
          <div>
            <div className="cuenta-card">
              <h3>Datos de la cuenta</h3>
              <div style={{ display: 'grid', gap: 10, marginTop: 14, fontSize: 13 }}>
                <div><span className="ayuda" style={{ margin: 0 }}>Correo</span><div>{usuario.email}</div></div>
                <div><span className="ayuda" style={{ margin: 0 }}>Rol</span><div style={{ marginTop: 4 }}><BadgeRol rol={usuario.rol} /> {usuario.solicitud && usuario.rol === 'usuario' && <BadgeSolicitud estado={usuario.solicitud.estado} />}</div></div>
                <div><span className="ayuda" style={{ margin: 0 }}>Miembro desde</span><div>{formatearFecha(usuario.creado_en)}</div></div>
              </div>
              <div className="acciones" style={{ marginTop: 18 }}>
                <button type="button" className="btn btn-secundario" onClick={logout}>Cerrar sesión</button>
              </div>
            </div>
            <SolicitudInvestigador />
          </div>

          <div className="cuenta-card">
            <h3>Cambiar contraseña</h3>
            <p className="ayuda">Al cambiarla se cierran tus sesiones abiertas en otros dispositivos.</p>
            <FormularioCambioPassword />
          </div>
        </div>
      </div>
    </div>
  );
}
