import { useState } from 'react';
import { useAuth } from '../auth/AuthContext';
import { auth } from '../data/api';
import { Campo, CampoPassword, Mensaje } from './Formulario';

/** Campo para el código de 6 dígitos (o de recuperación). */
export function CampoCodigo({ valor, onCambio, recuperacion = false, autoFocus = true }) {
  return (
    <Campo etiqueta={recuperacion ? 'Código de recuperación' : 'Código de 6 dígitos'}>
      <input
        value={valor}
        onChange={(e) => onCambio(e.target.value)}
        inputMode={recuperacion ? 'text' : 'numeric'}
        autoComplete="one-time-code"
        placeholder={recuperacion ? 'XXXXX-XXXXX' : '123456'}
        maxLength={recuperacion ? 11 : 6}
        pattern={recuperacion ? undefined : '[0-9]{6}'}
        required
        autoFocus={autoFocus}
        style={{ letterSpacing: recuperacion ? '0.08em' : '0.35em', fontFamily: "'JetBrains Mono', monospace", fontSize: 18 }}
      />
    </Campo>
  );
}

/** Muestra los códigos de recuperación una sola vez. */
export function CodigosRecuperacion({ codigos, onListo }) {
  const [guardados, setGuardados] = useState(false);
  const texto = `Códigos de recuperación de Coraleum (cada uno sirve una sola vez):\n\n${codigos.join('\n')}\n`;

  function descargar() {
    const url = URL.createObjectURL(new Blob([texto], { type: 'text/plain;charset=utf-8' }));
    const enlace = document.createElement('a');
    enlace.href = url;
    enlace.download = 'coraleum-codigos-recuperacion.txt';
    enlace.click();
    URL.revokeObjectURL(url);
  }

  return (
    <div>
      <Mensaje tipo="info">
        Guarda estos códigos en un lugar seguro. Si pierdes el celular, cada código te permite entrar <strong>una vez</strong>.
        No se volverán a mostrar.
      </Mensaje>
      <div className="codigos-grid">{codigos.map((c) => <code key={c}>{c}</code>)}</div>
      <div className="acciones" style={{ margin: '14px 0' }}>
        <button type="button" className="btn btn-secundario btn-pequeno" onClick={descargar}>Descargar .txt</button>
        <button type="button" className="btn btn-secundario btn-pequeno" onClick={() => navigator.clipboard?.writeText(texto)}>Copiar</button>
      </div>
      <label className="acciones" style={{ fontSize: 13, marginBottom: 12 }}>
        <input type="checkbox" checked={guardados} onChange={(e) => setGuardados(e.target.checked)} /> Ya guardé mis códigos
      </label>
      <button type="button" className="btn btn-primario btn-bloque" disabled={!guardados} onClick={onListo}>Terminar</button>
    </div>
  );
}

/** Asistente para activar la verificación en dos pasos. */
export function ConfigurarDosPasos({ onActivado }) {
  const { setUsuario } = useAuth();
  const [paso, setPaso] = useState('password');
  const [password, setPassword] = useState('');
  const [qr, setQr] = useState(null);
  const [codigo, setCodigo] = useState('');
  const [codigos, setCodigos] = useState(null);
  const [usuarioNuevo, setUsuarioNuevo] = useState(null);
  const [error, setError] = useState('');
  const [enviando, setEnviando] = useState(false);

  async function iniciar(evento) {
    evento.preventDefault();
    setError('');
    setEnviando(true);
    try {
      setQr(await auth.iniciar2fa(password));
      setPassword('');
      setPaso('escanear');
    } catch (err) {
      setError(err.message);
    } finally {
      setEnviando(false);
    }
  }

  async function activar(evento) {
    evento.preventDefault();
    setError('');
    setEnviando(true);
    try {
      const r = await auth.activar2fa(codigo);
      setCodigos(r.codigos_recuperacion);
      setUsuarioNuevo(r.usuario);
      setPaso('codigos');
    } catch (err) {
      setError(err.message);
    } finally {
      setEnviando(false);
    }
  }

  function terminar() {
    setUsuario(usuarioNuevo);
    onActivado?.(usuarioNuevo);
  }

  return (
    <div>
      <Mensaje tipo="error">{error}</Mensaje>
      {paso === 'password' && (
        <form onSubmit={iniciar}>
          <p className="ayuda">
            Necesitas una aplicación de autenticación en tu celular: Google Authenticator, Microsoft Authenticator o Authy
            (gratuitas). Primero confirma tu contraseña.
          </p>
          <CampoPassword etiqueta="Contraseña actual" valor={password} onCambio={setPassword} autoFocus />
          <button className="btn btn-primario" type="submit" disabled={enviando}>{enviando ? 'Generando…' : 'Continuar'}</button>
        </form>
      )}
      {paso === 'escanear' && qr && (
        <form onSubmit={activar}>
          <ol className="pasos-2fa">
            <li>Abre la aplicación de autenticación y toca <strong>+</strong> → <strong>Escanear código QR</strong>.</li>
            <li>Escanea este código:</li>
          </ol>
          <div className="qr-2fa"><img src={qr.qr} alt="Código QR para la aplicación de autenticación" width="180" height="180" /></div>
          <p className="ayuda" style={{ textAlign: 'center' }}>
            ¿No puedes escanear? Escribe esta clave en la app:<br />
            <code className="clave-manual">{qr.clave_manual}</code>
          </p>
          <ol className="pasos-2fa" start={3}><li>Escribe el código de 6 dígitos que muestra la app:</li></ol>
          <CampoCodigo valor={codigo} onCambio={setCodigo} />
          <button className="btn btn-primario btn-bloque" type="submit" disabled={enviando || codigo.length < 6}>
            {enviando ? 'Verificando…' : 'Activar verificación en dos pasos'}
          </button>
        </form>
      )}
      {paso === 'codigos' && codigos && <CodigosRecuperacion codigos={codigos} onListo={terminar} />}
    </div>
  );
}

/** Sección de "Mi cuenta" para gestionar la verificación en dos pasos. */
export function SeccionDosPasos() {
  const { usuario, setUsuario } = useAuth();
  const [modo, setModo] = useState(null);
  const [password, setPassword] = useState('');
  const [codigo, setCodigo] = useState('');
  const [codigos, setCodigos] = useState(null);
  const [error, setError] = useState('');
  const [ok, setOk] = useState('');
  const esAdmin = usuario.rol === 'admin';

  function cerrar() {
    setModo(null); setPassword(''); setCodigo(''); setError(''); setCodigos(null);
  }

  async function confirmar(evento) {
    evento.preventDefault();
    setError('');
    try {
      if (modo === 'desactivar') {
        const r = await auth.desactivar2fa(password, codigo);
        setUsuario(r.usuario);
        setOk('Verificación en dos pasos desactivada.');
        cerrar();
      } else {
        const r = await auth.regenerarCodigos(password, codigo);
        setCodigos(r.codigos_recuperacion);
        setUsuario(r.usuario);
      }
    } catch (err) {
      setError(err.message);
    }
  }

  return (
    <div className="cuenta-card">
      <h3>Verificación en dos pasos</h3>
      <p className="ayuda">
        Además de la contraseña, se pide un código de tu celular al iniciar sesión.
        {esAdmin ? ' Es obligatoria para administradores.' : ' Recomendada para todas las cuentas.'}
      </p>
      <Mensaje tipo="ok">{ok}</Mensaje>

      {!usuario.dos_pasos && modo !== 'activar' && (
        <button type="button" className="btn btn-primario" onClick={() => { setOk(''); setModo('activar'); }}>Activar</button>
      )}
      {!usuario.dos_pasos && modo === 'activar' && <ConfigurarDosPasos onActivado={() => { setModo(null); setOk('Verificación en dos pasos activada.'); }} />}

      {usuario.dos_pasos && !modo && (
        <>
          <p style={{ fontSize: 13, margin: '0 0 12px' }}>
            <span className="badge badge-aprobada">Activa</span>{' '}
            <span className="ayuda">Códigos de recuperación disponibles: {usuario.codigos_recuperacion_restantes ?? '—'}</span>
          </p>
          <div className="acciones">
            <button type="button" className="btn btn-secundario btn-pequeno" onClick={() => { setOk(''); setModo('regenerar'); }}>Nuevos códigos de recuperación</button>
            {!esAdmin && <button type="button" className="btn btn-peligro btn-pequeno" onClick={() => { setOk(''); setModo('desactivar'); }}>Desactivar</button>}
          </div>
        </>
      )}

      {usuario.dos_pasos && (modo === 'regenerar' || modo === 'desactivar') && (
        codigos ? <CodigosRecuperacion codigos={codigos} onListo={() => { cerrar(); setOk('Códigos nuevos guardados. Los anteriores ya no sirven.'); }} /> : (
          <form onSubmit={confirmar}>
            <Mensaje tipo="error">{error}</Mensaje>
            <CampoPassword etiqueta="Contraseña" valor={password} onCambio={setPassword} autoFocus />
            <CampoCodigo valor={codigo} onCambio={setCodigo} autoFocus={false} />
            <div className="acciones">
              <button className={`btn ${modo === 'desactivar' ? 'btn-peligro' : 'btn-primario'}`} type="submit">
                {modo === 'desactivar' ? 'Desactivar' : 'Generar códigos nuevos'}
              </button>
              <button className="btn btn-secundario" type="button" onClick={cerrar}>Cancelar</button>
            </div>
          </form>
        )
      )}
    </div>
  );
}
