# Contribuir

Requisitos: Python 3.10 o posterior. Las pruebas del mantenimiento usan la biblioteca estándar y dobles de la API; no requieren conectar una cuenta ni credenciales reales.

```bash
python -m unittest -v
python gmailkeeper.py --help
python install-maintenance.py --help
```

Principios de cambios:

- Validar la cuenta esperada antes de modificar mensajes.
- Conservar las etiquetas previas y el estado de lectura.
- Archivar retirando `INBOX`; no añadir funciones de borrado como efecto secundario.
- Respetar búsquedas y exclusiones también para los mensajes que llegan por historial.
- Mantener el estado por cuenta y política, y no avanzar la cola tras un error.
- Reutilizar etiquetas y filtros existentes; registrar solo los filtros nuevos como propios.
- No incluir cuentas reales, tokens, identificadores de mensajes o registros personales en ejemplos, pruebas e issues.

Las pruebas cubren la clasificación, restricciones, aislamiento de cuentas, vista previa, repetición segura y fallos de escritura. Las tareas de integración continua comprueban Linux, macOS y Windows. La programación de tareas y el consentimiento real de Google deben probarse en el sistema correspondiente; los tests no sustituyen esa comprobación.

Al añadir marcas comunes a `brands.json`, usa dominios oficiales y nombres consistentes. Para reglas específicas de una persona usa su configuración privada en lugar del registro público.
