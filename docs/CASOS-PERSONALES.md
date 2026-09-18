# Configura tu caso personal

Ejecuta `init` y edita el archivo de configuración que indica el programa, antes de la primera aplicación. Conserva las rutas que ha generado para tu cuenta; los fragmentos siguientes muestran solo las opciones que debes cambiar.

Después de editar, utiliza `preview` y revisa el campo **Alcance**. `--apply` aplica la política a todos los mensajes dentro de ese alcance; la vista previa es una muestra.

## Caso 1: archivar todo y agrupar por marca

La configuración predeterminada implementa las tres instrucciones originales:

```json
{
  "label_prefix": "Archivo",
  "query": "",
  "exclude_senders": [],
  "brands": {},
  "learn_brands": true,
  "create_filters": true
}
```

```bash
python gmailkeeper.py preview
python gmailkeeper.py bootstrap --apply
python gmailkeeper.py verify
python gmailkeeper.py sync --limit 200 --apply
```

Conserva las etiquetas existentes, incluida una etiqueta de familia o trabajo. Añade la subetiqueta por marca aunque el mensaje ya tenga otra etiqueta. El estado de leído no cambia.

## Caso 2: solo promociones

```json
{
  "query": "category:promotions",
  "exclude_senders": []
}
```

Solo se archivan y etiquetan los mensajes que Gmail clasifica como promociones. Actualizaciones, correo personal y otras categorías permanecen fuera del alcance. Esta restricción también se comprueba durante la revisión del historial de mensajes nuevos.

También puedes usar una búsqueda de Gmail por remitente, asunto o categoría; por ejemplo `from:news.example.org`. Para filtros de entrega evita reglas que dependan de etiquetas añadidas después de recibir el mensaje o de un estado de la interfaz como `in:inbox`.

## Caso 3: dejar algunos remitentes en Recibidos

```json
{
  "query": "",
  "exclude_senders": [
    "no-reply@accounts.google.com",
    "persona@example.org",
    "miempresa.example.org"
  ]
}
```

Las exclusiones se incorporan tanto a la búsqueda del histórico como a los filtros nuevos y a la revisión periódica. Usa direcciones completas para excluir a una persona; un dominio excluye el correo que coincida con él.

La herramienta no retira filtros de otros programas. Si uno de esos filtros ya archiva un remitente excluido, revísalo en Gmail.

## Caso 4: unificar marcas y poner nombres propios

```json
{
  "brands": {
    "amazon.es": "Amazon",
    "amazon.com": "Amazon",
    "news.example.org": "Mi tienda",
    "pedidos@proveedor.example.org": "Mi tienda",
    "ana@example.org": "Ana",
    "padre@example.net": "Papá"
  }
}
```

Los dominios aceptan sus subdominios. Una dirección completa tiene prioridad sobre la regla del dominio: puedes separar una dirección concreta de las demás. Varias claves con el mismo nombre comparten la subetiqueta en cada categoría.

No asignes `gmail.com` a una persona: agruparía el correo de muchas cuentas bajo su nombre. Utiliza su dirección completa. Los proveedores de correo personal nunca se aprenden automáticamente como marcas.

`brands.json` empieza vacío: no incluye marcas ni remitentes de ninguna cuenta. La detección automática aprende las marcas durante `sync`; puedes añadir tus propias reglas para fijar los nombres. Puedes reemplazar `brands_file` por otro archivo local con el mismo formato o poner `null` para empezar solo con tus reglas. Las reglas explícitas de `brands` tienen prioridad sobre las aprendidas. Los nombres no deben contener `/` ni caracteres de control; las categorías y el prefijo aportan la estructura.

La detección automática exige coincidencia entre nombre y dominio corporativo. Es una heurística conservadora, no una consulta a una base universal de empresas. Para revisar todos los nombres manualmente:

```json
{
  "learn_brands": false
}
```

Los desconocidos se archivan y quedan pendientes. Para resolver pendientes antiguos de un remitente tras añadir una regla, crea un perfil de revisión con otro `state_dir` y `query` limitado a ese remitente; ejecuta sus tandas hasta vaciar la cola. Al reconocerlo se retira la etiqueta propia de pendientes.

## Caso 5: otra estructura de etiquetas

```json
{
  "label_prefix": "Correo organizado"
}
```

Obtendrás `Correo organizado/Promociones/Marca`, `Correo organizado/Actualizaciones/Marca`, etc. También admite un prefijo anidado como `Correo/Archivo`. Gmail determina las categorías; la herramienta no inventa el tipo de mensaje a partir de su asunto.

## Caso 6: sin filtros nativos

```json
{
  "create_filters": false
}
```

En este caso etiqueta y archiva cuando ejecutas `sync`. Necesita ejecución periódica para mantener la bandeja; no creará nuevas reglas en Gmail. Si antes creaste filtros, desactivar esta opción no los retira: utiliza `remove-filters --apply` primero.

## Caso 7: varias cuentas

Usa `init --config /ruta/personal.json --account ...` y otro `init --config /ruta/trabajo.json --account ...`. El programa genera rutas de credenciales y estado separadas por cuenta. Consulta [la conexión de varias cuentas](CONECTAR-GMAIL.md#más-de-una-cuenta).

Todos los comandos y tareas programadas deben indicar el `--config` que corresponde. Los temporizadores Linux tienen nombres distintos por perfil.

## Cambiar una política que ya está activa

Cambiar el archivo local no elimina las reglas que ya existen en Gmail. Por ejemplo, si antes archivabas todo y ahora quieres solo promociones, el filtro anterior seguiría archivando las demás categorías.

1. Detén la revisión local con el programador correspondiente. En Linux: `python install-maintenance.py remove --config /ruta/config.json`.
2. Con la configuración antigua, retira sus filtros: `python gmailkeeper.py remove-filters --config /ruta/config.json --apply`.
3. Edita la política y cambia `state_dir` a una carpeta privada nueva. Esto evita reutilizar una cola o historial de otro alcance. Mantén tus credenciales si la cuenta es la misma.
4. Repite `preview`, `bootstrap --apply` y `verify` con esa configuración.
5. Instala o actualiza su tarea automática. En Linux: `python install-maintenance.py install --config /ruta/config.json`.

El correo ya archivado no vuelve automáticamente a Recibidos. Las etiquetas anteriores se conservan; si quieres reorganizarlas también, revisa el resultado y limpia las etiquetas que hayan quedado vacías desde Gmail.

## Referencia de configuración

| Campo | Significado |
|---|---|
| `account` | Cuenta esperada; se valida con Gmail antes de actuar |
| `credentials` | Archivo local de credenciales autorizadas, no el JSON del cliente sin autorizar |
| `state_dir` | Carpeta privada exclusiva para la cuenta y política |
| `brands_file` | Registro inicial de nombres, o `null` |
| `brands` | Reglas personales por dominio o dirección completa |
| `label_prefix` | Raíz de las etiquetas, por defecto `Archivo` |
| `query` | Búsqueda adicional de Gmail, por defecto todo lo recibido elegible |
| `exclude_senders` | Lista de direcciones o dominios fuera del alcance |
| `learn_brands` | Aprender nombres automáticamente, por defecto `true` |
| `create_filters` | Crear filtros nativos, por defecto `true` |

Las rutas pueden ser absolutas, comenzar por `~` o ser relativas al archivo de configuración. Mantén el archivo personal fuera del repositorio que compartes.
