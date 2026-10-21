import os
from datetime import datetime

class Settings:
    # Driver explícito (postgresql+psycopg2): SQLAlchemy 2.1+ ya no elige psycopg2 por defecto.
    DATABASE_URL: str = os.getenv("DATABASE_URL", "postgresql+psycopg2://postgres:postgres_password@database:5432/adaptmobile")
    AI_SERVICE_URL: str = os.getenv("AI_SERVICE_URL", "http://ai:8001")
    SECRET_KEY: str = os.getenv("SECRET_KEY", "adaptmobile_super_secret_jwt_key_2025")
    ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = int(os.getenv("ACCESS_TOKEN_EXPIRE_MINUTES", "1440"))
    DATA_CSV_PATH: str = os.getenv("DATA_CSV_PATH", "/data/processed_data2.csv")
    DATA_JSON_PATH: str = os.getenv("DATA_JSON_PATH", "/data/data.json")
    ADMIN_EMAIL: str = os.getenv("ADMIN_EMAIL", "admin@adaptmobile.io")
    ADMIN_PASSWORD: str = os.getenv("ADMIN_PASSWORD", "admin123")
    # Token compartido con el microservicio ai para rotar la API key de DeepSeek
    AI_ADMIN_TOKEN: str = os.getenv("AI_ADMIN_TOKEN", "")
    FREE_CREDITS_LIMIT: int = 2
    # Antigüedad máxima (años). Un teléfono con esa edad o más queda fuera del análisis
    # y se responde "No compatible" si el usuario pregunta por él. 2026 - 5 => 2021 se descarta.
    MAX_AGE_YEARS: int = int(os.getenv("MAX_AGE_YEARS", "5"))
    # Primer año de lanzamiento que SÍ se conserva (se calcula con el año actual)
    MIN_RELEASE_YEAR: int = datetime.utcnow().year - MAX_AGE_YEARS + 1
    DEFAULT_REGION: str = "mx"
    # Stripe: estructura lista, sin cobros todavía (ver routers/subscriptions.py)
    STRIPE_SECRET_KEY: str = os.getenv("STRIPE_SECRET_KEY", "")
    STRIPE_WEBHOOK_SECRET: str = os.getenv("STRIPE_WEBHOOK_SECRET", "")
    FRONTEND_URL: str = os.getenv("FRONTEND_URL", "http://localhost:3000")

settings = Settings()
