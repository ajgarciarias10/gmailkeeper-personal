# Ejecución automática

La tarea programada ejecuta:

```bash
python /ruta/gmailkeeper.py sync --config /ruta/config.json --limit 200 --apply
```

Utiliza rutas absolutas al intérprete, script y configuración. No necesita un agente de IA ni mantener una conversación abierta. Si una revisión se solapa con otra, la segunda no modifica nada y termina; el avance continúa en la siguiente ejecución.

Los filtros creados viven en Gmail y se ejecutan con el ordenador apagado. La revisión local necesita la sesión activa y conexión a internet. Reanudar el equipo permite continuar el histórico pendiente y descubrir nuevas marcas.

## Linux con systemd

Desde el repositorio con Python activado:

```bash
python install-maintenance.py install --config ~/.config/gmailkeeper/config.json --interval 3 --run-now
python install-maintenance.py status --config ~/.config/gmailkeeper/config.json
```

El instalador copia el script, tu configuración y el registro inicial de marcas a una carpeta privada en `~/.local/share/gmailkeeper/<perfil>`. Las credenciales se leen de su ruta original, no se copian. El temporizador aparece en `~/.config/systemd/user` con un identificador diferente por perfil.

La ejecución programada usa el intérprete Python base del que ejecutó el instalador. Verifica que ese intérprete seguirá instalado. El temporizador retoma una ejecución perdida cuando vuelvas a iniciar la sesión. No necesitas `sudo` ni un servidor permanente.

Tras editar la configuración, repite `install` para actualizar su copia. Si cambias el alcance, primero sigue el procedimiento de [cambio de política](CASOS-PERSONALES.md#cambiar-una-política-que-ya-está-activa).

Para detenerlo:

```bash
python install-maintenance.py remove --config ~/.config/gmailkeeper/config.json
```

La copia instalada y el estado permanecen para poder reanudarlo. Detener la tarea local no retira los filtros de Gmail.

## macOS con launchd

Mantén el repositorio y Python en una ruta estable. Crea `~/Library/LaunchAgents/org.gmailkeeper.personal.plist` con este contenido, sustituyendo todas las rutas de ejemplo por las tuyas:

```xml
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
  <key>Label</key><string>org.gmailkeeper.personal</string>
  <key>ProgramArguments</key>
  <array>
    <string>/ruta/gmailkeeper-personal/.venv/bin/python</string>
    <string>/ruta/gmailkeeper-personal/gmailkeeper.py</string>
    <string>sync</string>
    <string>--config</string><string>/Users/tuusuario/.config/gmailkeeper/config.json</string>
    <string>--limit</string><string>200</string>
    <string>--apply</string>
  </array>
  <key>StartInterval</key><integer>180</integer>
  <key>RunAtLoad</key><true/>
  <key>StandardOutPath</key><string>/Users/tuusuario/Library/Logs/gmailkeeper.log</string>
  <key>StandardErrorPath</key><string>/Users/tuusuario/Library/Logs/gmailkeeper-error.log</string>
</dict>
</plist>
```

Las rutas dentro del XML son literales: `~` no se expande. Si contienen `&`, utiliza `&amp;`. La carpeta `~/Library/LaunchAgents` debe existir. Los registros son locales; no los subas al repositorio si contienen datos de tu cuenta.

Valida el archivo:

```bash
plutil -lint ~/Library/LaunchAgents/org.gmailkeeper.personal.plist
```

Al cerrar e iniciar la sesión, launchd carga los agentes de esa carpeta. Para cargarlo en la sesión actual, puedes usar:

```bash
launchctl load ~/Library/LaunchAgents/org.gmailkeeper.personal.plist
```

`load` es la interfaz tradicional; consulta `man launchctl` si tu versión recomienda `bootstrap`. Para detener la tarea en la sesión actual:

```bash
launchctl unload ~/Library/LaunchAgents/org.gmailkeeper.personal.plist
```

Mueve el `.plist` fuera de `LaunchAgents` si no quieres que se cargue al volver a iniciar sesión. Para otra cuenta usa otro `Label`, nombre de archivo y `--config`.

Referencia: [agentes de usuario y programación con launchd, Apple](https://developer.apple.com/library/archive/documentation/MacOSX/Conceptual/BPSystemStartup/Chapters/CreatingLaunchdJobs.html).

## Windows con el Programador de tareas

Abre **Programador de tareas → Crear tarea**:

1. En **General**, pon un nombre propio, por ejemplo `GmailKeeper Personal`, y selecciona ejecutar únicamente cuando tu usuario haya iniciado sesión. No requiere privilegios elevados.
2. En **Desencadenadores**, crea una programación diaria que repita la tarea cada **3 minutos** durante **1 día**; así vuelve a programarse el día siguiente. Puedes añadir también un desencadenador al iniciar sesión.
3. En **Acciones**, selecciona iniciar un programa. En **Programa**, usa la ruta absoluta a `.venv\Scripts\python.exe`.
4. En **Argumentos**, indica:

   ```text
   "C:\ruta\gmailkeeper-personal\gmailkeeper.py" sync --config "C:\Users\TuUsuario\.config\gmailkeeper\config.json" --limit 200 --apply
   ```

5. En **Iniciar en**, pon la carpeta del repositorio. En **Configuración**, selecciona ejecutar cuanto antes una programación perdida y **no iniciar una instancia nueva** si ya se está ejecutando.
6. Guarda y pulsa **Ejecutar**. Consulta el resultado de la última ejecución y comprueba el avance con `python gmailkeeper.py status`.

Las rutas deben apuntar a tu usuario y a una instalación de Python que mantengas. Para detenerlo, deshabilita esta tarea. Para otra cuenta crea otra tarea y cambia el `--config`.

Referencia: [desencadenadores y repetición de tareas, Microsoft](https://learn.microsoft.com/en-us/powershell/module/scheduledtasks/new-scheduledtasktrigger).

## Detener también el archivado en el servidor

Primero desactiva la tarea del sistema operativo. Después, con el mismo perfil:

```bash
python gmailkeeper.py remove-filters --config /ruta/config.json --apply
```

Solo elimina los filtros que este perfil registró como creados por él. Conserva los demás filtros, mensajes y etiquetas. Si perdiste su estado local, revisa manualmente **Gmail → Configuración → Filtros y direcciones bloqueadas**; la herramienta no asumirá que todos los filtros de la cuenta son suyos.
