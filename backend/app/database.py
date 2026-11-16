"""
SQLAlchemy configurado para o PostgreSQL interno.

  - Base: declarative base de onde todos os models herdam.
  - SessionLocal: fabricadora de sessões.
  - get_db(): dependency do FastAPI que entrega uma sessão e garante
    fechamento no fim do request.
"""
from sqlalchemy import create_engine
from sqlalchemy.orm import DeclarativeBase, sessionmaker

from app.config import get_settings


settings = get_settings()

# pool_pre_ping=True evita "server closed the connection unexpectedly"
# depois de longos períodos ociosos.
engine = create_engine(
    settings.postgres_url,
    pool_pre_ping=True,
    future=True,
)

SessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False)


class Base(DeclarativeBase):
    """Declarative base para todos os models da aplicação."""
    pass


def get_db():
    """Dependency FastAPI: injeta uma sessão e garante close ao fim."""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
