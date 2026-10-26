import { useState } from 'react';
import { useAuth } from '../auth/AuthContext';
import { Campo, CampoPassword, Mensaje, pistaPassword } from '../components/Formulario';

/** Inicio de sesión y registro. */
export default function ViewAcceso({ modoInicial = 'login', onExito }) {
  const { login, registro, aviso, setAviso } = useAuth();
  const [modo, setModo] = useState(modoInicial);
  const [nombre, setNombre] = useState('');
  const [email, setEmail] = useState('');
  const [password, setPassword] = useState('');
  const [confirmacion, setConfirmacion] = useState('');
  const [error, setError] = useState('');
  const [enviando, setEnviando] = useState(false);

  function cambiarModo(nuevo) {
    setModo(nuevo);
    setError('');
    setPassword('');
    setConfirmacion('');
  }

  async function enviar(evento) {
    evento.preventDefault();
    setError('');
    setAviso('');
    if (modo === 'registro' && password !== confirmacion) {
      setError('Las contraseñas no coinciden.');
      return;
    }
    setEnviando(true);
    try {
      const usuario = modo === 'login'
        ? await login(email.trim(), password)
        : await registro(nombre.trim(), email.trim(), password);
      onExito?.(usuario, modo);
    } catch (err) {
      setError(err.message || 'No fue posible completar la operación.');
    } finally {
      setEnviando(false);
    }
  }

  const pista = pistaPassword(password);

  return (
    <div className="cuenta-page">
      <div className="cuenta-wrap estrecho">
        <span className="cuenta-kicker">Cuenta Coraleum</span>
        <h2 className="cuenta-titulo">{modo === 'login' ? 'Iniciar sesión' : 'Crear una cuenta'}</h2>
        <p className="cuenta-sub">
          {modo === 'login'
            ? 'Accede al Explorador Térmico y al registro histórico si tu cuenta de investigador está aprobada.'
            : 'Con una cuenta puedes solicitar acceso de investigador al Explorador Térmico y al histórico de indicadores.'}
        </p>

        <div className="cuenta-card">
          <div className="tabs" role="tablist">
            <button type="button" role="tab" aria-selected={modo === 'login'} onClick={() => cambiarModo('login')}>Iniciar sesión</button>
            <button type="button" role="tab" aria-selected={modo === 'registro'} onClick={() => cambiarModo('registro')}>Registrarse</button>
          </div>

          <Mensaje tipo="info">{aviso}</Mensaje>
          <Mensaje tipo="error">{error}</Mensaje>

          <form onSubmit={enviar} noValidate={false}>
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
              <CampoPassword
                etiqueta="Repite la contraseña"
                valor={confirmacion}
                onCambio={setConfirmacion}
                autoComplete="new-password"
                pista={confirmacion && confirmacion !== password ? 'No coincide.' : undefined}
              />
            )}
            <button className="btn btn-primario btn-bloque" type="submit" disabled={enviando}>
              {enviando ? 'Procesando…' : modo === 'login' ? 'Entrar' : 'Crear cuenta'}
            </button>
          </form>

          {modo === 'login' && (
            <p className="ayuda" style={{ marginTop: 14, marginBottom: 0, textAlign: 'center' }}>
              ¿Olvidaste tu contraseña? Pide al administrador de Coraleum que la restablezca.
            </p>
          )}
        </div>
      </div>
    </div>
  );
}
