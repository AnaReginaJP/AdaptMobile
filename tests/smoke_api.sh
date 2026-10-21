#!/usr/bin/env bash
# Pruebas de humo de la API pública (a través de NGINX). No usa la IA, así que es rápida.
# Uso: bash tests/smoke_api.sh [IP]      (por defecto 79.143.88.199)
IP="${1:-${IP:-79.143.88.199}}"
BASE="http://$IP/api"
FALLOS=0
EMAIL="prueba_$(date +%s)@example.com"
PASS="Prueba-12345"

check() {  # check "nombre" "codigo_obtenido" "codigos_esperados (separados por |)"
  if [[ "|$3|" == *"|$2|"* ]]; then echo "OK     $1 (HTTP $2)"
  else echo "FALLO  $1 (HTTP $2, se esperaba $3)"; FALLOS=$((FALLOS+1)); fi
}
json_campo() { python3 -c "import sys,json; print(json.load(sys.stdin).get('$1',''))" 2>/dev/null; }

echo "Fecha: $(date)"
echo "API probada: $BASE"
echo "----------------------------------------------"

c=$(curl -m 15 -s -o /dev/null -w "%{http_code}" "$BASE/devices/count");              check "Conteo de dispositivos" "$c" "200"
c=$(curl -m 15 -s -o /dev/null -w "%{http_code}" "$BASE/devices/brands?region=mx");   check "Marcas disponibles (MX)" "$c" "200"
c=$(curl -m 15 -s -o /dev/null -w "%{http_code}" "$BASE/devices?region=mx&skip=0&limit=3"); check "Listado de dispositivos (MX)" "$c" "200"

r=$(curl -m 20 -s -w "\n%{http_code}" -X POST "$BASE/auth/register" -H "Content-Type: application/json" \
     -d "{\"email\":\"$EMAIL\",\"password\":\"$PASS\",\"full_name\":\"Usuario de prueba\"}")
c=$(echo "$r" | tail -1); check "Registro de usuario" "$c" "200"

r=$(curl -m 20 -s -w "\n%{http_code}" -X POST "$BASE/auth/login-json" -H "Content-Type: application/json" \
     -d "{\"email\":\"$EMAIL\",\"password\":\"$PASS\"}")
c=$(echo "$r" | tail -1); check "Inicio de sesión" "$c" "200"
TOKEN=$(echo "$r" | sed '$d' | json_campo access_token)

c=$(curl -m 15 -s -o /dev/null -w "%{http_code}" "$BASE/auth/me");                    check "Perfil sin token es rechazado" "$c" "401|403"
c=$(curl -m 15 -s -o /dev/null -w "%{http_code}" -H "Authorization: Bearer $TOKEN" "$BASE/auth/me"); check "Perfil con token válido" "$c" "200"
c=$(curl -m 15 -s -o /dev/null -w "%{http_code}" -X POST "$BASE/auth/login-json" -H "Content-Type: application/json" \
     -d "{\"email\":\"$EMAIL\",\"password\":\"incorrecta\"}");                         check "Contraseña incorrecta es rechazada" "$c" "401"

echo "----------------------------------------------"
if [ "$FALLOS" -eq 0 ]; then echo "RESULTADO: todas las pruebas pasaron"; else echo "RESULTADO: $FALLOS prueba(s) fallaron"; fi
exit "$FALLOS"
