# Evidencia del despliegue en la nube

**Servidor:** 79.143.88.199 (Ubuntu, disco de 5 GB)
**Aplicación:** http://79.143.88.199
**Responsable:** Ana Regina Jaramillo P.

## Decisión técnica
Docker Compose no pudo ejecutarse en el servidor por falta de espacio (`no space left on device`).
Se desplegó de forma nativa con `deploy/deploy_nativo.sh`: PostgreSQL local, entorno virtual de Python,
servicios systemd y NGINX como proxy inverso.

## Servicios
| Servicio | Escucha en | Acceso |
|---|---|---|
| NGINX (web + proxy `/api/`) | 0.0.0.0:80 | Público |
| adaptmobile-backend (FastAPI) | 127.0.0.1:8000 | Solo local |
| adaptmobile-ai (FastAPI) | 127.0.0.1:8001 | Solo local |
| PostgreSQL | 127.0.0.1:5432 | Solo local |
| Ollama (vía túnel SSH inverso) | 127.0.0.1:11434 | Solo local |

## Comandos de verificación (ejecutados en el servidor)
```bash
systemctl status adaptmobile-ai adaptmobile-backend nginx --no-pager
ss -ltnp
curl -s http://127.0.0.1:8001/health
curl -s -o /dev/null -w '%{http_code}\n' http://127.0.0.1/api/devices/brands?region=mx
```

## Prueba de puertos cerrados (desde una computadora externa)
```bash
curl -s -o /dev/null -w '%{http_code}\n' --max-time 5 http://79.143.88.199:8000/health   # sin respuesta (000)
curl -s -o /dev/null -w '%{http_code}\n' --max-time 5 http://79.143.88.199:8001/health   # sin respuesta (000)
timeout 5 bash -c '</dev/tcp/79.143.88.199/5432' && echo abierto || echo cerrado
```
Resultado obtenido: 8000 y 8001 sin respuesta (000) y 5432 cerrado; solo el puerto 80 atiende desde Internet.

## Capturas
Agregar en `docs/img/`: salida de `ss -ltnp`, estado de los servicios y la aplicación funcionando.
