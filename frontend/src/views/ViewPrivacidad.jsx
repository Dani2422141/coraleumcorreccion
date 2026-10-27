/**
 * Política de tratamiento de datos personales (Ley 1581 de 2012 y
 * Decreto 1377 de 2013, compilado en el Decreto 1074 de 2015).
 *
 * ⚠️ Antes de publicar Coraleum, reemplace los valores [COMPLETAR] con los
 * datos reales del responsable. Si cambia el contenido de la política,
 * actualice también POLITICA_VERSION en api/config.py y VERSION aquí: los
 * usuarios deberán aceptar la nueva versión.
 */

export const VERSION = '2026-10';
const VIGENCIA = '26 de octubre de 2026';

const RESPONSABLE = {
  nombre: 'Equipo de desarrollo de Coraleum — proyecto de grado de Ingeniería de Sistemas, Universidad de San Buenaventura, sede Bogotá',
  direccion: '[COMPLETAR: dirección de contacto]',
  correo: '[COMPLETAR: correo de contacto para datos personales]',
  telefono: '[COMPLETAR: teléfono de contacto]',
};

function Seccion({ titulo, children }) {
  return (
    <section style={{ marginBottom: 18 }}>
      <h3 style={{ fontSize: 15, fontWeight: 600, color: '#eaf8f7', margin: '0 0 6px' }}>{titulo}</h3>
      <div style={{ fontSize: 13.5, lineHeight: 1.7, color: 'rgba(214,238,235,.86)' }}>{children}</div>
    </section>
  );
}

/** Texto de la política (se reutiliza en la página y en la ventana del registro). */
export function PoliticaContenido() {
  return (
    <div>
      <Seccion titulo="1. Responsable del tratamiento">
        <p style={{ margin: 0 }}>{RESPONSABLE.nombre}.</p>
        <p style={{ margin: 0 }}>Dirección: {RESPONSABLE.direccion} · Correo: {RESPONSABLE.correo} · Teléfono: {RESPONSABLE.telefono}.</p>
      </Seccion>

      <Seccion titulo="2. Datos que recolectamos">
        <ul style={{ margin: 0, paddingLeft: 18 }}>
          <li>Nombre y correo electrónico, al crear la cuenta.</li>
          <li>Institución y motivo, solo si solicitas acceso de investigador.</li>
          <li>Registro de actividad de seguridad: fecha, tipo de evento, dirección IP y navegador (inicios de sesión, cambios de contraseña, etc.).</li>
        </ul>
        <p style={{ margin: '6px 0 0' }}>
          No recolectamos datos sensibles ni datos de menores de edad. La contraseña y el secreto de verificación en dos
          pasos se guardan cifrados o como hash irreversible: nadie, ni siquiera los administradores, puede verlos.
        </p>
      </Seccion>

      <Seccion titulo="3. Finalidades">
        <ul style={{ margin: 0, paddingLeft: 18 }}>
          <li>Crear y administrar tu cuenta y permitirte iniciar sesión.</li>
          <li>Evaluar tu solicitud de acceso al Explorador Térmico y al registro histórico.</li>
          <li>Proteger la plataforma: detectar accesos indebidos y mantener un registro de auditoría.</li>
          <li>Comunicarnos contigo sobre tu cuenta y sobre cambios en esta política.</li>
        </ul>
        <p style={{ margin: '6px 0 0' }}>Tus datos no se venden ni se comparten con terceros para fines comerciales.</p>
      </Seccion>

      <Seccion titulo="4. Tus derechos como titular">
        <p style={{ margin: 0 }}>De acuerdo con la Ley 1581 de 2012 tienes derecho a:</p>
        <ul style={{ margin: '4px 0 0', paddingLeft: 18 }}>
          <li>Conocer, actualizar y rectificar tus datos.</li>
          <li>Solicitar prueba de la autorización que nos diste.</li>
          <li>Ser informado sobre el uso que se da a tus datos.</li>
          <li>Revocar la autorización y pedir la supresión de tus datos cuando no exista un deber legal de conservarlos.</li>
          <li>Acceder gratuitamente a tus datos.</li>
          <li>Presentar quejas ante la Superintendencia de Industria y Comercio (SIC).</li>
        </ul>
      </Seccion>

      <Seccion titulo="5. Cómo ejercer tus derechos">
        <ul style={{ margin: 0, paddingLeft: 18 }}>
          <li><strong>Consultar tus datos:</strong> en "Mi cuenta" → "Descargar mis datos" obtienes una copia inmediata.</li>
          <li><strong>Suprimir tus datos y revocar la autorización:</strong> en "Mi cuenta" → "Eliminar mi cuenta". Se borran tu cuenta y tus datos; el registro de seguridad se conserva de forma anónima.</li>
          <li><strong>Otras solicitudes o reclamos:</strong> escribe a {RESPONSABLE.correo}. Las consultas se responden en máximo 10 días hábiles y los reclamos en máximo 15 días hábiles, según la Ley 1581 de 2012.</li>
        </ul>
      </Seccion>

      <Seccion titulo="6. Seguridad y conservación">
        <p style={{ margin: 0 }}>
          Aplicamos medidas técnicas como cifrado de contraseñas (Argon2id), sesiones protegidas, verificación en dos pasos
          para administradores y control de acceso por roles. Los datos de la cuenta se conservan mientras esté activa;
          el registro de seguridad se elimina automáticamente a los 180 días.
        </p>
      </Seccion>

      <Seccion titulo="7. Vigencia y cambios">
        <p style={{ margin: 0 }}>
          Versión {VERSION}, vigente desde el {VIGENCIA}. Si la política cambia de forma sustancial, te lo informaremos y
          te pediremos aceptar la nueva versión al iniciar sesión.
        </p>
      </Seccion>
    </div>
  );
}

export default function ViewPrivacidad() {
  return (
    <div className="cuenta-page">
      <div className="cuenta-wrap" style={{ maxWidth: 820 }}>
        <span className="cuenta-kicker">Protección de datos personales</span>
        <h2 className="cuenta-titulo">Política de tratamiento de datos</h2>
        <p className="cuenta-sub">Ley 1581 de 2012 y Decreto 1377 de 2013 (compilado en el Decreto 1074 de 2015).</p>
        <div className="cuenta-card"><PoliticaContenido /></div>
      </div>
    </div>
  );
}
