# GmailKeeper Personal

Organiza tu Gmail con tres instrucciones:

1. **Identifica quién envía cada mensaje.** Agrupa las direcciones de una marca bajo el mismo nombre.
2. **Añade su etiqueta si falta.** Crea subetiquetas dentro de la categoría correspondiente y conserva las etiquetas que ya tengas.
3. **Archiva automáticamente.** Retira el mensaje de Recibidos sin borrarlo ni cambiar si está leído.

Cada persona utiliza su propia cuenta, configuración y cliente OAuth de Google. El mantenimiento corre en su ordenador; los filtros que crea se guardan en Gmail. No utiliza modelos de IA ni un servidor del proyecto.

```text
Archivo/
├── Promociones/
│   ├── Amazon
│   └── IKEA
├── Actualizaciones/
│   ├── Amazon
│   └── PayPal
└── Social/
    └── LinkedIn
```

Son ejemplos de estructura. El registro de marcas empieza vacío. Las etiquetas reales se crean a partir del correo de cada cuenta, mediante detección automática o sus reglas personales. Si un mensaje no se puede asociar a una marca con suficiente confianza, se archiva en su categoría y recibe `Archivo/Pendiente de marca`.

## Qué necesitas

- Una cuenta con Gmail habilitado, personal o de Workspace si tu organización permite esta aplicación.
- Un ordenador con **Python 3.10 o posterior**, Git y un navegador.
- Un proyecto de Google Cloud con Gmail API activada y un cliente OAuth de tipo **Aplicación de escritorio**. La guía muestra cómo crearlo.

El programa de mantenimiento funciona en Linux, macOS y Windows. El instalador automático incluido utiliza systemd en Linux; para los otros sistemas hay instrucciones de programación de tareas.

## Empieza desde cero

### 1. Descarga e instala

```bash
git clone https://github.com/ajgarciarias10/gmailkeeper-personal.git
cd gmailkeeper-personal
python3 -m venv .venv
```

Activa el entorno:

| Sistema | Comando |
|---|---|
| Linux / macOS | `source .venv/bin/activate` |
| Windows, PowerShell | `.venv\Scripts\Activate.ps1` |
| Windows, CMD | `.venv\Scripts\activate.bat` |

En Windows puedes usar `py -3` en lugar de `python3` para crear el entorno. Si PowerShell bloquea la activación, utiliza directamente `.venv\Scripts\python.exe` donde la guía indica `python`.

```bash
python -m pip install -r requirements.txt
```

La dependencia sirve para conectar la cuenta; el mantenimiento utiliza la biblioteca estándar de Python.

### 2. Prepara tu cuenta y las reglas

```bash
python gmailkeeper.py init --account tu-correo@gmail.com
```

El programa indica dónde ha guardado tu configuración. Por defecto es `~/.config/gmailkeeper/config.json`; contiene rutas privadas separadas para las credenciales y el estado de tu cuenta.

**Por defecto se archiva todo el correo recibido que entre en el alcance**, incluidos avisos y facturas. Se excluyen enviados, borradores, chats, spam y papelera. Si prefieres solo promociones o dejar ciertos remitentes en Recibidos, configura tu caso antes de aplicar: [casos personales y opciones](docs/CASOS-PERSONALES.md).

### 3. Conecta Gmail

Sigue [la guía de Google y OAuth](docs/CONECTAR-GMAIL.md) para activar la API, configurar el acceso personal y descargar tu archivo de cliente OAuth. Después:

```bash
python gmailkeeper.py auth --client-secret /ruta/al/client_secret.json
```

Selecciona la misma cuenta que has configurado y concede los permisos. El navegador vuelve al programa y las credenciales se guardan en una ruta privada. Si autorizas otra cuenta, el programa se detiene sin guardarlas.

¿Ya tienes la API conectada? La guía incluye [cómo reutilizar credenciales existentes](docs/CONECTAR-GMAIL.md#si-ya-tienes-la-api-conectada).

### 4. Revisa una muestra

```bash
python gmailkeeper.py preview --limit 20
```

Muestra qué etiquetas añadiría y qué correo archivaría. **No modifica mensajes, etiquetas ni filtros en Gmail.** Guarda una muestra privada para comprobar el resultado después. La vista previa contiene hasta 50 mensajes recientes; no representa un inventario completo.

### 5. Aplica la organización

```bash
python gmailkeeper.py bootstrap --apply
python gmailkeeper.py verify
```

`bootstrap` crea los filtros generales de archivo por categoría, archiva los mensajes de Recibidos dentro del alcance y clasifica el histórico de las marcas configuradas. Conserva las etiquetas existentes. `verify` comprueba la muestra anterior, su estado de lectura y los filtros previos.

El resto del histórico y las marcas nuevas se revisan por tandas:

```bash
python gmailkeeper.py sync --limit 200 --apply
python gmailkeeper.py status
```

Repite `sync` hasta que `backfill_remaining` llegue a cero, o activa la ejecución automática. El avance se guarda; cerrar el programa no obliga a empezar desde cero. Los mensajes nuevos tienen prioridad sobre el histórico pendiente.

### 6. Déjalo automático

En Linux con systemd:

```bash
python install-maintenance.py install --interval 3 --run-now
python install-maintenance.py status
```

Instala una copia de tu configuración y el script en una carpeta privada, con un temporizador cada tres minutos. No necesita `sudo`. Después de editar tus reglas, repite `install` para actualizar la copia.

Para macOS y Windows, sigue [la guía de automatización](docs/AUTOMATIZACION.md).

## Qué funciona con el ordenador apagado

Los filtros guardados en Gmail siguen archivando el correo y aplicando las combinaciones de marca y categoría para las que ya existe una regla. Descubrir una marca nueva, cubrir una nueva combinación de categoría y revisar el histórico pendiente requiere ejecutar `sync` en tu ordenador. El trabajo continúa al volver a iniciar la sesión.

Los filtros no borran correo ni lo marcan como leído. Cuando la herramienta resuelve una marca pendiente, retira únicamente su propia etiqueta de pendientes.

## Personaliza tu caso

| Necesidad | Qué configurar |
|---|---|
| Archivar todo lo recibido | Configuración predeterminada |
| Archivar solo promociones | `"query": "category:promotions"` |
| Mantener alertas o familiares en Recibidos | `exclude_senders` con sus direcciones o dominios |
| Unificar varias direcciones de una empresa | `brands` con sus dominios y el mismo nombre |
| Nombrar un remitente personal | Una dirección completa en `brands` |
| Usar otra etiqueta principal | `label_prefix` |
| Revisar siempre las marcas antes de aceptarlas | `"learn_brands": false` y reglas manuales en `brands` |
| Ejecutar sin crear filtros nativos | `"create_filters": false` y programación de `sync` |
| Mantener dos cuentas separadas | Un archivo `--config` y un `state_dir` por cuenta |

Encontrarás los ejemplos completos y cómo cambiar una configuración ya activa en [CASOS-PERSONALES.md](docs/CASOS-PERSONALES.md).

## Cómo detenerlo

En Linux:

```bash
python install-maintenance.py remove
```

Esto detiene la revisión local. Para detener también los filtros que ha creado este perfil en Gmail:

```bash
python gmailkeeper.py remove-filters --apply
```

Conserva los mensajes, las etiquetas y los filtros que ya existían antes. No devuelve automáticamente a Recibidos el correo archivado; puedes localizarlo por sus etiquetas y moverlo a Recibidos desde Gmail.

## Coste y privacidad

No hay suscripción de este proyecto, alojamiento contratado ni llamadas a IA de pago. Google ofrece el uso estándar de Gmail API sin coste adicional y anuncia posibles cargos futuros por superar el umbral diario de 80 millones de unidades. Consulta sus [condiciones actuales](https://developers.google.com/workspace/gmail/api/reference/quota); esta herramienta procesa tandas pequeñas y limita su velocidad.

Las credenciales, el estado, la muestra de verificación y los identificadores de mensajes se guardan localmente, fuera del repositorio, con permisos privados en sistemas POSIX. En Windows se utilizan carpetas del usuario y sus permisos de acceso. Se consulta el remitente y las etiquetas; no se descargan cuerpos ni adjuntos. Las conexiones del programa son con los servicios OAuth y Gmail de Google.

Cada usuario crea su propio cliente OAuth para uso personal. Publicar este código no equivale a ofrecer una aplicación OAuth común verificada para todos. [Explicación de Google](https://developers.google.com/identity/protocols/oauth2/production-readiness/restricted-scope-verification#personal-use).

## Problemas y desarrollo

- [Solución de problemas](docs/PROBLEMAS.md): permisos, tokens que caducan, límites, marcas pendientes y temporizadores.
- [Contribuir y ejecutar pruebas](CONTRIBUTING.md).

Licencia [MIT](LICENSE).
