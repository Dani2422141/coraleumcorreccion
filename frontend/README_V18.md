# V18 — Conoce los Corales: scroll correcto

Ajuste puntual de layout para que la vista `Conoce los Corales` use el alto disponible del contenedor principal y tenga su propio scroll vertical.

Cambios:
- `main` del layout principal ahora tiene `min-height:0` y `overflow:hidden`.
- `.corales-page-v17` usa `height:100%`, `min-height:0` y `max-height:100%` con `overflow-y:auto`.
- No se modifica el contenido educativo, la animación ni la estructura de tarjetas.
