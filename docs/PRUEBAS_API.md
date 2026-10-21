# Pruebas de humo de la API

El script `tests/smoke_api.sh` comprueba, a través del proxy NGINX público, que la aplicación responde:

1. El catálogo de dispositivos sale del dataset (conteo, marcas, listado por región).
2. Se puede registrar un usuario nuevo y abrir sesión (JWT).
3. Las rutas protegidas rechazan peticiones sin token y aceptan las que lo traen.
4. Una contraseña incorrecta es rechazada.

El resultado real, con fecha y hora, está en `docs/evidencia_pruebas_api.txt`.

**Nota:** cada ejecución crea un usuario de prueba (`prueba_<fecha>@example.com`) en el plan gratuito.
No se prueba la subida de archivos porque invoca a la IA (Ollama) y puede tardar minutos; esa prueba se
hace manualmente y queda documentada en el video de demostración.
