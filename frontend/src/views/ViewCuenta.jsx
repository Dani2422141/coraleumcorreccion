import { useState } from 'react';
import { useAuth } from '../auth/AuthContext';
import { auth } from '../data/api';
import { BadgeRol, BadgeSolicitud, Campo, CampoPassword, Mensaje, formatearFecha, pistaPassword } from '../components/Formulario';
import { CampoCodigo, SeccionDosPasos } from '../components/DosPasos';
import { PoliticaContenido } from './ViewPrivacidad';

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

/** Derechos del titular: descargar y eliminar sus datos (Ley 1581 de 2012). */
function SeccionMisDatos({ onNavigate }) {
  const { usuario, setUsuario } = useAuth();
  const [eliminando, setEliminando] = useState(false);
  const [password, setPassword] = useState('');
  const [codigo, setCodigo] = useState('');
  const [confirmo, setConfirmo] = useState(false);
  const [error, setError] = useState('');
  const [enviando, setEnviando] = useState(false);

  async function descargar() {
    setError('');
    try {
      const datos = await auth.misDatos();
      const url = URL.createObjectURL(new Blob([JSON.stringify(datos, null, 2)], { type: 'application/json' }));
      const enlace = document.createElement('a');
      enlace.href = url;
      enlace.download = 'coraleum-mis-datos.json';
      enlace.click();
      URL.revokeObjectURL(url);
    } catch (err) {
      setError(err.message);
    }
  }

  async function eliminar(evento) {
    evento.preventDefault();
    setError('');
    setEnviando(true);
    try {
      await auth.eliminarCuenta(password, codigo);
      setUsuario(null);
      onNavigate?.('inicio');
    } catch (err) {
      setError(err.message);
      setEnviando(false);
    }
  }

  return (
    <div className="cuenta-card">
      <h3>Tus datos personales</h3>
      <p className="ayuda">
        Según la Ley 1581 de 2012 puedes conocer y suprimir tus datos.{' '}
        <button type="button" className="enlace" onClick={() => onNavigate?.('privacidad')}>Ver la política de datos</button>
      </p>
      <Mensaje tipo="error">{!eliminando && error}</Mensaje>
      {!eliminando ? (
        <div className="acciones">
          <button type="button" className="btn btn-secundario" onClick={descargar}>Descargar mis datos</button>
          <button type="button" className="btn btn-peligro" onClick={() => { setError(''); setEliminando(true); }}>Eliminar mi cuenta</button>
        </div>
      ) : (
        <form onSubmit={eliminar}>
          <Mensaje tipo="error">
            Esta acción es <strong>permanente</strong>: se borran tu cuenta, tu solicitud y tus datos personales, y se cierran
            todas tus sesiones. El registro de seguridad se conserva de forma anónima.
          </Mensaje>
          <Mensaje tipo="error">{error}</Mensaje>
          <CampoPassword etiqueta="Confirma tu contraseña" valor={password} onCambio={setPassword} autoFocus />
          {usuario.dos_pasos && <CampoCodigo valor={codigo} onCambio={setCodigo} autoFocus={false} />}
          <label className="acciones" style={{ fontSize: 13, marginBottom: 12 }}>
            <input type="checkbox" checked={confirmo} onChange={(e) => setConfirmo(e.target.checked)} /> Entiendo que no se puede deshacer
          </label>
          <div className="acciones">
            <button className="btn btn-peligro" type="submit" disabled={!confirmo || enviando}>{enviando ? 'Eliminando…' : 'Eliminar definitivamente'}</button>
            <button className="btn btn-secundario" type="button" onClick={() => { setEliminando(false); setPassword(''); setCodigo(''); setConfirmo(false); setError(''); }}>Cancelar</button>
          </div>
        </form>
      )}
    </div>
  );
}

/** Pantalla obligatoria si la persona no ha aceptado la política vigente. */
export function AceptarPoliticaObligatorio() {
  const { setUsuario, logout } = useAuth();
  const [error, setError] = useState('');
  const [acepto, setAcepto] = useState(false);

  async function aceptar() {
    setError('');
    try {
      const { usuario } = await auth.aceptarPolitica();
      setUsuario(usuario);
    } catch (err) {
      setError(err.message);
    }
  }

  return (
    <div className="cuenta-page">
      <div className="cuenta-wrap" style={{ maxWidth: 760 }}>
        <span className="cuenta-kicker">Protección de datos personales</span>
        <h2 className="cuenta-titulo">Antes de continuar</h2>
        <p className="cuenta-sub">Para seguir usando tu cuenta necesitamos tu autorización para el tratamiento de tus datos personales.</p>
        <div className="cuenta-card">
          <div className="modal-scroll"><PoliticaContenido /></div>
          <Mensaje tipo="error">{error}</Mensaje>
          <label className="consentimiento">
            <input type="checkbox" checked={acepto} onChange={(e) => setAcepto(e.target.checked)} />
            <span>He leído y autorizo el tratamiento de mis datos personales conforme a esta política y a la Ley 1581 de 2012.</span>
          </label>
          <div className="acciones">
            <button type="button" className="btn btn-primario" disabled={!acepto} onClick={aceptar}>Aceptar y continuar</button>
            <button type="button" className="btn btn-secundario" onClick={logout}>No acepto — cerrar sesión</button>
          </div>
          <p className="ayuda" style={{ marginTop: 12, marginBottom: 0 }}>
            Si no aceptas, puedes solicitar la eliminación de tu cuenta escribiendo al correo de contacto de la política.
          </p>
        </div>
      </div>
    </div>
  );
}

export default function ViewCuenta({ onNavigate }) {
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

          <div>
            <div className="cuenta-card">
              <h3>Cambiar contraseña</h3>
              <p className="ayuda">Al cambiarla se cierran tus sesiones abiertas en otros dispositivos.</p>
              <FormularioCambioPassword />
            </div>
            <SeccionDosPasos />
            <SeccionMisDatos onNavigate={onNavigate} />
          </div>
        </div>
      </div>
    </div>
  );
}
