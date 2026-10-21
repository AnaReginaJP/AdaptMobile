# AdaptMobile — SaaS de Compatibilidad de Hardware Móvil con IA

**AdaptMobile** es una plataforma SaaS de alto rendimiento diseñada para analizar proyectos móviles a partir de **un único archivo** de configuración o manifiesto (`package.json`, `build.gradle`, `pubspec.yaml`, `README.md`, `AndroidManifest.xml`, `Podfile`, etc.).

Estima automáticamente los requerimientos aproximados de hardware (RAM, CPU, GPU, almacenamiento, API gráfica Vulkan/Metal/OpenGL y versión mínima de SO) y determina con precisión qué teléfonos pueden ejecutar el proyecto clasificándolos en:
- 🟢 **Compatible**
- 🟡 **Compatible con limitaciones**
- 🔴 **No compatible**

> **Importante:** AdaptMobile **NO inventa datos ni teléfonos**. Utiliza únicamente los registros de dispositivos reales provistos en `processed_data2.csv` y `data.json`, normalizados y desduplicados en PostgreSQL.

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
- Al agotar los 2 créditos, el sistema muestra el modal de suscripción.
- La arquitectura incluye planes preparados (`free`, `pro`, `enterprise`) con actualización de plan simulada (MVP funcional sin pasarela bancaria real obligatoria).

---

## Configuración de Variables de Entorno (`.env`)

| Variable | Descripción | Valor por defecto |
|---|---|---|
| `POSTGRES_DB` | Nombre de la base de datos | `adaptmobile` |
| `POSTGRES_USER` | Usuario de PostgreSQL | `postgres` |
| `POSTGRES_PASSWORD` | Contraseña de PostgreSQL | `postgres_password` |
| `SECRET_KEY` | Clave secreta para tokens JWT | `adaptmobile_super_secret_jwt_key_2025` |
| `AI_PROVIDER` | Proveedor del motor IA (`heuristic`, `gemini`, `openai`) | `heuristic` (100% funcional sin API key) |
| `OPENAI_API_KEY` | Clave de OpenAI (opcional) | |
| `GEMINI_API_KEY` | Clave de Google Gemini (opcional) | |

---

## Estructura del Repositorio

```text
AdaptMobile/
├── docker-compose.yml
├── .env.example
├── .env
├── README.md
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
│   └── app/
│       ├── main.py
│       ├── config.py
│       ├── database.py
│       ├── models.py
│       ├── schemas.py
│       ├── auth.py
│       ├── importer.py
│       ├── ai_client.py
│       └── routers/
│           ├── auth.py
│           ├── analysis.py
│           ├── devices.py
│           ├── subscriptions.py
│           └── admin.py
├── ai/
│   ├── Dockerfile
│   ├── requirements.txt
│   └── app/
│       ├── main.py
│       ├── config.py
│       ├── engine.py
│       └── parser.py
└── database/
    ├── processed_data2.csv
    └── data.json
```
