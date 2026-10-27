// Siluetas de animales del arrecife del Caribe, dibujadas para Coraleum.
// Todas usan currentColor: toman el color del texto donde se ponen.

const PEZ = 'M2.5 12c2.6-3.6 6.2-5 10-4.2 2 .4 3.8 1.6 5.2 3l3.8-2.6v7.6l-3.8-2.6c-1.4 1.4-3.2 2.6-5.2 3-3.8.8-7.4-.6-10-4.2Z';
const OJO = (x, y, r = 1) => `M${x - r} ${y}a${r} ${r} 0 1 0 ${2 * r} 0 ${r} ${r} 0 1 0 ${-2 * r} 0Z`;

const DIBUJOS = {
  // Tortuga carey vista desde arriba
  tortuga: (
    <>
      <path fillRule="evenodd" d="M12 6.8c-3 0-5.3 2.8-5.3 6.2S9 19.3 12 19.3s5.3-2.9 5.3-6.3S15 6.8 12 6.8Zm0 4.1 1.5.9v1.9l-1.5.9-1.5-.9v-1.9Z" />
      <circle cx="12" cy="4.6" r="2" />
      <path d="M7.4 9.8 3 7.2c-.9-.5-1.7.6-.9 1.3L6.9 12ZM16.6 9.8 21 7.2c.9-.5 1.7.6.9 1.3L17.1 12ZM8.2 17.1l-2.7 2.6c-.6.6.1 1.5.9 1.1l3.1-2ZM15.8 17.1l2.7 2.6c.6.6-.1 1.5-.9 1.1l-3.1-2Z" />
    </>
  ),
  // Pez loro: aleta dorsal y escamas marcadas
  pezLoro: (
    <>
      <path fillRule="evenodd" d={`${PEZ}${OJO(6.6, 11.3, 1.05)}`} />
      <path d="M8.6 8.3c1.5-2.2 3.8-3 6.2-2.6l-.9 2.8ZM9.4 15.7c1.3 1.6 3 2.1 4.8 1.8l-1-2.1Z" />
      <path d="M10.6 9.6v4.8M13.2 9.4v5.2M15.6 10.3v3.4" stroke="rgba(0,0,0,.32)" strokeWidth="1" strokeLinecap="round" />
    </>
  ),
  // Pez cirujano azul: cuerpo alto y ovalado
  pezCirujano: (
    <path fillRule="evenodd" d={`M3 12c2.4-4.4 6.2-6.6 10.4-6.2 2.6.2 4.6 1.8 5.8 3.6L22 7.6v8.8l-2.8-1.8c-1.2 1.8-3.2 3.4-5.8 3.6C9.2 18.6 5.4 16.4 3 12Z${OJO(7, 10.8, 1.1)}M16.2 13.4l1.6-.8-1.6-.8Z`} />
  ),
  pez: <path fillRule="evenodd" d={`${PEZ}${OJO(6.6, 11.3, 1.05)}`} />,
  // Caballito de mar
  caballito: (
    <path fillRule="evenodd" d={`M14.5 3.2c-1.8-.4-3.4.6-3.8 2.3l-2.8.6c-.6.1-.6 1 0 1.1l2.9.3c.1.9.5 1.7 1.1 2.3-1.9 1.5-2.7 3.8-2.1 6 .5 1.8 1.9 3.2 3.6 3.6.9.2 1.4 1.1 1 1.9-.4.8-1.4 1-2.1.5-.5-.4-1.3 0-1.1.7.3 1.3 1.9 2 3.1 1.5 1.8-.7 2.5-2.9 1.6-4.6-.4-.8-.2-1.7.4-2.3 1.4-1.6 1.8-4 .9-6-.4-.9-.4-2 .1-2.9.9-1.7.1-3.7-1.6-4.1Z${OJO(13.4, 5.6, .8)}M16.6 11.2l2.4-.9-2.1 2.3Z`} />
  ),
  // Raya / manta
  raya: (
    <path d="M12 5.6c-1.4 0-2.4 1-2.9 2.2C6.8 8.2 4.2 9.8 2 12.6c2.8.2 5.2.9 7.2 2.1.5 1 1.2 1.9 1.9 2.6L12 22.4l.9-5.1c.7-.7 1.4-1.6 1.9-2.6 2-1.2 4.4-1.9 7.2-2.1-2.2-2.8-4.8-4.4-7.1-4.8-.5-1.2-1.5-2.2-2.9-2.2ZM10.1 6.4 9 3.6l2 2.2ZM13.9 6.4 15 3.6l-2 2.2Z" />
  ),
  // Estrella de mar
  estrella: (
    <path d="M12 2.6 14.5 9.2 21.5 9.5 16 13.9 17.9 20.7 12 16.8 6.1 20.7 8 13.9 2.5 9.5 9.5 9.2Z" stroke="currentColor" strokeWidth="2.2" strokeLinejoin="round" />
  ),
  // Pulpo
  pulpo: (
    <>
      <path fillRule="evenodd" d={`M12 2.8c-3.6 0-6 2.6-6 6 0 1.8.7 3.3 1.8 4.3h8.4c1.1-1 1.8-2.5 1.8-4.3 0-3.4-2.4-6-6-6Z${OJO(9.8, 9, .95)}${OJO(14.2, 9, .95)}`} />
      <path d="M8.3 13c-.5 2.6-2 3.9-3.8 4.2M10.3 13.2c0 3-.6 5.2-2.3 6.9M13.7 13.2c0 3 .6 5.2 2.3 6.9M15.7 13c.5 2.6 2 3.9 3.8 4.2" fill="none" stroke="currentColor" strokeWidth="1.9" strokeLinecap="round" />
    </>
  ),
  // Banco de peces
  banco: (
    <>
      <path fillRule="evenodd" transform="translate(1 1.2) scale(.52)" d={`${PEZ}${OJO(6.6, 11.3, 1.2)}`} />
      <path fillRule="evenodd" transform="translate(10.6 4.6) scale(.52)" d={`${PEZ}${OJO(6.6, 11.3, 1.2)}`} />
      <path fillRule="evenodd" transform="translate(3.4 10.6) scale(.52)" d={`${PEZ}${OJO(6.6, 11.3, 1.2)}`} />
    </>
  ),
  // Cangrejo
  cangrejo: (
    <>
      <path d="M6.5 13.2c0-2.6 2.5-4.5 5.5-4.5s5.5 1.9 5.5 4.5S15 17.3 12 17.3s-5.5-1.5-5.5-4.1Z" />
      <path d="M5.4 3.8a2.4 2.4 0 0 0-1.6 4.1l2.6 3 1.2-.9-1.5-2.6 1.3-.9a2.4 2.4 0 0 0-2-2.7ZM18.6 3.8a2.4 2.4 0 0 1 1.6 4.1l-2.6 3-1.2-.9 1.5-2.6-1.3-.9a2.4 2.4 0 0 1 2-2.7Z" />
      <path d="M7.1 14.6 3.4 16.2M7.6 16.4l-2.8 2.5M16.9 14.6l3.7 1.6M16.4 16.4l2.8 2.5M10.4 8.9V7.2M13.6 8.9V7.2" fill="none" stroke="currentColor" strokeWidth="1.6" strokeLinecap="round" />
      <circle cx="10.4" cy="6.6" r="1" /><circle cx="13.6" cy="6.6" r="1" />
    </>
  ),
  // Langosta espinosa
  langosta: (
    <>
      <path d="M12 6c-1.3 0-2.2 1-2.2 2.3v2.2l-1 1.2v2l1 1.1v1.7l-.9 1.3.9 1 1-.6h2.4l1 .6.9-1-.9-1.3v-1.7l1-1.1v-2l-1-1.2V8.3C14.2 7 13.3 6 12 6ZM9.5 18.9 12 22.2l2.5-3.3Z" />
      <path d="M11 6.4 6.6 2.2M13 6.4l4.4-4.2M9.8 10.8 6.6 9.6M9.8 12.8l-3.4.2M14.2 10.8l3.2-1.2M14.2 12.8l3.4.2" fill="none" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" />
    </>
  ),
  // Concha de abanico (vieira)
  concha: (
    <>
      <path d="M12 3.8C7 3.8 3.5 7.5 3.5 11.9c0 1.4.4 2.7 1 3.8l4.2 1.6L12 20l3.3-2.7 4.2-1.6c.6-1.1 1-2.4 1-3.8 0-4.4-3.5-8.1-8.5-8.1ZM9.6 19.6h4.8l-.8 1.6h-3.2Z" />
      <path d="M12 6v12.8M8.4 6.8l1.6 11.4M15.6 6.8 14 18.2M5.6 9.2l3.2 8.2M18.4 9.2l-3.2 8.2" stroke="rgba(0,0,0,.28)" strokeWidth="1" strokeLinecap="round" />
    </>
  ),
  // Tiburón
  tiburon: (
    <path fillRule="evenodd" d={`M2 13c3.2-1.6 6.4-2.6 9.6-2.9L14 6.5c.3-.5 1-.3 1 .3l-.4 3.4c2 .3 4 1 5.9 2.1l1.5-1.6c.4-.4 1-.1.9.4L22.4 14l.5 2.9c.1.5-.5.8-.9.4l-1.5-1.5c-3 1.6-6.4 2.4-10.2 2.2l-1.6 2.5c-.3.5-1 .3-1-.3l.2-2.6C5.6 17 3.6 15.4 2 13Z${OJO(5.6, 12.6, .85)}M8.4 13.4v1.8M9.6 13.2v1.8`} />
  ),
};

export default function AnimalMarino({ nombre, size = 20, className = '', titulo }) {
  return (
    <svg
      className={className}
      width={size}
      height={size}
      viewBox="0 0 24 24"
      fill="currentColor"
      role={titulo ? 'img' : undefined}
      aria-label={titulo}
      aria-hidden={titulo ? undefined : true}
    >
      {DIBUJOS[nombre]}
    </svg>
  );
}

export const NOMBRES_ANIMALES = Object.keys(DIBUJOS);
