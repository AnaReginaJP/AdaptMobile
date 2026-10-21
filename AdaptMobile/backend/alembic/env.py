"""
Entorno de Alembic para AdaptMobile.

La URL de la base y el script_location los fija `app/migrations.py` en tiempo de
ejecución, así que este archivo funciona igual desde el contenedor (arranque con
uvicorn) que desde la CLI (`alembic upgrade head` dentro del contenedor backend).
"""
import os
import sys
from logging.config import fileConfig  # noqa: F401  (no lo usamos: respetamos el logging de la app)

from alembic import context
from sqlalchemy import engine_from_config, pool

# Permite `from app...` cuando se ejecuta desde la CLI
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.database import Base  # noqa: E402
from app import models  # noqa: E402,F401  (registra todas las tablas en Base.metadata)

config = context.config
target_metadata = Base.metadata


def run_migrations_offline() -> None:
    context.configure(
        url=config.get_main_option("sqlalchemy.url"),
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
    )
    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
    connectable = engine_from_config(
        config.get_section(config.config_ini_section, {}),
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,
    )
    with connectable.connect() as connection:
        context.configure(connection=connection, target_metadata=target_metadata)
        with context.begin_transaction():
            context.run_migrations()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
