"""
Alembic env.py customizado para:
  - Ler a URL do banco do .env (via app.config.get_settings).
  - Importar todos os models para que autogenerate detecte as tabelas.
"""
import os
import sys
from logging.config import fileConfig
from pathlib import Path

from alembic import context
from sqlalchemy import engine_from_config, pool

# Coloca a raiz do backend no sys.path para importar `app.*` daqui.
BACKEND_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(BACKEND_DIR))

from app.config import get_settings  # noqa: E402
from app.database import Base         # noqa: E402
import app.models                      # noqa: F401,E402  (carrega todos os models)


config = context.config

# Setup do logger do Alembic.
if config.config_file_name is not None:
    fileConfig(config.config_file_name)

# Injeta a URL do banco dinamicamente.
settings = get_settings()
config.set_main_option("sqlalchemy.url", settings.postgres_url)

target_metadata = Base.metadata


def run_migrations_offline() -> None:
    url = config.get_main_option("sqlalchemy.url")
    context.configure(
        url=url,
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
