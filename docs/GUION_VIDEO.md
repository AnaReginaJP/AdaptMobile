# Guion del video de demostración (máximo 3 minutos)

**Antes de grabar:** túnel SSH hacia Ollama abierto, modelo ya cargado (haz una consulta de prueba) y
sesión del servidor lista en otra terminal. Archivos de ejemplo en la carpeta `demo/`.

| Tiempo | Qué se muestra | Qué se dice |
|---|---|---|
| 0:00–0:20 | Portada de la aplicación en `http://79.143.88.199` (se ve la IP en la barra) | Nombre del proyecto, problema que resuelve y que está en línea en la nube. |
| 0:20–0:45 | Registro o inicio de sesión | Cada usuario tiene un plan gratuito con créditos. |
| 0:45–1:45 | Subir `demo/package.json`; esperar el resultado | La IA (Ollama, modelo local) estima RAM, CPU y GPU y clasifica los teléfonos del dataset. |
| 1:45–2:15 | Preguntar por un teléfono concreto del catálogo | La respuesta se basa en datos reales; si el modelo no existe, lo dice. |
| 2:15–2:45 | Terminal del servidor: `systemctl status adaptmobile-backend adaptmobile-ai nginx postgresql --no-pager -n 0` y `ss -ltnp` | Solo NGINX está expuesto; el resto escucha en localhost. |
| 2:45–3:00 | Repositorio con ramas y commits del equipo | Cierre: arquitectura, SCRUM y valor del proyecto. |

**Consejos:** la IA local puede tardar minutos; si pasa del tiempo, graba la espera y acelérala al editar.
No muestres contraseñas, llaves ni archivos `.env` en pantalla.
