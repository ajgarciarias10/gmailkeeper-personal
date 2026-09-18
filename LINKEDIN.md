# Post para LinkedIn

Tres instrucciones para organizar Gmail acabaron convirtiéndose en un experimento que quiero compartir.

La petición era sencilla:

→ Identificar qué marca envía cada mensaje.
→ Añadir su etiqueta si falta, con una subetiqueta por marca.
→ Archivarlo automáticamente.

De ahí salió GmailKeeper Personal: un proyecto en Python que utiliza la API de Gmail para organizar el correo, conservando las etiquetas anteriores y el estado de lectura.

Quise documentarlo para que otras personas con conocimientos técnicos puedan probarlo y adaptarlo. Preparé un repositorio con instrucciones para conectar una cuenta propia, revisar una muestra antes de aplicar cambios y ajustar las reglas:

• Archivar solo promociones.
• Dejar ciertos remitentes en Recibidos.
• Unificar varias direcciones de una marca.
• Mantener varias cuentas separadas.

El mantenimiento funciona en Linux, macOS y Windows. Los filtros ya creados siguen actuando en Gmail con el ordenador apagado; descubrir marcas nuevas requiere ejecutar el programa.

Cada persona usa sus propias credenciales. El código empieza sin un registro de marcas de ninguna cuenta y no descarga cuerpos ni adjuntos. La automatización funciona con reglas, sin llamadas a modelos de IA.

Hoy es un proyecto abierto en desarrollo. Todavía requiere configurar Python, la API de Google y los permisos de acceso.

Para llegar a ser un producto accesible para más personas necesita mucho apoyo de la comunidad: probarlo con distintos casos, detectar errores, mejorar las instrucciones y simplificar la instalación. Las pruebas automáticas son un primer paso; queda trabajo por hacer.

Lo comparto para encontrar personas que quieran aportar a ese camino. Si te interesa probarlo, proponer mejoras o colaborar con el código y la documentación, tus aportaciones son bienvenidas en GitHub.

Idea original: ajgarciarias10. El código y la documentación se publican bajo licencia MIT: puedes usarlos, modificarlos y compartirlos conservando el aviso de copyright y la licencia.

Aquí explico cómo funciona:
https://ajgarciarias10.github.io/gmailkeeper-personal/

Código y guías:
https://github.com/ajgarciarias10/gmailkeeper-personal

¿Qué necesitarías para poder usar algo así en tu día a día?

#Automatización #Python #OpenSource #Productividad
