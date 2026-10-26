import { useAuth } from '../auth/AuthContext';

/** Se muestra en lugar de una sección protegida cuando no hay permiso. */
export default function AccesoRestringido({ seccion, onNavigate }) {
  const { autenticado, usuario } = useAuth();
  const pendiente = usuario?.solicitud?.estado === 'pendiente';

  return (
    <div className="restringido">
      <div className="cuenta-card">
        <div className="icono" aria-hidden="true">🔒</div>
        <h3>{seccion} es para investigadores</h3>
        {!autenticado && (
          <>
            <p className="ayuda">
              El mapa interactivo, el detalle por área y el registro histórico de indicadores requieren una cuenta de
              investigador. El contenido educativo sigue siendo libre.
            </p>
            <div className="acciones">
              <button type="button" className="btn btn-primario" onClick={() => onNavigate('acceso')}>Iniciar sesión</button>
              <button type="button" className="btn btn-secundario" onClick={() => onNavigate('registro')}>Crear cuenta</button>
            </div>
          </>
        )}
        {autenticado && (
          <>
            <p className="ayuda">
              {pendiente
                ? 'Tu solicitud de acceso está pendiente de revisión por un administrador.'
                : 'Tu cuenta aún no tiene acceso de investigador. Puedes solicitarlo desde "Mi cuenta".'}
            </p>
            <div className="acciones">
              <button type="button" className="btn btn-primario" onClick={() => onNavigate('cuenta')}>
                {pendiente ? 'Ver mi solicitud' : 'Solicitar acceso'}
              </button>
              <button type="button" className="btn btn-secundario" onClick={() => onNavigate('corales')}>Ir al contenido educativo</button>
            </div>
          </>
        )}
      </div>
    </div>
  );
}
