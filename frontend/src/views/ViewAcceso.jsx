import { useState } from 'react';
import { useAuth } from '../auth/AuthContext';
import { auth } from '../data/api';
import { Campo, CampoPassword, Mensaje, pistaPassword } from '../components/Formulario';
import { CampoCodigo } from '../components/DosPasos';
import { PoliticaContenido } from './ViewPrivacidad';

function VentanaPolitica({ onCerrar }) {
  return (
    <div className="modal-fondo" role="dialog" aria-modal="true" aria-labelledby="titulo-politica" onClick={onCerrar}>
      <div className="cuenta-card modal-ancha" onClick={(e) => e.stopPropagation()}>
        <h3 id="titulo-politica">Política de tratamiento de datos personales</h3>
        <div className="modal-scroll"><PoliticaContenido /></div>
        <button type="button" className="btn btn-primario btn-bloque" onClick={onCerrar}>Cerrar</button>
      </div>
    </div>
  );
}

/** Segundo paso: código de la aplicación de autenticación. */
function SegundoPaso({ desafio, onCancelar, onExito }) {
  const { verificar2fa } = useAuth();
  const [codigo, setCodigo] = useState('');
  const [recuperacion, setRecuperacion] = useState(false);
  const [error, setError] = useState('');
  const [enviando, setEnviando] = useState(false);

  async function enviar(evento) {
    evento.preventDefault();
    setError('');
    setEnviando(true);
    try {
      onExito(await verificar2fa(desafio, codigo));
    } catch (err) {
      setError(err.message);
      setCodigo('');
    } finally {
      setEnviando(false);
    }
  }

  return (
    <form onSubmit={enviar}>
      <p className="ayuda">
        {recuperacion
          ? 'Escribe uno de los códigos de recuperación que guardaste al activar la verificación. Cada código sirve una sola vez.'
          : 'Abre tu aplicación de autenticación (Google Authenticator, Microsoft Authenticator…) y escribe el código de Coraleum.'}
      </p>
      <Mensaje tipo="error">{error}</Mensaje>
      <CampoCodigo key={recuperacion ? 'r' : 't'} valor={codigo} onCambio={setCodigo} recuperacion={recuperacion} />
      <button className="btn btn-primario btn-bloque" type="submit" disabled={enviando}>{enviando ? 'Verificando…' : 'Verificar'}</button>
      <div className="acciones" style={{ justifyContent: 'space-between', marginTop: 12 }}>
        <button type="button" className="btn btn-secundario btn-pequeno" onClick={() => { setRecuperacion((r) => !r); setCodigo(''); setError(''); }}>
          {recuperacion ? 'Usar el código del celular' : 'Usar un código de recuperación'}
        </button>
        <button type="button" className="btn btn-secundario btn-pequeno" onClick={onCancelar}>Cancelar</button>
      </div>
    </form>
  );
}

/** "Olvidé mi contraseña": la solicitud llega al administrador. */
function RecuperarPassword({ onVolver }) {
  const [email, setEmail] = useState('');
  const [respuesta, setRespuesta] = useState('');
  const [error, setError] = useState('');
  const [enviando, setEnviando] = useState(false);

  async function enviar(evento) {
    evento.preventDefault();
    setError('');
    setEnviando(true);
    try {
      setRespuesta((await auth.olvidePassword(email.trim())).mensaje);
    } catch (err) {
      setError(err.message);
    } finally {
      setEnviando(false);
    }
  }

  return (
    <div>
      {respuesta ? (
        <Mensaje tipo="ok">{respuesta}</Mensaje>
      ) : (
        <form onSubmit={enviar}>
          <p className="ayuda">
            Escribe el correo de tu cuenta. Un administrador recibirá la solicitud y te entregará una contraseña temporal
            por un canal seguro; al iniciar sesión deberás cambiarla.
          </p>
          <Mensaje tipo="error">{error}</Mensaje>
          <Campo etiqueta="Correo electrónico">
            <input type="email" value={email} onChange={(e) => setEmail(e.target.value)} autoComplete="email" maxLength={254} required autoFocus />
          </Campo>
          <button className="btn btn-primario btn-bloque" type="submit" disabled={enviando}>{enviando ? 'Enviando…' : 'Solicitar restablecimiento'}</button>
        </form>
      )}
      <button type="button" className="btn btn-secundario btn-bloque" style={{ marginTop: 10 }} onClick={onVolver}>Volver a iniciar sesión</button>
    </div>
  );
}

/** Inicio de sesión y registro. */
export default function ViewAcceso({ modoInicial = 'login', onExito }) {
  const { login, registro, aviso, setAviso } = useAuth();
  const [modo, setModo] = useState(modoInicial);
  const [nombre, setNombre] = useState('');
  const [email, setEmail] = useState('');
  const [password, setPassword] = useState('');
  const [confirmacion, setConfirmacion] = useState('');
  const [aceptaPolitica, setAceptaPolitica] = useState(false);
  const [verPolitica, setVerPolitica] = useState(false);
  const [desafio, setDesafio] = useState(null);
  const [error, setError] = useState('');
  const [enviando, setEnviando] = useState(false);

  function cambiarModo(nuevo) {
    setModo(nuevo);
    setError('');
    setPassword('');
    setConfirmacion('');
    setDesafio(null);
  }

  async function enviar(evento) {
    evento.preventDefault();
    setError('');
    setAviso('');
    if (modo === 'registro' && password !== confirmacion) {
      setError('Las contraseñas no coinciden.');
      return;
    }
    if (modo === 'registro' && !aceptaPolitica) {
      setError('Para crear la cuenta debes aceptar la política de tratamiento de datos personales.');
      return;
    }
    setEnviando(true);
    try {
      if (modo === 'login') {
        const resultado = await login(email.trim(), password);
        setPassword('');
        if (resultado.requiere2fa) setDesafio(resultado.desafio);
        else onExito?.(resultado.usuario, modo);
      } else {
        onExito?.(await registro(nombre.trim(), email.trim(), password, aceptaPolitica), modo);
      }
    } catch (err) {
      setError(err.message || 'No fue posible completar la operación.');
    } finally {
      setEnviando(false);
    }
  }

  const pista = pistaPassword(password);

  return (
    <div className="cuenta-page">
      {verPolitica && <VentanaPolitica onCerrar={() => setVerPolitica(false)} />}
      <div className="cuenta-wrap estrecho">
        <span className="cuenta-kicker">Cuenta Coraleum</span>
        <h2 className="cuenta-titulo">{desafio ? 'Verificación en dos pasos' : modo === 'recuperar' ? 'Restablecer contraseña' : modo === 'login' ? 'Iniciar sesión' : 'Crear una cuenta'}</h2>
        <p className="cuenta-sub">
          {desafio
            ? 'Tu contraseña es correcta. Falta un último paso para proteger tu cuenta.'
            : modo === 'login'
              ? 'Accede al Explorador Térmico y al registro histórico si tu cuenta de investigador está aprobada.'
              : 'Con una cuenta puedes solicitar acceso de investigador al Explorador Térmico y al histórico de indicadores.'}
        </p>

        <div className="cuenta-card">
          {desafio ? (
            <SegundoPaso desafio={desafio} onCancelar={() => cambiarModo('login')} onExito={(u) => onExito?.(u, 'login')} />
          ) : modo === 'recuperar' ? (
            <RecuperarPassword onVolver={() => cambiarModo('login')} />
          ) : (
            <>
              <div className="tabs" role="tablist">
                <button type="button" role="tab" aria-selected={modo === 'login'} onClick={() => cambiarModo('login')}>Iniciar sesión</button>
                <button type="button" role="tab" aria-selected={modo === 'registro'} onClick={() => cambiarModo('registro')}>Registrarse</button>
              </div>

              <Mensaje tipo="info">{aviso}</Mensaje>
              <Mensaje tipo="error">{error}</Mensaje>

              <form onSubmit={enviar}>
                {modo === 'registro' && (
                  <Campo etiqueta="Nombre completo">
                    <input value={nombre} onChange={(e) => setNombre(e.target.value)} autoComplete="name" minLength={2} maxLength={80} required />
                  </Campo>
                )}
                <Campo etiqueta="Correo electrónico">
                  <input type="email" value={email} onChange={(e) => setEmail(e.target.value)} autoComplete="email" maxLength={254} required autoFocus />
                </Campo>
                <CampoPassword
                  etiqueta="Contraseña"
                  valor={password}
                  onCambio={setPassword}
                  autoComplete={modo === 'login' ? 'current-password' : 'new-password'}
                  pista={modo === 'registro' ? pista.texto : undefined}
                  pistaOk={pista.ok}
                />
                {modo === 'registro' && (
                  <>
                    <CampoPassword
                      etiqueta="Repite la contraseña"
                      valor={confirmacion}
                      onCambio={setConfirmacion}
                      autoComplete="new-password"
                      pista={confirmacion && confirmacion !== password ? 'No coincide.' : undefined}
                    />
                    <label className="consentimiento">
                      <input type="checkbox" checked={aceptaPolitica} onChange={(e) => setAceptaPolitica(e.target.checked)} required />
                      <span>
                        Autorizo el tratamiento de mis datos personales (nombre, correo y registro de actividad) para las
                        finalidades descritas en la{' '}
                        <button type="button" className="enlace" onClick={() => setVerPolitica(true)}>política de tratamiento de datos</button>,
                        conforme a la Ley 1581 de 2012.
                      </span>
                    </label>
                  </>
                )}
                <button className="btn btn-primario btn-bloque" type="submit" disabled={enviando || (modo === 'registro' && !aceptaPolitica)}>
                  {enviando ? 'Procesando…' : modo === 'login' ? 'Entrar' : 'Crear cuenta'}
                </button>
              </form>

              {modo === 'login' && (
                <p className="ayuda" style={{ marginTop: 14, marginBottom: 0, textAlign: 'center' }}>
                  <button type="button" className="enlace" onClick={() => cambiarModo('recuperar')}>¿Olvidaste tu contraseña?</button>
                </p>
              )}
            </>
          )}
        </div>
      </div>
    </div>
  );
}
