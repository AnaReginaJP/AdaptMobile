# AdaptMobile — SaaS de Compatibilidad de Hardware Móvil con IA

**AdaptMobile** es una plataforma SaaS de alto rendimiento diseñada para analizar proyectos móviles a partir de **un único archivo** de configuración o manifiesto (`package.json`, `build.gradle`, `pubspec.yaml`, `README.md`, `AndroidManifest.xml`, `Podfile`, etc.).

Estima automáticamente los requerimientos aproximados de hardware (RAM, CPU, GPU, almacenamiento, API gráfica Vulkan/Metal/OpenGL y versión mínima de SO) y determina con precisión qué teléfonos pueden ejecutar el proyecto clasificándolos en:
- 🟢 **Compatible**
- 🟡 **Compatible con limitaciones**
- 🔴 **No compatible**

> **Importante:** AdaptMobile **NO inventa datos ni teléfonos**. Utiliza únicamente los registros de dispositivos reales provistos en `processed_data2.csv` y `data.json`, normalizados y desduplicados en PostgreSQL.

---

## Mercados y antigüedad (catálogo curado)

El catálogo no se analiza completo: se filtra **al importarlo** a PostgreSQL (los archivos CSV/JSON originales nunca se modifican).

**1. Mercado objetivo (MX / US / CA).** Se elige en la interfaz y viaja en cada análisis. La pertenencia a un mercado se deduce con evidencia real, en este orden (`AdaptMobile/backend/app/regions.py`):

| Evidencia | Fuente | Regiones donde aplica |
|---|---|---|
| **Venta** | `pricing.United States` / `pricing.Canada` en `data.json`, o tienda `Amazon US` / `Best Buy` en el CSV | US, CA |
| **Red** | Bandas LTE declaradas por el teléfono (`Network.4G bands`) frente a las bandas necesarias para operar en el país | MX, US, CA |

El dataset **no trae datos de venta de México**, así que MX se deduce por bandas de red. Las reglas de bandas (`REGION_LTE_RULES`) son un supuesto editable: cada región exige cumplir **todos** los grupos y cada grupo se satisface con **cualquiera** de sus bandas.

**2. Antigüedad.** Se descartan los teléfonos lanzados hace `MAX_AGE_YEARS` años o más (por defecto 5 ⇒ **2021 y anteriores quedan fuera**). Esos modelos se guardan en modo *legacy* (marca, modelo y año) para poder responder **"No compatible" sin gastar tokens de IA** si alguien pregunta por ellos.

**3. Resultado:** de más de 8.000 fichas se pasa a **944 teléfonos activos** (MX=810, US=826, CA=672) más ~4.350 registros legacy solo para consulta. Menos datos ⇒ menos tokens y respuestas más precisas.

---

## Arquitectura (4 Contenedores Docker)

```text
Usuario ────► [Contenedor Web: Nginx SPA] (Puerto 3000)
                     │
                     ▼ (Red interna Docker)
              [Contenedor Backend: FastAPI] (Puerto 8000)
                │                  │
                ▼                  ▼
     [Contenedor PostgreSQL 16]   [Contenedor IA: FastAPI Engine] (Puerto 8001)
     (Persistencia y Filtro)      (Estimación y Razonamiento)
```

1. **`web`**: Interfaz de usuario moderna y responsive en modo oscuro, con panel de desarrollador, panel de administración, catálogo de dispositivos interactivo y visualización en tiempo real.
2. **`backend`**: API REST en Python (FastAPI). Gestiona autenticación JWT, usuarios, límites de créditos/suscripciones, subida y validación de archivos, pre-filtrado SQL de bajo consumo de tokens y orquestación con la IA.
3. **`database`**: PostgreSQL 16. Almacena usuarios, catálogo de dispositivos normalizados, análisis guardados, historial y preguntas.
4. **`ai`**: Microservicio desacoplado de Inteligencia Artificial. Analiza manifiestos, calcula requerimientos de hardware, sintetiza reportes ejecutivos y responde consultas sobre teléfonos específicos basándose estrictamente en datos de PostgreSQL.

---

## Reducción de Consumo de Tokens (Optimización Clave)

Para evitar enviar miles de dispositivos a modelos de lenguaje en cada consulta:
1. **Pre-filtrado SQL en Backend:** El backend evalúa la compatibilidad en PostgreSQL mediante consultas indexadas.
2. **Síntesis Mínima a la IA:** A la IA solo se le envía un paquete mínimo con métricas agregadas y 3 dispositivos de muestra (~250 tokens).
3. **Consultas de Modelos Concretos:** Cuando el usuario pregunta por un teléfono, el backend lo busca primero en PostgreSQL. Si no existe, responde de inmediato: *"El dispositivo no se encuentra en nuestra base de datos verificada. No generamos especificaciones no verificadas."* Si existe, se envían únicamente sus especificaciones exactas.

---

## Puesta en Marcha Inmediata

Ejecuta en la raíz del proyecto:

```bash
docker compose up --build
```

### URLs de Acceso

- **Aplicación Web:** [http://localhost:3000](http://localhost:3000)
- **Documentación Swagger API Backend:** [http://localhost:8000/docs](http://localhost:8000/docs)
- **Microservicio IA Healthcheck:** [http://localhost:8001/health](http://localhost:8001/health)

---

## Credenciales de Acceso

El sistema inicializa automáticamente una cuenta administradora:
- **Email:** `admin@adaptmobile.io`
- **Contraseña:** `admin123`
- **Rol:** `admin` (Acceso al Panel de Administración y créditos ilimitados)

También puedes crear una cuenta nueva desde el botón **Registrarse**, la cual iniciará automáticamente con el **Plan Gratuito** (2 análisis/preguntas mensuales).

---

## Modelo de Suscripciones y Créditos (Plan Gratuito)

- **Plan Gratuito:** Cada usuario registrado cuenta con **2 análisis/preguntas al mes**.
- **Reinicio mensual automático:** al primer uso de un mes nuevo, `credits_used` vuelve a 0 comparando con `users.period_start` (último reinicio guardado). No depende de ningún cron.
- Al agotar los créditos, la web muestra un **aviso persistente con botón "Ver planes"** y el backend responde `402` con un código identificable (`credits_exhausted`).
- La arquitectura incluye planes preparados (`free`, `pro`, `enterprise`) con actualización de plan simulada (MVP funcional sin pasarela bancaria real obligatoria).

### Uso, embudo y pagos

| Elemento | Dónde | Qué hace |
|---|---|---|
| `usage_events` | PostgreSQL | Una fila por cada crédito consumido (`analysis` / `question`) |
| `GET /api/usage` | Usuario | Historial de consumo + resumen del periodo |
| `GET /api/admin/usage` | Admin | Uso total, créditos consumidos y usuarios que más gastan |
| `funnel_events` + `POST /api/events` | Web → Backend | Pasos del embudo (`register`, `upload_started`, `analysis_done`, `limit_reached`, `pricing_viewed`, `upgrade_clicked`) |
| `GET /api/admin/funnel` | Admin | Conteos por paso y tasa de conversión (vs. paso anterior y vs. registro) |
| `payments` + `stripe_*` | PostgreSQL | Estructura lista para Stripe (sin cobros todavía) |
| `POST /api/subscriptions/checkout` | Stub | Responde `501 payments_not_implemented`; el docstring describe el Checkout Session que creará |
| `POST /api/webhooks/stripe` | Stub | Responde `501`; el docstring describe la verificación de firma y los eventos a procesar |

Al activar los pagos: rellenar `STRIPE_SECRET_KEY`/`STRIPE_WEBHOOK_SECRET`, el `stripe_price_id` de cada plan y descomentar `stripe` en `backend/requirements.txt`.

---

## Migraciones de base de datos (Alembic)

El esquema lo controla **Alembic** dentro del contenedor backend y se aplica solo al arrancar (`docker compose up --build`), desde el `lifespan` de FastAPI: no hay que ejecutar nada a mano ni hay cron.

```text
backend/alembic/versions/
├── 0001_initial.py                  # esquema original (usuarios, dispositivos, análisis, planes)
├── 0002_region_columns.py           # columnas de región/antigüedad (idempotente)
└── 0003_usage_funnel_payments.py    # usage_events, funnel_events, payments y columnas de Stripe
```

- **Bases nuevas:** se aplican 0001 → 0002 → 0003.
- **Bases ya existentes** (creadas por versiones anteriores con `create_all`): si hay tablas pero no `alembic_version`, se **estampa** la revisión inicial y se completan solo las diferencias. 0002 comprueba columna por columna, así que no rompe nada.
- Crear una migración nueva: `docker compose exec backend alembic revision --autogenerate -m "descripcion"`.

---

## Configuración de Variables de Entorno (`.env`)

| Variable | Descripción | Valor por defecto |
|---|---|---|
| `POSTGRES_DB` | Nombre de la base de datos | `adaptmobile` |
| `POSTGRES_USER` | Usuario de PostgreSQL | `postgres` |
| `POSTGRES_PASSWORD` | Contraseña de PostgreSQL | `postgres_password` |
| `SECRET_KEY` | Clave secreta para tokens JWT | `adaptmobile_super_secret_jwt_key_2025` |
| `AI_PROVIDER` | Motor de IA: `deepseek` (usa la API si hay key; si no, cae a heurística) o `heuristic` (100% offline) | `heuristic` en `.env.example` |
| `DEEPSEEK_API_KEY` | API key de DeepSeek (opción B de rotación) | *(vacío)* |
| `DEEPSEEK_API_KEY_FILE` | Archivo con la API key, **releído en cada petición** (opción A: rotar sin reiniciar) | `/run/secrets/deepseek_api_key` |
| `DEEPSEEK_BASE_URL` | Endpoint de la API de DeepSeek | `https://api.deepseek.com` |
| `DEEPSEEK_MODEL` | Modelo a usar | `deepseek-chat` |
| `DEEPSEEK_TIMEOUT` / `DEEPSEEK_MAX_TOKENS` | Timeout (s) y tope de tokens de salida | `45` / `1200` |
| `AI_MODEL_NAME` | Si se define, tiene prioridad sobre `DEEPSEEK_MODEL` | *(vacío)* |
| `AI_ADMIN_TOKEN` | Token compartido backend↔ai que autoriza la rotación de la key | *(vacío = rotación deshabilitada)* |
| `MAX_AGE_YEARS` | Antigüedad máxima del catálogo; 5 descarta 2021 y anteriores | `5` |

> La API key **nunca** se escribe en `docker-compose.yml`: vive en `.env` o en `secrets/deepseek_api_key` (ambos en `.gitignore`).

---

## Rotar la API key de DeepSeek (4 formas)

Para cambiarla **constantemente por seguridad**, sin reconstruir imágenes:

1. **Desde el Panel de Administración (lo más fácil, sin comandos).** Entra como `admin@adaptmobile.io`, pestaña **Admin** → tarjeta **🔑 Motor de IA · API key de DeepSeek**: muestra la fuente, la key enmascarada y el modo efectivo, permite pegar una key nueva y guardarla (activa al instante), o volver a la del `.env`/archivo.
2. **Editando un archivo (cero reinicios).** Escribe la key en `secrets/deepseek_api_key` (una línea, sin comillas; se admiten comentarios con `#`). El microservicio `ai` **relee ese archivo en cada petición**, así que la nueva key queda activa al instante.
3. **Por variable de entorno.** Ponla en `DEEPSEEK_API_KEY` y recrea solo ese contenedor: `docker compose up -d ai`.
4. **En caliente desde la API** (requiere `AI_ADMIN_TOKEN`; el token se genera con `python -c "import secrets;print(secrets.token_urlsafe(32))"`):

```bash
# Estado actual: fuente, modo efectivo y key enmascarada
curl http://localhost:8000/api/admin/ai-key -H "Authorization: Bearer <JWT_ADMIN>"

# Rotar
curl -X PUT http://localhost:8000/api/admin/ai-key \
  -H "Authorization: Bearer <JWT_ADMIN>" -H "Content-Type: application/json" \
  -d '{"api_key":"sk-tu-nueva-key"}'

# Descartar el override (vuelve al archivo / .env)
curl -X DELETE http://localhost:8000/api/admin/ai-key -H "Authorization: Bearer <JWT_ADMIN>"
```

Precedencia: **override en memoria → archivo → variable de entorno**. La key solo se muestra enmascarada (`sk-a…8888`) y nunca aparece en los logs.

**Guardarraíles del motor:** si DeepSeek no responde (sin key, 401, timeout o JSON inválido) el sistema sigue con la heurística determinista, y todo número que devuelva el modelo se acota a rangos físicos razonables (RAM 1–16 GB, almacenamiento 0.5–32 GB, núcleos 2–16, Android 4–16, iOS 8–20) antes de usarse.

---

## Estructura del Repositorio

```text
AdaptMobile/
├── docker-compose.yml
├── .env.example
├── .env
├── README.md
├── secrets/
│   └── deepseek_api_key      # API key releída en cada petición (rotación en caliente)
├── web/
│   ├── Dockerfile
│   ├── nginx.conf
│   └── src/
│       ├── index.html
│       ├── styles.css
│       └── app.js
├── backend/
│   ├── Dockerfile
│   ├── requirements.txt
│   ├── alembic.ini
│   ├── alembic/               # migraciones (se aplican solas al arrancar)
│   │   ├── env.py
│   │   └── versions/
│   │       ├── 0001_initial.py
│   │       ├── 0002_region_columns.py
│   │       └── 0003_usage_funnel_payments.py
│   └── app/
│       ├── main.py
│       ├── config.py
│       ├── database.py
│       ├── models.py
│       ├── schemas.py
│       ├── auth.py
│       ├── importer.py
│       ├── regions.py         # clasificación MX / US / CA y filtro de antigüedad
│       ├── migrations.py      # ejecuta Alembic al arrancar (con estampado de bases viejas)
│       ├── telemetry.py       # créditos, reinicio mensual, usage_events y embudo
│       ├── ai_client.py
│       └── routers/
│           ├── auth.py
│           ├── analysis.py
│           ├── devices.py
│           ├── subscriptions.py   # incluye los stubs de Stripe
│           ├── usage.py           # /api/usage y /api/events
│           └── admin.py
├── ai/
│   ├── Dockerfile
│   ├── requirements.txt
│   └── app/
│       ├── main.py
│       ├── config.py
│       ├── engine.py
│       ├── deepseek.py       # cliente DeepSeek + guardarraíles numéricos
│       ├── keyring.py        # precedencia y rotación de la API key
│       └── parser.py
└── database/
    ├── processed_data2.csv
    └── data.json
```

---

## Despliegue en la nube (Práctica integradora 2)

**Aplicación en línea:** http://79.143.88.199

### Cómo se desplegó
El proyecto incluye `docker-compose.yml` (4 contenedores) y sirve para ejecutarlo en una computadora local.
En el servidor de la práctica **se desplegó sin Docker** porque el disco es de solo 5 GB y las imágenes no cabían.
El script [`deploy/deploy_nativo.sh`](deploy/deploy_nativo.sh) instala PostgreSQL, NGINX y un entorno de Python,
y crea los servicios `adaptmobile-ai` y `adaptmobile-backend` con systemd:

```bash
# en el servidor, como root, con el proyecto descomprimido en /opt/Los_Telefonos
bash deploy_nativo.sh
```

El proxy inverso (NGINX) es la única puerta de entrada pública: sirve el frontend y reenvía `/api/` al backend.
El backend (8000), la IA (8001) y PostgreSQL (5432) escuchan solo en `127.0.0.1`.
La configuración real está en [`deploy/nginx-adaptmobile.conf`](deploy/nginx-adaptmobile.conf) y el diagrama de red
en [`docs/ARQUITECTURA_RED.md`](docs/ARQUITECTURA_RED.md).

### IA con Ollama
El servicio de IA usa una API compatible con OpenAI, por lo que se conecta a Ollama sin cambiar código
(modelo `qwen2.5-coder:7b`). Variables en `.env` (ver `.env.example`):

```env
AI_PROVIDER=deepseek
DEEPSEEK_BASE_URL=http://127.0.0.1:11434/v1
DEEPSEEK_MODEL=qwen2.5-coder:7b
DEEPSEEK_TIMEOUT=300
DEEPSEEK_MAX_TOKENS=500
```

Ollama corre en la computadora de un integrante y el servidor llega a él mediante un **túnel SSH inverso**
(`ssh -N -R 127.0.0.1:11434:localhost:11434 usuario@servidor`). Si Ollama no responde, el servicio usa un motor
determinista de respaldo. La conexión por la VPN del equipo queda como paso pendiente: solo cambiaría `DEEPSEEK_BASE_URL`.
