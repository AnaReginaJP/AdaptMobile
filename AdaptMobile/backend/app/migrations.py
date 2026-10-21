"""
Migraciones Alembic ejecutadas al arrancar el contenedor backend.

Sustituye a los ALTER TABLE manuales: el esquema lo controla Alembic y se aplica
solo con `docker compose up --build` (desde el lifespan de FastAPI, sin cron).

Bases ya existentes: si hay tablas pero no hay `alembic_version`, se "estampa" la
revisión inicial en lugar de recrear el esquema. La revisión 0002 es idempotente,
así que completará las columnas de región que falten sin tocar lo que ya existe.
"""
import logging
from pathlib import Path

from alembic import command
from alembic.config import Config
from sqlalchemy import inspect

from .config import settings
from .database import engine

logger = logging.getLogger("migrations")

BACKEND_DIR = Path(__file__).resolve().parent.parent   # /app
ALEMBIC_DIR = BACKEND_DIR / "alembic"
BASE_REVISION = "0001_initial"


def _alembic_config() -> Config:
    cfg = Config(str(BACKEND_DIR / "alembic.ini"))
    cfg.set_main_option("script_location", str(ALEMBIC_DIR))
    # ConfigParser interpreta "%" como interpolación: hay que escaparlo.
    cfg.set_main_option("sqlalchemy.url", settings.DATABASE_URL.replace("%", "%%"))
    return cfg


def _existing_schema_revision() -> str:
    """Revisión que representa el esquema ya presente ('' si la base está vacía)."""
    insp = inspect(engine)
    if not insp.has_table("users"):
        return ""
    return BASE_REVISION


def run_migrations() -> None:
    cfg = _alembic_config()
    if not inspect(engine).has_table("alembic_version"):
        baseline = _existing_schema_revision()
        if baseline:
            logger.info("Base existente sin alembic_version: se estampa en %s y se completa lo que falte.", baseline)
            command.stamp(cfg, baseline)
    command.upgrade(cfg, "head")
    logger.info("Migraciones aplicadas correctamente.")
