# Solución de problemas

## Falta la configuración

Ejecuta `python gmailkeeper.py init --account tu-correo@gmail.com`. Para una configuración en otra ruta, indica `--config /ruta/config.json` en todos los comandos. `init` no sobrescribe un archivo existente.

## La cuenta autorizada no coincide

Comprueba `account` y el archivo `credentials` de tu configuración. Autoriza la cuenta esperada con `auth --client-secret ...`. No reutilices el mismo `state_dir` entre cuentas. La herramienta se detiene antes de modificar mensajes de una cuenta inesperada.

## Faltan permisos o aparece HTTP 403

Comprueba que Gmail API está habilitada en el proyecto del cliente OAuth, que el acceso no está bloqueado por Workspace y que has autorizado `gmail.modify` y `gmail.settings.basic`. Consultar filtros no prueba que puedas crearlos. Repite `auth` después de modificar los permisos.

Si has configurado `create_filters: false`, basta con `gmail.modify` para el mantenimiento. Los filtros previamente creados siguen activos hasta que los retires.

## `invalid_grant` o el acceso caduca a los siete días

Revisa el estado del proyecto OAuth. En Pruebas, los permisos de Gmail limitan normalmente el refresh token a siete días. Sigue [Mantener la autorización](CONECTAR-GMAIL.md#mantener-la-autorización) y vuelve a autorizar. También puede haberse revocado la conexión desde Google.

## El histórico avanza despacio o aparecen límites

Cada lectura de metadatos consume cuota. GmailKeeper limita la velocidad, procesa tandas pequeñas y reintenta errores temporales. No lo ejecutes simultáneamente desde muchas herramientas con el mismo proyecto. `status` muestra cuántos mensajes quedan; un histórico grande se completa gradualmente.

Si no hay conexión, la ejecución puede terminar con un error; la siguiente tarea programada reintenta el trabajo pendiente. La cola no se avanza si falla una modificación. No aumentes el límite por encima de 250; el límite recomendado para la programación es 200.

## Otra revisión está en curso

Es una ejecución solapada. La segunda termina sin modificar Gmail. Espera a que acabe la primera. La revisión de estado y vista previa son de lectura y no bloquean el mantenimiento.

## Una marca queda pendiente o tiene un nombre mejorable

El nombre visible por sí solo no basta. Añade una regla explícita a `brands` usando su dominio corporativo o dirección completa. Para varias direcciones o dominios utiliza el mismo nombre. Los remitentes personales se resuelven con su dirección completa, no con el dominio del proveedor.

El nombre aprendido puede necesitar una corrección humana: la heurística no conoce todas las empresas, sufijos públicos o plataformas de envío compartidas. Las reglas manuales tienen prioridad. Para revisar nombres antes de aceptarlos automáticamente, desactiva `learn_brands`. Consulta cómo [revisar pendientes antiguos](CASOS-PERSONALES.md#caso-4-unificar-marcas-y-poner-nombres-propios).

## Cambié las reglas pero sigue archivando igual

El filtro anterior sigue en Gmail o la tarea utiliza una copia antigua de la configuración. Sigue [Cambiar una política](CASOS-PERSONALES.md#cambiar-una-política-que-ya-está-activa): detén la tarea, retira los filtros del perfil con la configuración antigua, utiliza un estado nuevo y aplica la nueva política. Reinstala la copia Linux.

## Llegué al límite de filtros

Gmail permite como máximo 1.000 filtros. La herramienta deja de crear nuevos cerca de ese límite y continúa clasificando y archivando mediante `sync`. Revisa reglas antiguas en Gmail. Fuente: [creación de filtros, Google](https://developers.google.com/workspace/gmail/api/reference/rest/v1/users.settings.filters/create).

## La comprobación indica que cambió el estado de lectura

`verify` compara la muestra tomada por `preview`. Leer o etiquetar esos mensajes desde Gmail entre ambos comandos también cambia el resultado. Revisa los mensajes afectados y toma una muestra nueva. El programa solo retira `INBOX` y su propia etiqueta de pendientes, y añade etiquetas; no retira `UNREAD`.

## No tengo systemd

Usa el programador disponible en tu sistema con el comando `sync --apply`, rutas absolutas y tu `--config`. El mantenimiento no depende de systemd; solamente el instalador Linux. Consulta [AUTOMATIZACION.md](AUTOMATIZACION.md).
