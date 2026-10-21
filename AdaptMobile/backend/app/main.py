import logging
import time
from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy.exc import OperationalError

from .config import settings
from .database import SessionLocal
from .importer import seed_subscriptions_and_admin, import_devices_from_sources
from .migrations import run_migrations
from .routers import auth, analysis, devices, subscriptions, admin, usage

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(name)s: %(message)s")
logger = logging.getLogger("adaptmobile")

@asynccontextmanager
async def lifespan(app: FastAPI):
    # Wait for PostgreSQL to be ready, then apply Alembic migrations
    retries = 15
    while retries > 0:
        try:
            logger.info("Connecting to PostgreSQL database...")
            run_migrations()
            logger.info("Database schema up to date (alembic head).")
            break
        except OperationalError as e:
            retries -= 1
            logger.warning(f"Database not ready yet, retrying in 2 seconds ({retries} left)...")
            time.sleep(2)
    
    # Run seed & import
    db = SessionLocal()
    try:
        seed_subscriptions_and_admin(db)
        import_devices_from_sources(db, settings.DATA_CSV_PATH, settings.DATA_JSON_PATH)
    except Exception as e:
        logger.error(f"Error during startup data initialization: {e}")
    finally:
        db.close()

    yield

app = FastAPI(
    title="AdaptMobile SaaS Backend",
    description="Motor de análisis de compatibilidad móvil con IA",
    version="1.0.0",
    lifespan=lifespan
)

# CORS configuration
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Include API Routers
app.include_router(auth.router)
app.include_router(analysis.router)
app.include_router(devices.router)
app.include_router(subscriptions.router)
app.include_router(subscriptions.webhook_router)
app.include_router(usage.router)
app.include_router(admin.router)

@app.get("/health")
def health():
    return {"status": "ok", "service": "adaptmobile-backend", "time": time.time()}

@app.get("/")
def root():
    return {
        "app": "AdaptMobile SaaS API",
        "version": "1.0.0",
        "docs": "/docs",
        "status": "healthy"
    }
