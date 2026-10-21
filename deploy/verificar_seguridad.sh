#!/usr/bin/env bash
# Verifica desde FUERA del servidor que solo el puerto 80 es público.
# Uso: bash deploy/verificar_seguridad.sh [IP]     (por defecto 79.143.88.199)
IP="${1:-${IP:-79.143.88.199}}"
FALLOS=0

puerto_abierto() { timeout 5 bash -c "</dev/tcp/$IP/$1" 2>/dev/null; }

debe_estar_cerrado() {
  if puerto_abierto "$2"; then echo "FALLO  $1 (puerto $2) está ABIERTO desde internet"; FALLOS=$((FALLOS+1))
  else echo "OK     $1 (puerto $2) cerrado desde internet"; fi
}

echo "Fecha: $(date)"
echo "Servidor probado: $IP"
echo "----------------------------------------------"
codigo=$(curl -m 10 -s -o /dev/null -w "%{http_code}" "http://$IP/")
if [ "$codigo" = "200" ]; then echo "OK     NGINX responde en el puerto 80 (HTTP $codigo)"
else echo "FALLO  NGINX no responde 200 en el puerto 80 (HTTP $codigo)"; FALLOS=$((FALLOS+1)); fi

codigo=$(curl -m 15 -s -o /dev/null -w "%{http_code}" "http://$IP/api/devices/count")
if [ "$codigo" = "200" ]; then echo "OK     El proxy /api/ llega al backend (HTTP $codigo)"
else echo "FALLO  El proxy /api/ no llega al backend (HTTP $codigo)"; FALLOS=$((FALLOS+1)); fi

debe_estar_cerrado "Backend FastAPI" 8000
debe_estar_cerrado "Servicio de IA" 8001
debe_estar_cerrado "PostgreSQL" 5432
debe_estar_cerrado "Ollama" 11434
echo "----------------------------------------------"
if [ "$FALLOS" -eq 0 ]; then echo "RESULTADO: todas las pruebas pasaron"; else echo "RESULTADO: $FALLOS prueba(s) fallaron"; fi
exit "$FALLOS"
