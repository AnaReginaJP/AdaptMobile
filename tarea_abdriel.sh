#!/usr/bin/env bash
# Tarea de Abdriel — Práctica integradora 2 (IA e infraestructura de red)
# Uso: dentro de tu copia del repositorio (donde está la carpeta AdaptMobile):  bash tarea_abdriel.sh
# Hace tu parte, la sube en TU rama y con TU cuenta de git.
set -euo pipefail

RAMA="docs/abdriel-idea-de-negocio"
MSG="docs: documento de idea de negocio de AdaptMobile"

[ -d AdaptMobile ] || { echo "Ejecuta el script en la raíz del repo (donde está la carpeta AdaptMobile)."; exit 1; }
git rev-parse --is-inside-work-tree >/dev/null 2>&1 || { echo "Esta carpeta no es un repositorio git."; exit 1; }
git config user.name  >/dev/null || { echo "Configura tu nombre:  git config --global user.name 'Tu Nombre'"; exit 1; }
git config user.email >/dev/null || { echo "Configura tu correo:  git config --global user.email 'tu@correo.com'"; exit 1; }

echo "Vas a hacer commit como: $(git config user.name) <$(git config user.email)>"
read -r -p "¿Es tu cuenta personal de GitHub? (s/n) " resp
[ "$resp" = "s" ] || { echo "Cancelado. Configura tu cuenta y vuelve a intentarlo."; exit 1; }

git switch main 2>/dev/null || git switch master 2>/dev/null || true
git pull --ff-only 2>/dev/null || true
git switch -c "$RAMA" 2>/dev/null || git switch "$RAMA"
mkdir -p docs deploy tests demo

cat > docs/IDEA_DE_NEGOCIO.md <<'EOF'
# AdaptMobile — Idea de negocio

## Problema
Los equipos que desarrollan apps móviles no saben con certeza qué teléfonos podrán ejecutar su proyecto.
Averiguarlo exige probar en dispositivos físicos o revisar fichas técnicas dispersas, y cada mercado
(México, Estados Unidos, Canadá) vende modelos distintos. El resultado: tiempo perdido, apps lentas o
que fallan en los teléfonos de sus usuarios.

## Solución
**AdaptMobile** es un servicio web que analiza un solo archivo del proyecto (`package.json`, `pubspec.yaml`,
`build.gradle`, `README.md`, etc.). Una IA estima los requisitos aproximados (RAM, CPU, GPU, API gráfica y
versión mínima del sistema) y los cruza con un catálogo real de teléfonos para clasificar cada modelo como
**compatible**, **compatible con limitaciones** o **no compatible**. El usuario también puede preguntar por
un teléfono concreto y recibe una respuesta basada solo en datos verificados del catálogo.

## Usuario final
Desarrolladores independientes, equipos de startups, personas de control de calidad (QA) y estudiantes
de desarrollo móvil que necesitan decidir qué dispositivos soportar antes de publicar.

## Valor agregado
- **Datos reales:** usa un dataset de fichas de teléfonos; no inventa modelos ni especificaciones.
- **Por mercado:** filtra el catálogo por región (MX, US, CA) y por antigüedad del dispositivo.
- **IA privada y económica:** funciona con un modelo local (Ollama), por lo que el código del cliente no
  tiene que enviarse a un tercero, y reduce el consumo de tokens al prefiltrar en la base de datos.
- **Respuestas honestas:** si el teléfono no está en la base verificada, lo dice en lugar de inventar.
- **Resiliente:** si la IA no responde, un motor determinista de respaldo entrega una estimación.

## Modelo de ingresos
Plan gratuito (2 análisis o preguntas al mes) y planes de pago por mayor uso. La estructura de
suscripciones ya existe en la aplicación; la pasarela de pagos está preparada pero todavía no activa.

## Alcance y límites
Los requisitos son estimaciones a partir de un archivo, no mediciones; el catálogo es una foto en el tiempo
y la compatibilidad de bandas en México se infiere con reglas configurables.
EOF

git add docs/IDEA_DE_NEGOCIO.md

git commit -m "$MSG"
git push -u origin "$RAMA"
echo
echo "Listo. Tu rama es: $RAMA"
echo "Abre el repositorio en GitHub y crea el Pull Request hacia main (botón 'Compare & pull request')."
