# Conectar tu Gmail

Cada persona utiliza su propio proyecto y cliente OAuth. Estos pasos se hacen una vez por cuenta; las etiquetas y reglas se crean después con la herramienta.

## Si empiezas desde cero

1. Abre [Google Cloud Console](https://console.cloud.google.com/) con la cuenta que vas a organizar. Crea un proyecto, por ejemplo `Mi GmailKeeper`. Apunta el proyecto seleccionado para no configurar otro por error.
2. Ve a **APIs y servicios → Biblioteca**, busca **Gmail API** y pulsa **Habilitar**. No necesitas desplegar un servidor ni contratar una máquina virtual.
3. Abre **Google Auth Platform → Branding**. Si aparece el asistente inicial, configura el nombre de la aplicación, tu correo de soporte y tu correo de contacto.
4. En **Audience / Público**, para una cuenta Gmail personal selecciona **External / Externo**. `Internal / Interno` solo está disponible cuando corresponde a una organización Workspace.
5. Mientras el proyecto esté en **Testing / Pruebas**, añade tu dirección a **Test users / Usuarios de prueba**. Autorizar otra cuenta que no esté en esta lista puede fallar.
6. En **Data Access / Acceso a datos**, añade estos permisos:

   ```text
   https://www.googleapis.com/auth/gmail.modify
   https://www.googleapis.com/auth/gmail.settings.basic
   ```

   El primero permite leer metadatos y cambiar etiquetas. El segundo permite crear y retirar filtros. No se solicita permiso para enviar correo ni acceso a otros productos de Google.
7. En **Clients / Clientes**, pulsa **Crear cliente** y elige **Desktop app / Aplicación de escritorio**. Descarga su JSON a una carpeta privada. No crees una cuenta de servicio ni un cliente web.
8. Desde el repositorio, con el entorno Python activado, ejecuta:

   ```bash
   python gmailkeeper.py init --account tu-correo@gmail.com
   python gmailkeeper.py auth --client-secret /ruta/al/client_secret.json
   ```

   Si ya ejecutaste `init`, no lo repitas; utiliza la configuración existente. En Windows la ruta puede ser `C:\Users\TuUsuario\Downloads\client_secret.json`.
9. En el navegador, selecciona tu cuenta, revisa el nombre de la aplicación y concede los permisos. La conexión vuelve a una dirección local del ordenador; no pegues códigos de acceso en el repositorio ni en una conversación pública.
10. Comprueba el acceso:

    ```bash
    python gmailkeeper.py status
    python gmailkeeper.py preview --limit 20
    ```

La cuenta se valida antes de trabajar. Si la cuenta autorizada difiere de la del archivo de configuración, el programa se detiene.

Los nombres de las pantallas pueden variar con el idioma o cambios de Google. Referencias: [cliente de escritorio y Gmail API](https://developers.google.com/workspace/gmail/api/quickstart/python), [configuración del consentimiento](https://developers.google.com/workspace/guides/configure-oauth-consent) y [OAuth para aplicaciones de escritorio](https://developers.google.com/identity/protocols/oauth2/native-app).

## Mantener la autorización

Un proyecto externo en **Pruebas** con permisos de Gmail normalmente recibe refresh tokens que caducan a los **siete días**. Para mantenimiento personal duradero, cambia el estado del proyecto a **In production / En producción** en Audience, si Google lo permite para tu caso, y después vuelve a ejecutar `auth` para obtener una autorización nueva.

Cambiar el estado no convierte la app en una aplicación verificada ni hace que el token sea eterno. Google puede revocar el acceso por otros motivos. Cada usuario mantiene su propio cliente para uso personal; no distribuyas un único cliente sin revisar los requisitos de verificación.

Una advertencia de aplicación no verificada puede aparecer con tu proyecto personal. Continúa únicamente si reconoces el proyecto y cliente que tú has creado. Si tu organización bloquea el acceso, consulta con su administrador.

Referencias: [caducidad de refresh tokens](https://developers.google.com/identity/protocols/oauth2#expiration) y [exención de uso personal](https://developers.google.com/identity/protocols/oauth2/production-readiness/restricted-scope-verification#personal-use).

## Si ya tienes la API conectada

Puedes reutilizar un archivo de credenciales de usuario autorizado de Google, incluido el archivo de Application Default Credentials que creó `gcloud`, siempre que tenga `client_id`, `client_secret`, `refresh_token` y los permisos necesarios. El JSON descargado del cliente OAuth por sí solo todavía no es una autorización de usuario.

```bash
python gmailkeeper.py init --account tu-correo@gmail.com --credentials /ruta/a/credenciales-autorizadas.json
python gmailkeeper.py status
python gmailkeeper.py preview
```

El programa lee ese archivo y renueva el acceso sin mostrar tokens. No modifica credenciales compartidas durante el mantenimiento.

Si faltan permisos, recomendamos autorizar una copia independiente: cambia `credentials` en tu configuración por una ruta privada nueva, por ejemplo `~/.config/gmailkeeper/mi-cuenta-token.json`, y ejecuta `auth --client-secret /ruta/a/tu-cliente.json`. Así puedes mantener intacta la conexión utilizada por otras herramientas.

Si no quieres filtros nativos y el archivo solo permite `gmail.modify`, configura `"create_filters": false`. Etiquetar y archivar funcionará cuando ejecutes `sync`; no se crearán reglas de Gmail.

## Más de una cuenta

```bash
python gmailkeeper.py init --config ~/.config/gmailkeeper/personal.json --account personal@gmail.com
python gmailkeeper.py auth --config ~/.config/gmailkeeper/personal.json --client-secret /ruta/cliente-personal.json

python gmailkeeper.py init --config ~/.config/gmailkeeper/trabajo.json --account persona@example.org
python gmailkeeper.py auth --config ~/.config/gmailkeeper/trabajo.json --client-secret /ruta/cliente-trabajo.json
```

Utiliza siempre el `--config` correspondiente en los siguientes comandos y en la programación automática. Cada perfil debe tener su propio `state_dir`; el programa rechaza reutilizar el estado de otra cuenta o alcance.
