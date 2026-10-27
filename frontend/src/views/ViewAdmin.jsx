import { useCallback, useEffect, useState } from 'react';
import { useAuth } from '../auth/AuthContext';
import { admin } from '../data/api';
import { LoadingState } from '../components/LoadingState';
import { BadgesRoles, BadgeSolicitud, Campo, CampoPassword, Mensaje, NOMBRES_PERMISOS, formatearFecha, pistaPassword } from '../components/Formulario';
import { ConfigurarDosPasos } from '../components/DosPasos';

const NOMBRES_EVENTO = {
  registro: 'Registro',
  login: 'Inicio de sesión',
  logout: 'Cierre de sesión',
  cuenta_bloqueada: 'Cuenta bloqueada',
  refresh_reutilizado: 'Reutilización de sesión',
  sesion_expirada: 'Sesión cerrada automáticamente',
  cambio_password: 'Cambio de contraseña',
  solicitud_investigador: 'Solicitud de investigador',
  solicitud_aprobada: 'Solicitud aprobada',
  solicitud_rechazada: 'Solicitud rechazada',
  usuario_actualizado: 'Usuario actualizado (roles o estado)',
  password_restablecida: 'Contraseña restablecida por admin',
  recuperacion_solicitada: '"Olvidé mi contraseña"',
  recuperacion_descartada: 'Solicitud de contraseña descartada',
  rol_creado: 'Rol creado',
  rol_actualizado: 'Rol modificado',
  rol_eliminado: 'Rol eliminado',
  configuracion_actualizada: 'Configuración de sesión cambiada',
  acceso_denegado: 'Acceso denegado',
  login_primer_paso: 'Contraseña correcta (falta 2FA)',
  '2fa_activado': '2FA activado',
  '2fa_desactivado': '2FA desactivado',
  '2fa_restablecido': '2FA restablecido por admin',
  '2fa_codigos_regenerados': 'Códigos de recuperación nuevos',
  politica_aceptada: 'Política de datos aceptada',
  datos_descargados: 'Descarga de datos personales',
  cuenta_eliminada: 'Cuenta eliminada por el titular',
  sesion_reemplazada: 'Sesión cerrada por inicio en otro navegador',
  sesiones_cerradas: 'Sesiones cerradas por el titular',
  cambio_email: 'Cambio de correo',
  archivo_cargado: 'Archivo cargado',
  archivo_rechazado: 'Archivo rechazado',
  soporte_descargado: 'Soporte descargado',
  fallo_simulado: 'Fallo simulado (prueba)',
};

const NOMBRES_CAMPO = {
  token_minutos: 'vigencia del token (min)',
  inactividad_minutos: 'inactividad (min)',
  maxima_horas: 'duración máxima (h)',
  sesiones_simultaneas: 'sesiones simultáneas',
  cerradas: 'cerradas',
  nueva: 'nueva',
  limite: 'límite',
  archivo: 'archivo',
  motivo: 'motivo',
  tamano: 'bytes',
  tipo_declarado: 'tipo declarado',
  anterior: 'antes',
  nuevo: 'ahora',
  soporte: 'soporte',
};

function Modal({ titulo, children, onCerrar, ancho = false }) {
  return (
    <div className="modal-fondo" role="dialog" aria-modal="true" aria-label={titulo} onClick={onCerrar}>
      <div className={`cuenta-card ${ancho ? 'modal-ancha' : ''}`} onClick={(e) => e.stopPropagation()}>
        <h3>{titulo}</h3>
        {children}
      </div>
    </div>
  );
}

function ClaveTemporal({ datos, onCerrar }) {
  const [copiada, setCopiada] = useState(false);
  async function copiar() {
    try {
      await navigator.clipboard.writeText(datos.clave);
      setCopiada(true);
    } catch (_) { /* el usuario puede copiarla a mano */ }
  }
  return (
    <Modal titulo={`Contraseña temporal de ${datos.nombre}`} onCerrar={onCerrar}>
      <p className="ayuda">Entrégala a la persona por un canal seguro. <strong>Solo se muestra esta vez.</strong> Al iniciar sesión se le pedirá crear una nueva.</p>
      <div className="clave-temporal"><span>{datos.clave}</span><button type="button" className="btn btn-secundario btn-pequeno" onClick={copiar}>{copiada ? 'Copiada' : 'Copiar'}</button></div>
      <button type="button" className="btn btn-primario btn-bloque" onClick={onCerrar}>Listo</button>
    </Modal>
  );
}

/** Restablecer la contraseña de otra cuenta: generada o escrita por el admin. */
function RestablecerPassword({ usuario, onCerrar, onListo }) {
  const [modo, setModo] = useState('generar');
  const [password, setPassword] = useState('');
  const [error, setError] = useState('');
  const [temporal, setTemporal] = useState(null);
  const [enviando, setEnviando] = useState(false);

  async function confirmar(evento) {
    evento.preventDefault();
    setError('');
    setEnviando(true);
    try {
      if (modo === 'generar') {
        const r = await admin.restablecerPassword(usuario.id);
        setTemporal({ nombre: usuario.nombre, clave: r.password_temporal });
      } else {
        await admin.establecerPassword(usuario.id, password);
        onListo(`Contraseña de ${usuario.nombre} actualizada. Deberá cambiarla al iniciar sesión.`);
      }
    } catch (err) {
      setError(err.message);
    } finally {
      setEnviando(false);
    }
  }

  if (temporal) return <ClaveTemporal datos={temporal} onCerrar={() => onListo('')} />;
  const pista = pistaPassword(password);
  return (
    <Modal titulo={`Restablecer la contraseña de ${usuario.nombre}`} onCerrar={onCerrar}>
      <p className="ayuda">Se cerrarán sus sesiones abiertas y deberá crear una contraseña nueva al entrar.</p>
      <div className="tabs" role="tablist">
        <button type="button" role="tab" aria-selected={modo === 'generar'} onClick={() => { setModo('generar'); setError(''); }}>Generar automáticamente</button>
        <button type="button" role="tab" aria-selected={modo === 'escribir'} onClick={() => { setModo('escribir'); setError(''); }}>Escribir una contraseña</button>
      </div>
      <Mensaje tipo="error">{error}</Mensaje>
      <form onSubmit={confirmar}>
        {modo === 'escribir' && (
          <CampoPassword etiqueta="Nueva contraseña" valor={password} onCambio={setPassword} autoComplete="new-password" pista={pista.texto} pistaOk={pista.ok} autoFocus />
        )}
        {modo === 'escribir' && <p className="ayuda">Se aplica la misma política de contraseñas que a cualquier usuario.</p>}
        <div className="acciones">
          <button className="btn btn-primario" type="submit" disabled={enviando}>{modo === 'generar' ? 'Generar contraseña temporal' : 'Guardar contraseña'}</button>
          <button className="btn btn-secundario" type="button" onClick={onCerrar}>Cancelar</button>
        </div>
      </form>
    </Modal>
  );
}

/** Asignar uno o varios roles a un usuario. */
function AsignarRoles({ usuario, roles, onCerrar, onListo }) {
  const [seleccion, setSeleccion] = useState(usuario.roles.map((r) => r.clave));
  const [error, setError] = useState('');
  const permisosResultantes = [...new Set(roles.filter((r) => seleccion.includes(r.clave)).flatMap((r) => r.permisos))].sort();

  function alternar(clave) {
    setSeleccion((s) => (s.includes(clave) ? s.filter((c) => c !== clave) : [...s, clave]));
  }

  async function guardar() {
    setError('');
    if (!seleccion.length) { setError('Seleccione al menos un rol.'); return; }
    if (seleccion.includes('admin') && !usuario.roles.some((r) => r.clave === 'admin')
      && !window.confirm(`¿Dar el rol ADMINISTRADOR a ${usuario.nombre}? Tendrá todos los permisos.`)) return;
    try {
      await admin.actualizar(usuario.id, { roles: seleccion });
      onListo(`Roles de ${usuario.nombre} actualizados.`);
    } catch (err) {
      setError(err.message);
    }
  }

  return (
    <Modal titulo={`Roles de ${usuario.nombre}`} onCerrar={onCerrar} ancho>
      <p className="ayuda">Un usuario puede tener varios roles; sus permisos son la suma de los permisos de todos ellos.</p>
      <Mensaje tipo="error">{error}</Mensaje>
      <div className="lista-roles">
        {roles.map((r) => (
          <label key={r.clave} className={`opcion-rol ${seleccion.includes(r.clave) ? 'activa' : ''}`}>
            <input type="checkbox" checked={seleccion.includes(r.clave)} onChange={() => alternar(r.clave)} />
            <span>
              <strong>{r.nombre}</strong>
              <small>{r.permisos.length ? r.permisos.map((p) => NOMBRES_PERMISOS[p] || p).join(' · ') : 'Sin permisos adicionales'}</small>
            </span>
          </label>
        ))}
      </div>
      <p className="ayuda" style={{ marginTop: 12 }}>
        <strong>Permisos resultantes:</strong> {permisosResultantes.length ? permisosResultantes.map((p) => NOMBRES_PERMISOS[p] || p).join(' · ') : 'ninguno'}
      </p>
      <div className="acciones">
        <button type="button" className="btn btn-primario" onClick={guardar}>Guardar roles</button>
        <button type="button" className="btn btn-secundario" onClick={onCerrar}>Cancelar</button>
      </div>
    </Modal>
  );
}

function Solicitudes({ usuarios, onCambio, puedeAprobar, puedeGestionar }) {
  const [comentarios, setComentarios] = useState({});
  const [error, setError] = useState('');
  const [ocupado, setOcupado] = useState(null);
  const [restablecer, setRestablecer] = useState(null);
  const [ok, setOk] = useState('');
  const pendientes = puedeAprobar ? usuarios.filter((u) => u.solicitud?.estado === 'pendiente') : [];
  const recuperaciones = puedeGestionar ? usuarios.filter((u) => u.recuperacion_solicitada) : [];

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

  async function verSoporte(u) {
    setError('');
    try {
      const blob = await admin.descargarSoporte(u.id);
      const url = URL.createObjectURL(blob);
      const enlace = document.createElement('a');
      enlace.href = url;
      enlace.download = u.solicitud.soporte?.nombre || 'soporte.pdf';
      enlace.click();
      setTimeout(() => URL.revokeObjectURL(url), 1000);
    } catch (err) {
      setError(err.message);
    }
  }

  async function descartar(u) {
    try {
      await admin.descartarRecuperacion(u.id);
      onCambio();
    } catch (err) {
      setError(err.message);
    }
  }

  return (
    <div>
      {restablecer && (
        <RestablecerPassword
          usuario={restablecer}
          onCerrar={() => setRestablecer(null)}
          onListo={(m) => { setRestablecer(null); setOk(m); onCambio(); }}
        />
      )}
      <Mensaje tipo="error">{error}</Mensaje>
      <Mensaje tipo="ok">{ok}</Mensaje>

      {puedeGestionar && (
        <>
          <h4 className="subtitulo-admin">Restablecimiento de contraseña ({recuperaciones.length})</h4>
          {!recuperaciones.length ? <div className="vacio">No hay solicitudes de "Olvidé mi contraseña".</div> : recuperaciones.map((u) => (
            <div className="solicitud" key={`r-${u.id}`}>
              <div className="cabecera">
                <div>
                  <strong>{u.nombre}</strong> <span className="ayuda" style={{ margin: 0 }}>· {u.email}</span>
                  <div className="ayuda" style={{ margin: '2px 0 0' }}>Solicitado el {formatearFecha(u.recuperacion_solicitada)}</div>
                </div>
                <span className="badge badge-pendiente">Olvidó su contraseña</span>
              </div>
              <p className="ayuda">Antes de entregar una contraseña, confirma la identidad de la persona por un canal conocido.</p>
              <div className="acciones">
                <button type="button" className="btn btn-primario btn-pequeno" onClick={() => setRestablecer(u)}>Restablecer contraseña</button>
                <button type="button" className="btn btn-secundario btn-pequeno" onClick={() => descartar(u)}>Descartar</button>
              </div>
            </div>
          ))}
        </>
      )}

      {puedeAprobar && (
        <>
          <h4 className="subtitulo-admin">Acceso de investigador ({pendientes.length})</h4>
          {!pendientes.length ? <div className="vacio">No hay solicitudes de acceso pendientes.</div> : pendientes.map((u) => (
            <div className="solicitud" key={u.id}>
              <div className="cabecera">
                <div>
                  <strong>{u.nombre}</strong> <span className="ayuda" style={{ margin: 0 }}>· {u.email}</span>
                  <div className="ayuda" style={{ margin: '2px 0 0' }}>{u.solicitud.institucion} · {formatearFecha(u.solicitud.fecha)}</div>
                </div>
                <BadgeSolicitud estado="pendiente" />
              </div>
              <p className="motivo">{u.solicitud.motivo}</p>
              {u.solicitud.soporte && (
                <p className="ayuda" style={{ margin: '0 0 10px' }}>
                  Soporte: <button type="button" className="enlace" onClick={() => verSoporte(u)}>{u.solicitud.soporte.nombre}</button>{' '}
                  ({Math.max(1, Math.round((u.solicitud.soporte.tamano || 0) / 1024))} KB · PDF verificado)
                </p>
              )}
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
        </>
      )}
    </div>
  );
}

function Usuarios({ usuarios, roles, onCambio, miId }) {
  const [busqueda, setBusqueda] = useState('');
  const [error, setError] = useState('');
  const [ok, setOk] = useState('');
  const [editandoRoles, setEditandoRoles] = useState(null);
  const [restablecer, setRestablecer] = useState(null);
  const filtro = busqueda.trim().toLowerCase();
  const lista = filtro ? usuarios.filter((u) => `${u.nombre} ${u.email}`.toLowerCase().includes(filtro)) : usuarios;

  async function ejecutar(accion) {
    setError('');
    setOk('');
    try {
      await accion();
      onCambio();
    } catch (err) {
      setError(err.message);
    }
  }

  function alternarActivo(u) {
    const texto = u.activo ? `¿Desactivar la cuenta de ${u.nombre}? Se cerrarán sus sesiones de inmediato.` : `¿Reactivar la cuenta de ${u.nombre}?`;
    if (window.confirm(texto)) ejecutar(() => admin.actualizar(u.id, { activo: !u.activo }));
  }

  function restablecer2fa(u) {
    if (!window.confirm(`¿Quitar la verificación en dos pasos de ${u.nombre}? Úselo solo si perdió el celular y sus códigos. Se cerrarán sus sesiones.`)) return;
    ejecutar(() => admin.restablecer2fa(u.id));
  }

  const listo = (m) => { setEditandoRoles(null); setRestablecer(null); setOk(m); onCambio(); };

  return (
    <div>
      {editandoRoles && <AsignarRoles usuario={editandoRoles} roles={roles} onCerrar={() => setEditandoRoles(null)} onListo={listo} />}
      {restablecer && <RestablecerPassword usuario={restablecer} onCerrar={() => setRestablecer(null)} onListo={listo} />}
      <Mensaje tipo="error">{error}</Mensaje>
      <Mensaje tipo="ok">{ok}</Mensaje>
      <input className="control" style={{ marginBottom: 14 }} placeholder="Buscar por nombre o correo" value={busqueda} onChange={(e) => setBusqueda(e.target.value)} maxLength={100} />
      <div className="tabla-scroll">
        <table className="tabla">
          <thead>
            <tr><th>Usuario</th><th>Roles</th><th>Estado</th><th>2FA</th><th>Último acceso</th><th>Acciones</th></tr>
          </thead>
          <tbody>
            {lista.map((u) => {
              const soyYo = u.id === miId;
              const tieneAdmin = u.permisos.some((p) => !p.startsWith('datos.'));
              return (
                <tr key={u.id}>
                  <td>{u.nombre}{soyYo && ' (tú)'}<span className="secundario">{u.email}</span></td>
                  <td>
                    <BadgesRoles roles={u.roles} />
                    {!soyYo && <button type="button" className="enlace" style={{ display: 'block', marginTop: 4, fontSize: 12 }} onClick={() => setEditandoRoles(u)}>Cambiar roles</button>}
                  </td>
                  <td>
                    {u.activo ? <span className="badge badge-aprobada">Activa</span> : <span className="badge badge-inactivo">Desactivada</span>}
                    {u.debe_cambiar_password && <span className="secundario">Clave temporal</span>}
                  </td>
                  <td>{u.dos_pasos ? <span className="badge badge-aprobada">Activa</span> : <span className={`badge ${tieneAdmin ? 'badge-pendiente' : 'badge-usuario'}`}>{tieneAdmin ? 'Pendiente' : 'No'}</span>}</td>
                  <td>{formatearFecha(u.ultimo_acceso)}</td>
                  <td>
                    {!soyYo && (
                      <div className="acciones">
                        <button type="button" className="btn btn-secundario btn-pequeno" onClick={() => setRestablecer(u)}>Restablecer clave</button>
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

/** Crear y editar un rol con sus permisos. */
function EditorRol({ rol, catalogo, misPermisos, onCerrar, onListo }) {
  const nuevo = !rol;
  const [nombre, setNombre] = useState(rol?.nombre || '');
  const [descripcion, setDescripcion] = useState(rol?.descripcion || '');
  const [seleccion, setSeleccion] = useState(rol?.permisos || []);
  const [error, setError] = useState('');
  const soloDatos = rol && ['usuario', 'investigador'].includes(rol.clave);

  function alternar(p) {
    setSeleccion((s) => (s.includes(p) ? s.filter((x) => x !== p) : [...s, p]));
  }

  async function guardar(evento) {
    evento.preventDefault();
    setError('');
    try {
      if (nuevo) {
        await admin.crearRol({ nombre: nombre.trim(), descripcion: descripcion.trim() || null, permisos: seleccion });
        onListo(`Rol "${nombre.trim()}" creado.`);
      } else {
        const cambios = { permisos: seleccion, descripcion: descripcion.trim() };
        if (!rol.sistema) cambios.nombre = nombre.trim();
        await admin.actualizarRol(rol.clave, cambios);
        onListo(`Rol "${nombre.trim()}" actualizado. Los cambios aplican de inmediato a sus usuarios.`);
      }
    } catch (err) {
      setError(err.message);
    }
  }

  return (
    <Modal titulo={nuevo ? 'Nuevo rol' : `Editar rol: ${rol.nombre}`} onCerrar={onCerrar} ancho>
      <Mensaje tipo="error">{error}</Mensaje>
      <form onSubmit={guardar}>
        <Campo etiqueta="Nombre del rol">
          <input value={nombre} onChange={(e) => setNombre(e.target.value)} minLength={2} maxLength={60} required disabled={rol?.sistema} autoFocus={nuevo} />
        </Campo>
        <Campo etiqueta="Descripción (opcional)">
          <input value={descripcion} onChange={(e) => setDescripcion(e.target.value)} maxLength={200} />
        </Campo>
        <span className="etiqueta-campo">Permisos</span>
        <div className="lista-roles">
          {catalogo.map((p) => {
            const ajeno = !misPermisos.includes(p.clave);
            const bloqueado = ajeno || (soloDatos && !p.clave.startsWith('datos.'));
            return (
              <label key={p.clave} className={`opcion-rol ${seleccion.includes(p.clave) ? 'activa' : ''} ${bloqueado ? 'bloqueada' : ''}`}>
                <input type="checkbox" checked={seleccion.includes(p.clave)} onChange={() => alternar(p.clave)} disabled={bloqueado} />
                <span>
                  <strong>{NOMBRES_PERMISOS[p.clave] || p.clave}</strong>
                  <small>{p.descripcion}{ajeno ? ' — usted no tiene este permiso' : ''}</small>
                </span>
              </label>
            );
          })}
        </div>
        {soloDatos && <p className="ayuda" style={{ marginTop: 10 }}>Este rol del sistema solo puede tener permisos de consulta de datos.</p>}
        <div className="acciones" style={{ marginTop: 14 }}>
          <button className="btn btn-primario" type="submit">{nuevo ? 'Crear rol' : 'Guardar cambios'}</button>
          <button className="btn btn-secundario" type="button" onClick={onCerrar}>Cancelar</button>
        </div>
      </form>
    </Modal>
  );
}

function Roles({ roles, catalogo, misPermisos, onCambio }) {
  const [editando, setEditando] = useState(undefined);
  const [error, setError] = useState('');
  const [ok, setOk] = useState('');

  async function eliminar(r) {
    const aviso = r.usuarios ? ` ${r.usuarios} usuario(s) lo perderán de inmediato.` : '';
    if (!window.confirm(`¿Eliminar el rol "${r.nombre}"?${aviso}`)) return;
    setError('');
    try {
      await admin.eliminarRol(r.clave);
      setOk(`Rol "${r.nombre}" eliminado.`);
      onCambio();
    } catch (err) {
      setError(err.message);
    }
  }

  return (
    <div>
      {editando !== undefined && (
        <EditorRol
          rol={editando}
          catalogo={catalogo}
          misPermisos={misPermisos}
          onCerrar={() => setEditando(undefined)}
          onListo={(m) => { setEditando(undefined); setOk(m); onCambio(); }}
        />
      )}
      <div className="acciones" style={{ justifyContent: 'space-between', marginBottom: 12 }}>
        <p className="ayuda" style={{ margin: 0 }}>Cada rol agrupa permisos. Asigna roles a los usuarios desde la pestaña Usuarios.</p>
        <button type="button" className="btn btn-primario btn-pequeno" disabled={!catalogo.length} onClick={() => { setOk(''); setEditando(null); }}>+ Nuevo rol</button>
      </div>
      <Mensaje tipo="error">{error}</Mensaje>
      <Mensaje tipo="ok">{ok}</Mensaje>
      <div className="tabla-scroll">
        <table className="tabla">
          <thead><tr><th>Rol</th><th>Permisos</th><th>Usuarios</th><th>Acciones</th></tr></thead>
          <tbody>
            {roles.map((r) => (
              <tr key={r.clave}>
                <td><strong>{r.nombre}</strong>{r.sistema && <span className="secundario">Rol del sistema</span>}{r.descripcion && <span className="secundario">{r.descripcion}</span>}</td>
                <td><span className="permisos-celda">{r.permisos.length ? r.permisos.map((p) => <span key={p} className="chip-permiso">{NOMBRES_PERMISOS[p] || p}</span>) : <span className="secundario">Ninguno</span>}</span></td>
                <td>{r.usuarios}</td>
                <td>
                  <div className="acciones">
                    {r.editable && <button type="button" className="btn btn-secundario btn-pequeno" onClick={() => { setOk(''); setEditando(r); }}>Editar permisos</button>}
                    {!r.sistema && <button type="button" className="btn btn-peligro btn-pequeno" onClick={() => eliminar(r)}>Eliminar</button>}
                    {!r.editable && <span className="secundario">Siempre tiene todos los permisos</span>}
                  </div>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  );
}

function Sesion() {
  const [datos, setDatos] = useState(null);
  const [valores, setValores] = useState({});
  const [error, setError] = useState('');
  const [ok, setOk] = useState('');

  useEffect(() => {
    admin.configuracion().then((r) => { setDatos(r); setValores(r.valores); }).catch((err) => setError(err.message));
  }, []);

  async function guardar(evento) {
    evento.preventDefault();
    setError('');
    setOk('');
    try {
      const cambios = Object.fromEntries(Object.entries(valores).map(([k, v]) => [k, Number(v)]));
      const r = await admin.guardarConfiguracion(cambios);
      setDatos(r);
      setValores(r.valores);
      setOk('Configuración guardada. Se aplica de inmediato a todas las sesiones.');
    } catch (err) {
      setError(err.message);
    }
  }

  if (!datos) return error ? <Mensaje tipo="error">{error}</Mensaje> : <LoadingState message="Cargando configuración…" />;
  return (
    <form onSubmit={guardar}>
      <p className="ayuda">
        Límites según NIST SP 800-63B-4 (nivel AAL2): inactividad de máximo 1 hora y duración máxima de 24 horas.
        Aumentar los tiempos es más cómodo pero menos seguro; el sistema no permite superar esos límites.
      </p>
      <Mensaje tipo="error">{error}</Mensaje>
      <Mensaje tipo="ok">{ok}</Mensaje>
      <div className="cuenta-grid">
        {Object.entries(datos.limites).map(([campo, regla]) => (
          <Campo key={campo} etiqueta={regla.descripcion} pista={`Entre ${regla.minimo} y ${regla.maximo}. Por defecto: ${regla.defecto}.`}>
            <input
              type="number"
              min={regla.minimo}
              max={regla.maximo}
              value={valores[campo] ?? ''}
              onChange={(e) => setValores((v) => ({ ...v, [campo]: e.target.value }))}
              required
            />
          </Campo>
        ))}
      </div>
      <p className="ayuda">
        <strong>Token de acceso:</strong> credencial de corta duración que el navegador renueva solo mientras la sesión sigue activa.
        <br />
        <strong>Inactividad:</strong> si la persona no usa la aplicación durante ese tiempo, la sesión se cierra y debe iniciar sesión de nuevo.
        <br />
        <strong>Sesiones simultáneas:</strong> cuántos navegadores o dispositivos pueden tener abierta la misma cuenta a la vez.
        Al superar el límite se cierra la sesión que lleva más tiempo sin usarse y se le avisa a la persona.
      </p>
      <button className="btn btn-primario" type="submit">Guardar configuración</button>
    </form>
  );
}

function Auditoria() {
  const [eventos, setEventos] = useState(null);
  const [soloFallidos, setSoloFallidos] = useState(false);
  const [error, setError] = useState('');
  const [recarga, setRecarga] = useState(0);

  useEffect(() => {
    let cancelado = false;
    setEventos(null);
    admin.auditoria(soloFallidos)
      .then((r) => { if (!cancelado) setEventos(r.eventos); })
      .catch((err) => { if (!cancelado) setError(err.message); });
    return () => { cancelado = true; };
  }, [soloFallidos, recarga]);

  const valor = (k, v) => (Array.isArray(v) ? v.map((x) => (x === true ? 'sí' : x === false ? 'no' : x)).join(' → ') : v);
  const detalle = (d) => (d == null ? '' : typeof d === 'string' ? d : Object.entries(d).map(([k, v]) => `${NOMBRES_CAMPO[k] || k}: ${valor(k, v)}`).join(' · '));

  return (
    <div>
      <Mensaje tipo="error">{error}</Mensaje>
      <div className="acciones" style={{ marginBottom: 12, justifyContent: 'space-between' }}>
        <label className="acciones" style={{ fontSize: 13 }}>
          <input type="checkbox" checked={soloFallidos} onChange={(e) => setSoloFallidos(e.target.checked)} /> Solo intentos fallidos o denegados
        </label>
        <button type="button" className="btn btn-secundario btn-pequeno" onClick={() => setRecarga((n) => n + 1)}>Actualizar</button>
      </div>
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

function Errores({ puedeSimular }) {
  const [errores, setErrores] = useState(null);
  const [error, setError] = useState('');
  const [aviso, setAviso] = useState('');
  const [abierto, setAbierto] = useState(null);
  const [recarga, setRecarga] = useState(0);

  useEffect(() => {
    let cancelado = false;
    admin.errores()
      .then((r) => { if (!cancelado) setErrores(r.errores); })
      .catch((err) => { if (!cancelado) setError(err.message); });
    return () => { cancelado = true; };
  }, [recarga]);

  async function simular() {
    setAviso('');
    setError('');
    try {
      await admin.simularError();
    } catch (err) {
      // Lo que vería cualquier persona: mensaje genérico + código de referencia.
      setAviso(`Respuesta que recibe la persona: «${err.message}»`);
    }
    setRecarga((n) => n + 1);
  }

  return (
    <div>
      <p className="ayuda">
        Fallos internos (500) y caídas de la base de datos (503). La persona solo ve un mensaje genérico con el
        código de referencia; el detalle técnico queda aquí, en el archivo <code>logs/errores.log</code> y en
        <code> docker compose logs backend</code>. Se conservan 90 días.
      </p>
      <Mensaje tipo="error">{error}</Mensaje>
      <Mensaje tipo="info">{aviso}</Mensaje>
      <div className="acciones" style={{ marginBottom: 12, justifyContent: 'space-between' }}>
        {puedeSimular
          ? <button type="button" className="btn btn-peligro btn-pequeno" onClick={simular}>Simular un fallo del sistema</button>
          : <span />}
        <button type="button" className="btn btn-secundario btn-pequeno" onClick={() => setRecarga((n) => n + 1)}>Actualizar</button>
      </div>
      {!errores ? <LoadingState message="Cargando errores…" /> : (
        <div className="tabla-scroll">
          <table className="tabla">
            <thead><tr><th>Fecha</th><th>Código</th><th>Estado</th><th>Ruta</th><th>Error</th></tr></thead>
            <tbody>
              {errores.map((e) => (
                <tr key={e.referencia + e.fecha}>
                  <td>{formatearFecha(e.fecha)}{e.registrado_tarde && <span className="secundario">guardado al volver la BD</span>}</td>
                  <td><code>{e.referencia}</code></td>
                  <td><span className="estado-http">{e.estado}</span></td>
                  <td>{e.metodo} {e.ruta}<span className="secundario">IP {e.ip || '—'}</span></td>
                  <td>
                    <strong>{e.tipo}</strong>
                    <span className="secundario">{e.mensaje}</span>
                    <button type="button" className="enlace" style={{ fontSize: 12 }} onClick={() => setAbierto(abierto === e.referencia ? null : e.referencia)}>
                      {abierto === e.referencia ? 'Ocultar traza' : 'Ver traza'}
                    </button>
                    {abierto === e.referencia && <pre className="traza">{e.traza}</pre>}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
          {!errores.length && <div className="vacio">No se han registrado errores.</div>}
        </div>
      )}
    </div>
  );
}

export default function ViewAdmin({ onPendientes }) {
  const { usuario, tienePermiso, setUsuario } = useAuth();
  const puede = {
    solicitudes: tienePermiso('solicitudes.aprobar') || tienePermiso('usuarios.gestionar'),
    usuarios: tienePermiso('usuarios.gestionar'),
    roles: tienePermiso('roles.gestionar'),
    sesion: tienePermiso('configuracion.gestionar'),
    auditoria: tienePermiso('auditoria.ver'),
    errores: tienePermiso('auditoria.ver'),
  };
  const pestanas = [
    ['solicitudes', 'Solicitudes'],
    ['usuarios', 'Usuarios'],
    ['roles', 'Roles y permisos'],
    ['sesion', 'Sesión'],
    ['auditoria', 'Auditoría'],
    ['errores', 'Errores'],
  ].filter(([id]) => puede[id]);
  const [pestana, setPestana] = useState(pestanas[0]?.[0]);
  const [datos, setDatos] = useState(null);
  const [roles, setRoles] = useState([]);
  const [catalogo, setCatalogo] = useState([]);
  const [error, setError] = useState('');
  const falta2fa = !usuario?.dos_pasos;

  const cargar = useCallback(async () => {
    if (falta2fa) return;
    try {
      setError('');
      if (puede.solicitudes) {
        const r = await admin.usuarios();
        setDatos(r);
        onPendientes?.((tienePermiso('solicitudes.aprobar') ? r.pendientes : 0) + (tienePermiso('usuarios.gestionar') ? r.recuperaciones : 0));
      }
      if (puede.roles || puede.usuarios) {
        const [rs, cat] = await Promise.all([admin.roles(), admin.permisos()]);
        setRoles(rs.roles);
        setCatalogo(cat.permisos);
      }
    } catch (err) {
      setError(err.message);
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [falta2fa, puede.solicitudes, puede.roles, puede.usuarios, tienePermiso, onPendientes]);

  useEffect(() => { cargar(); }, [cargar]);

  if (falta2fa) {
    return (
      <div className="cuenta-page">
        <div className="cuenta-wrap estrecho">
          <span className="cuenta-kicker">Administración</span>
          <h2 className="cuenta-titulo">Activa la verificación en dos pasos</h2>
          <p className="cuenta-sub">
            Las cuentas con permisos de administración pueden cambiar roles y ver la actividad de otros usuarios, por eso
            deben proteger su acceso con un código del celular además de la contraseña.
          </p>
          <div className="cuenta-card"><ConfigurarDosPasos onActivado={(u) => setUsuario(u)} /></div>
        </div>
      </div>
    );
  }

  const necesitaDatos = pestana === 'solicitudes' || pestana === 'usuarios';
  return (
    <div className="cuenta-page">
      <div className="cuenta-wrap">
        <span className="cuenta-kicker">Administración</span>
        <h2 className="cuenta-titulo">Usuarios y accesos</h2>
        <p className="cuenta-sub">Solo se muestran las secciones que permiten tus roles.</p>

        <div className="tabs" role="tablist">
          {pestanas.map(([id, nombre]) => {
            const contador = id === 'solicitudes' && datos
              ? (tienePermiso('solicitudes.aprobar') ? datos.pendientes : 0) + (tienePermiso('usuarios.gestionar') ? datos.recuperaciones : 0)
              : 0;
            return (
              <button key={id} type="button" role="tab" aria-selected={pestana === id} onClick={() => setPestana(id)}>
                {nombre}{contador ? <span className="contador">{contador}</span> : null}
              </button>
            );
          })}
        </div>

        <div className="cuenta-card">
          <Mensaje tipo="error">{error}</Mensaje>
          {necesitaDatos && !datos ? <LoadingState message="Cargando usuarios…" /> : null}
          {pestana === 'solicitudes' && datos && (
            <Solicitudes usuarios={datos.usuarios} onCambio={cargar} puedeAprobar={tienePermiso('solicitudes.aprobar')} puedeGestionar={puede.usuarios} />
          )}
          {pestana === 'usuarios' && datos && <Usuarios usuarios={datos.usuarios} roles={roles} onCambio={cargar} miId={usuario?.id} />}
          {pestana === 'roles' && <Roles roles={roles} catalogo={catalogo} misPermisos={usuario.permisos} onCambio={cargar} />}
          {pestana === 'sesion' && <Sesion />}
          {pestana === 'auditoria' && <Auditoria />}
          {pestana === 'errores' && <Errores puedeSimular={tienePermiso('configuracion.gestionar')} />}
        </div>
      </div>
    </div>
  );
}
