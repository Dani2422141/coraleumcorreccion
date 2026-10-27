import { useCallback, useEffect, useState } from 'react';
import { useAuth } from '../auth/AuthContext';
import { admin } from '../data/api';
import { LoadingState } from '../components/LoadingState';
import { BadgeRol, BadgeSolicitud, Mensaje, formatearFecha } from '../components/Formulario';
import { ConfigurarDosPasos } from '../components/DosPasos';

const NOMBRES_EVENTO = {
  registro: 'Registro',
  login: 'Inicio de sesión',
  logout: 'Cierre de sesión',
  cuenta_bloqueada: 'Cuenta bloqueada',
  refresh_reutilizado: 'Reutilización de sesión',
  cambio_password: 'Cambio de contraseña',
  solicitud_investigador: 'Solicitud de investigador',
  solicitud_aprobada: 'Solicitud aprobada',
  solicitud_rechazada: 'Solicitud rechazada',
  usuario_actualizado: 'Usuario actualizado',
  password_restablecida: 'Contraseña restablecida',
  acceso_denegado: 'Acceso denegado',
  login_primer_paso: 'Contraseña correcta (falta 2FA)',
  '2fa_activado': '2FA activado',
  '2fa_desactivado': '2FA desactivado',
  '2fa_restablecido': '2FA restablecido por admin',
  '2fa_codigos_regenerados': 'Códigos de recuperación nuevos',
  politica_aceptada: 'Política de datos aceptada',
  datos_descargados: 'Descarga de datos personales',
  cuenta_eliminada: 'Cuenta eliminada por el titular',
};

function ClaveTemporal({ datos, onCerrar }) {
  const [copiada, setCopiada] = useState(false);
  if (!datos) return null;
  async function copiar() {
    try {
      await navigator.clipboard.writeText(datos.clave);
      setCopiada(true);
    } catch (_) { /* el usuario puede copiarla a mano */ }
  }
  return (
    <div className="modal-fondo" role="dialog" aria-modal="true" aria-labelledby="titulo-clave">
      <div className="cuenta-card">
        <h3 id="titulo-clave">Contraseña temporal de {datos.nombre}</h3>
        <p className="ayuda">Entrégala a la persona por un canal seguro. <strong>Solo se muestra esta vez.</strong> Al iniciar sesión se le pedirá crear una nueva.</p>
        <div className="clave-temporal"><span>{datos.clave}</span><button type="button" className="btn btn-secundario btn-pequeno" onClick={copiar}>{copiada ? 'Copiada' : 'Copiar'}</button></div>
        <button type="button" className="btn btn-primario btn-bloque" onClick={onCerrar}>Listo</button>
      </div>
    </div>
  );
}

function Solicitudes({ usuarios, onCambio }) {
  const [comentarios, setComentarios] = useState({});
  const [error, setError] = useState('');
  const [ocupado, setOcupado] = useState(null);
  const pendientes = usuarios.filter((u) => u.solicitud?.estado === 'pendiente');

  async function decidir(u, decision) {
    setError('');
    setOcupado(u.id);
    try {
      await admin.decidirSolicitud(u.id, decision, comentarios[u.id]);
      onCambio();
    } catch (err) {
      setError(err.message);
    } finally {
      setOcupado(null);
    }
  }

  if (!pendientes.length) return <div className="vacio">No hay solicitudes pendientes.</div>;
  return (
    <div>
      <Mensaje tipo="error">{error}</Mensaje>
      {pendientes.map((u) => (
        <div className="solicitud" key={u.id}>
          <div className="cabecera">
            <div>
              <strong>{u.nombre}</strong> <span className="ayuda" style={{ margin: 0 }}>· {u.email}</span>
              <div className="ayuda" style={{ margin: '2px 0 0' }}>{u.solicitud.institucion} · {formatearFecha(u.solicitud.fecha)}</div>
            </div>
            <BadgeSolicitud estado="pendiente" />
          </div>
          <p className="motivo">{u.solicitud.motivo}</p>
          <div className="acciones">
            <input
              className="control"
              style={{ flex: '1 1 220px', width: 'auto' }}
              placeholder="Comentario (opcional, se muestra al usuario)"
              maxLength={300}
              value={comentarios[u.id] || ''}
              onChange={(e) => setComentarios((c) => ({ ...c, [u.id]: e.target.value }))}
            />
            <button type="button" className="btn btn-primario btn-pequeno" disabled={ocupado === u.id} onClick={() => decidir(u, 'aprobar')}>Aprobar</button>
            <button type="button" className="btn btn-peligro btn-pequeno" disabled={ocupado === u.id} onClick={() => decidir(u, 'rechazar')}>Rechazar</button>
          </div>
        </div>
      ))}
    </div>
  );
}

function Usuarios({ usuarios, onCambio, miId }) {
  const [busqueda, setBusqueda] = useState('');
  const [error, setError] = useState('');
  const [clave, setClave] = useState(null);
  const filtro = busqueda.trim().toLowerCase();
  const lista = filtro ? usuarios.filter((u) => `${u.nombre} ${u.email}`.toLowerCase().includes(filtro)) : usuarios;

  async function ejecutar(accion) {
    setError('');
    try {
      await accion();
      onCambio();
    } catch (err) {
      setError(err.message);
    }
  }

  function cambiarRol(u, rol) {
    if (rol === 'admin' && !window.confirm(`¿Dar permisos de ADMINISTRADOR a ${u.nombre}? Podrá gestionar todas las cuentas.`)) return;
    ejecutar(() => admin.actualizar(u.id, { rol }));
  }

  function alternarActivo(u) {
    const texto = u.activo ? `¿Desactivar la cuenta de ${u.nombre}? Se cerrarán sus sesiones de inmediato.` : `¿Reactivar la cuenta de ${u.nombre}?`;
    if (window.confirm(texto)) ejecutar(() => admin.actualizar(u.id, { activo: !u.activo }));
  }

  function restablecer2fa(u) {
    if (!window.confirm(`¿Quitar la verificación en dos pasos de ${u.nombre}? Úselo solo si perdió el celular y sus códigos. Se cerrarán sus sesiones.`)) return;
    ejecutar(() => admin.restablecer2fa(u.id));
  }

  function restablecer(u) {
    if (!window.confirm(`¿Restablecer la contraseña de ${u.nombre}? Se cerrarán sus sesiones.`)) return;
    ejecutar(async () => {
      const r = await admin.restablecerPassword(u.id);
      setClave({ nombre: u.nombre, clave: r.password_temporal });
    });
  }

  return (
    <div>
      <ClaveTemporal datos={clave} onCerrar={() => setClave(null)} />
      <Mensaje tipo="error">{error}</Mensaje>
      <input className="control" style={{ marginBottom: 14 }} placeholder="Buscar por nombre o correo" value={busqueda} onChange={(e) => setBusqueda(e.target.value)} maxLength={100} />
      <div className="tabla-scroll">
        <table className="tabla">
          <thead>
            <tr><th>Usuario</th><th>Rol</th><th>Estado</th><th>2FA</th><th>Último acceso</th><th>Acciones</th></tr>
          </thead>
          <tbody>
            {lista.map((u) => {
              const soyYo = u.id === miId;
              return (
                <tr key={u.id}>
                  <td>{u.nombre}{soyYo && ' (tú)'}<span className="secundario">{u.email}</span></td>
                  <td>
                    {soyYo ? <BadgeRol rol={u.rol} /> : (
                      <select className="control" value={u.rol} onChange={(e) => cambiarRol(u, e.target.value)} aria-label={`Rol de ${u.nombre}`}>
                        <option value="usuario">Usuario</option>
                        <option value="investigador">Investigador</option>
                        <option value="admin">Administrador</option>
                      </select>
                    )}
                  </td>
                  <td>
                    {u.activo ? <span className="badge badge-aprobada">Activa</span> : <span className="badge badge-inactivo">Desactivada</span>}
                    {u.debe_cambiar_password && <span className="secundario">Clave temporal</span>}
                  </td>
                  <td>{u.dos_pasos ? <span className="badge badge-aprobada">Activa</span> : <span className={`badge ${u.rol === 'admin' ? 'badge-pendiente' : 'badge-usuario'}`}>{u.rol === 'admin' ? 'Pendiente' : 'No'}</span>}</td>
                  <td>{formatearFecha(u.ultimo_acceso)}</td>
                  <td>
                    {!soyYo && (
                      <div className="acciones">
                        <button type="button" className="btn btn-secundario btn-pequeno" onClick={() => restablecer(u)}>Restablecer clave</button>
                        {u.dos_pasos && <button type="button" className="btn btn-secundario btn-pequeno" onClick={() => restablecer2fa(u)}>Quitar 2FA</button>}
                        <button type="button" className={`btn btn-pequeno ${u.activo ? 'btn-peligro' : 'btn-secundario'}`} onClick={() => alternarActivo(u)}>
                          {u.activo ? 'Desactivar' : 'Activar'}
                        </button>
                      </div>
                    )}
                  </td>
                </tr>
              );
            })}
          </tbody>
        </table>
        {!lista.length && <div className="vacio">Sin resultados.</div>}
      </div>
    </div>
  );
}

function Auditoria() {
  const [eventos, setEventos] = useState(null);
  const [soloFallidos, setSoloFallidos] = useState(false);
  const [error, setError] = useState('');

  useEffect(() => {
    let cancelado = false;
    setEventos(null);
    admin.auditoria(soloFallidos)
      .then((r) => { if (!cancelado) setEventos(r.eventos); })
      .catch((err) => { if (!cancelado) setError(err.message); });
    return () => { cancelado = true; };
  }, [soloFallidos]);

  const detalle = (d) => (d == null ? '' : typeof d === 'string' ? d : Object.entries(d).map(([k, v]) => `${k}: ${Array.isArray(v) ? v.join(' → ') : v}`).join(' · '));

  return (
    <div>
      <Mensaje tipo="error">{error}</Mensaje>
      <label className="acciones" style={{ marginBottom: 12, fontSize: 13 }}>
        <input type="checkbox" checked={soloFallidos} onChange={(e) => setSoloFallidos(e.target.checked)} /> Solo intentos fallidos o denegados
      </label>
      {!eventos ? <LoadingState message="Cargando auditoría…" /> : (
        <div className="tabla-scroll">
          <table className="tabla">
            <thead><tr><th>Fecha</th><th>Evento</th><th>Cuenta</th><th>IP</th><th>Detalle</th></tr></thead>
            <tbody>
              {eventos.map((e, i) => (
                <tr key={i}>
                  <td>{formatearFecha(e.fecha)}</td>
                  <td>{e.exito ? '✓' : '✗'} {NOMBRES_EVENTO[e.evento] || e.evento}</td>
                  <td>{e.email || '—'}</td>
                  <td>{e.ip || '—'}</td>
                  <td><span className="secundario">{detalle(e.detalle)}</span></td>
                </tr>
              ))}
            </tbody>
          </table>
          {!eventos.length && <div className="vacio">Sin eventos.</div>}
        </div>
      )}
    </div>
  );
}

export default function ViewAdmin({ onPendientes }) {
  const { usuario } = useAuth();
  const [pestana, setPestana] = useState('solicitudes');
  const [datos, setDatos] = useState(null);
  const [error, setError] = useState('');
  const [falta2fa, setFalta2fa] = useState(false);

  const cargar = useCallback(async () => {
    try {
      const r = await admin.usuarios();
      setDatos(r);
      onPendientes?.(r.pendientes);
      setError('');
      setFalta2fa(false);
    } catch (err) {
      if (err.accion === 'configurar-2fa') setFalta2fa(true);
      else setError(err.message);
    }
  }, [onPendientes]);

  useEffect(() => { cargar(); }, [cargar]);

  if (falta2fa) {
    return (
      <div className="cuenta-page">
        <div className="cuenta-wrap estrecho">
          <span className="cuenta-kicker">Administración</span>
          <h2 className="cuenta-titulo">Activa la verificación en dos pasos</h2>
          <p className="cuenta-sub">
            Las cuentas de administrador pueden cambiar roles y ver la actividad de todos los usuarios, por eso deben
            proteger su acceso con un código del celular además de la contraseña.
          </p>
          <div className="cuenta-card"><ConfigurarDosPasos onActivado={cargar} /></div>
        </div>
      </div>
    );
  }

  return (
    <div className="cuenta-page">
      <div className="cuenta-wrap">
        <span className="cuenta-kicker">Administración</span>
        <h2 className="cuenta-titulo">Usuarios y accesos</h2>
        <p className="cuenta-sub">Aprueba investigadores, gestiona roles y revisa la actividad de seguridad.</p>

        <div className="tabs" role="tablist">
          <button type="button" role="tab" aria-selected={pestana === 'solicitudes'} onClick={() => setPestana('solicitudes')}>
            Solicitudes{datos?.pendientes ? <span className="contador">{datos.pendientes}</span> : null}
          </button>
          <button type="button" role="tab" aria-selected={pestana === 'usuarios'} onClick={() => setPestana('usuarios')}>Usuarios</button>
          <button type="button" role="tab" aria-selected={pestana === 'auditoria'} onClick={() => setPestana('auditoria')}>Auditoría</button>
        </div>

        <div className="cuenta-card">
          <Mensaje tipo="error">{error}</Mensaje>
          {pestana === 'auditoria' ? <Auditoria /> : !datos ? <LoadingState message="Cargando usuarios…" /> : pestana === 'solicitudes'
            ? <Solicitudes usuarios={datos.usuarios} onCambio={cargar} />
            : <Usuarios usuarios={datos.usuarios} onCambio={cargar} miId={usuario?.id} />}
        </div>
      </div>
    </div>
  );
}
