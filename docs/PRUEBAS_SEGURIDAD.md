# Pruebas de seguridad de la exposición de servicios

**Objetivo:** comprobar que solo NGINX (puerto 80) es accesible desde internet y que el backend, la IA, la
base de datos y Ollama quedan detrás del proxy inverso.

**Método:** el script `deploy/verificar_seguridad.sh` se ejecuta desde una computadora externa al servidor.
Intenta abrir una conexión TCP a cada puerto interno y consulta el sitio por el puerto 80.

| Prueba | Resultado esperado |
|---|---|
| `GET http://IP/` | HTTP 200 (frontend servido por NGINX) |
| `GET http://IP/api/devices/count` | HTTP 200 (proxy hacia el backend) |
| Puerto 8000 (backend) | Cerrado desde internet |
| Puerto 8001 (servicio de IA) | Cerrado desde internet |
| Puerto 5432 (PostgreSQL) | Cerrado desde internet |
| Puerto 11434 (Ollama) | Cerrado desde internet |

**Resultado real:** ver `docs/evidencia_seguridad.txt` (generado al ejecutar el script, con fecha y hora).

**Por qué funciona:** en el servidor, esos servicios escuchan solo en `127.0.0.1`
(`ss -ltnp` lo muestra), por lo que únicamente son alcanzables a través de NGINX o por SSH.

**Limitaciones:** una conexión rechazada también puede deberse a un firewall de tu red; conviene repetir la prueba
desde otra red (por ejemplo datos móviles). El puerto 22 (SSH) sigue público para administrar el servidor.
