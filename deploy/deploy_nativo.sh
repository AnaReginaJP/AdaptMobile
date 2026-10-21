#!/usr/bin/env bash
# Despliegue de AdaptMobile SIN Docker (PostgreSQL + Python venv + Nginx + systemd).
# Pensado para Ubuntu con poco disco. Ejecutar como root:  bash deploy_nativo.sh
# Se puede repetir: no duplica nada si ya se corrió antes.
set -euo pipefail

APP=/opt/Los_Telefonos
WEB="$APP/AdaptMobile/web/src"
SERVER_IP="79.143.88.199"
MIN_MB=250

paso() { printf '\n\033[1;34m== %s\033[0m\n' "$*"; }
libre_mb() { df --output=avail -BM / | tail -1 | tr -dc '0-9'; }
pg() { (cd /tmp && runuser -u postgres -- "$@"); }

[ "$(id -u)" -eq 0 ] || { echo "Ejecuta como root."; exit 1; }
[ -f "$APP/.env" ] || { echo "No existe $APP/.env (se crea en el paso de configuración anterior)."; exit 1; }
[ -d "$APP/AdaptMobile/backend" ] || { echo "No encuentro $APP/AdaptMobile. ¿Descomprimiste el zip en /opt?"; exit 1; }

paso "1/7 Paquetes (PostgreSQL, Nginx, Python venv)"
echo "Espacio libre antes: $(libre_mb) MB"
apt-get update -qq
DEBIAN_FRONTEND=noninteractive apt-get install -y -qq --no-install-recommends postgresql nginx python3-venv
apt-get clean
echo "Espacio libre ahora: $(libre_mb) MB"
if [ "$(libre_mb)" -lt "$MIN_MB" ]; then
  echo "Quedan menos de ${MIN_MB} MB libres: no sigo para no llenar el disco." >&2
  exit 1
fi
systemctl enable --now postgresql >/dev/null

paso "2/7 Base de datos"
set -a; . "$APP/.env"; set +a
pg psql -v ON_ERROR_STOP=1 -q <<SQL
DO \$\$ BEGIN
  IF NOT EXISTS (SELECT FROM pg_roles WHERE rolname = 'adaptmobile') THEN
    CREATE ROLE adaptmobile LOGIN PASSWORD '${POSTGRES_PASSWORD}';
  ELSE
    ALTER ROLE adaptmobile PASSWORD '${POSTGRES_PASSWORD}';
  END IF;
END \$\$;
SQL
pg psql -tAc "SELECT 1 FROM pg_database WHERE datname='adaptmobile'" | grep -q 1 \
  || pg createdb -O adaptmobile adaptmobile
echo "Base 'adaptmobile' lista."

paso "3/7 Entorno Python y dependencias"
[ -x "$APP/venv/bin/python" ] || python3 -m venv "$APP/venv"
"$APP/venv/bin/pip" install -q --no-cache-dir --only-binary=:all: \
  -r "$APP/AdaptMobile/backend/requirements.txt"
echo "Espacio libre ahora: $(libre_mb) MB"

paso "4/7 Usuario de servicio y variables de entorno"
id adaptmobile >/dev/null 2>&1 || useradd --system --no-create-home --home-dir "$APP" \
  --shell /usr/sbin/nologin adaptmobile
cat > "$APP/adaptmobile.env" <<EOF
DATABASE_URL=postgresql+psycopg2://adaptmobile:${POSTGRES_PASSWORD}@127.0.0.1:5432/adaptmobile
AI_SERVICE_URL=http://127.0.0.1:8001
SECRET_KEY=${SECRET_KEY}
ACCESS_TOKEN_EXPIRE_MINUTES=1440
DATA_CSV_PATH=$APP/AdaptMobile/database/processed_data2.csv
DATA_JSON_PATH=$APP/AdaptMobile/database/data.json
ADMIN_EMAIL=${ADMIN_EMAIL}
ADMIN_PASSWORD=${ADMIN_PASSWORD}
AI_ADMIN_TOKEN=${AI_ADMIN_TOKEN}
FRONTEND_URL=http://${SERVER_IP}
AI_PROVIDER=${AI_PROVIDER:-heuristic}
DEEPSEEK_API_KEY_FILE=$APP/secrets/deepseek_api_key
DEEPSEEK_BASE_URL=${DEEPSEEK_BASE_URL:-https://api.deepseek.com}
DEEPSEEK_MODEL=${DEEPSEEK_MODEL:-deepseek-chat}
MAX_AGE_YEARS=${MAX_AGE_YEARS:-5}
EOF
chown root:adaptmobile "$APP/adaptmobile.env"
chmod 640 "$APP/adaptmobile.env"
chmod -R a+rX "$APP/AdaptMobile" "$APP/venv"
if [ -d "$APP/secrets" ]; then
  chown -R adaptmobile:adaptmobile "$APP/secrets"
  chmod 700 "$APP/secrets"
fi

paso "5/7 Servicios systemd (IA y backend)"
cat > /etc/systemd/system/adaptmobile-ai.service <<EOF
[Unit]
Description=AdaptMobile - microservicio de IA
After=network.target

[Service]
User=adaptmobile
WorkingDirectory=$APP/AdaptMobile/ai
EnvironmentFile=$APP/adaptmobile.env
Environment=PYTHONDONTWRITEBYTECODE=1
ExecStart=$APP/venv/bin/uvicorn app.main:app --host 127.0.0.1 --port 8001
Restart=always
RestartSec=3

[Install]
WantedBy=multi-user.target
EOF
cat > /etc/systemd/system/adaptmobile-backend.service <<EOF
[Unit]
Description=AdaptMobile - backend FastAPI
After=network.target postgresql.service adaptmobile-ai.service
Wants=postgresql.service adaptmobile-ai.service

[Service]
User=adaptmobile
WorkingDirectory=$APP/AdaptMobile/backend
EnvironmentFile=$APP/adaptmobile.env
Environment=PYTHONDONTWRITEBYTECODE=1
ExecStart=$APP/venv/bin/uvicorn app.main:app --host 127.0.0.1 --port 8000
Restart=always
RestartSec=3

[Install]
WantedBy=multi-user.target
EOF

paso "6/7 Nginx (web estática + proxy a /api)"
cat > /etc/nginx/conf.d/adaptmobile.conf <<EOF
server {
    listen 80 default_server;
    server_name _;

    root $WEB;
    index index.html;

    gzip on;
    gzip_types text/plain text/css application/json application/javascript text/xml application/xml text/javascript;

    location /api/ {
        proxy_pass http://127.0.0.1:8000/api/;
        proxy_http_version 1.1;
        proxy_set_header Host \$host;
        proxy_set_header X-Real-IP \$remote_addr;
        proxy_set_header X-Forwarded-For \$proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto \$scheme;
        proxy_read_timeout 120s;
        client_max_body_size 20M;
    }

    location / {
        try_files \$uri \$uri/ /index.html;
    }
}
EOF
rm -f /etc/nginx/sites-enabled/default
nginx -t

paso "7/7 Arranque"
systemctl daemon-reload
systemctl enable --now adaptmobile-ai adaptmobile-backend >/dev/null
systemctl enable nginx >/dev/null
systemctl restart nginx

echo "Esperando al backend (la primera vez importa el catálogo y puede tardar un poco)..."
ok=0
for _ in $(seq 1 45); do
  if curl -fsS http://127.0.0.1:8000/health >/dev/null 2>&1; then ok=1; break; fi
  sleep 4
done

echo
echo "IA:       $(curl -s http://127.0.0.1:8001/health | cut -c1-100)"
echo "Backend:  $(curl -s http://127.0.0.1:8000/health | cut -c1-100)"
echo "Web/API:  HTTP $(curl -s -o /dev/null -w '%{http_code}' 'http://127.0.0.1/api/devices/brands?region=mx') (esperado 200)"
echo "Espacio libre: $(libre_mb) MB"
if [ "$ok" -ne 1 ]; then
  echo
  echo "El backend no respondió a tiempo. Últimas líneas del registro:"
  journalctl -u adaptmobile-backend -n 25 --no-pager
  exit 1
fi
echo
echo "Listo: http://${SERVER_IP}"
echo "Admin: ${ADMIN_EMAIL}   Contraseña: ${ADMIN_PASSWORD}"
