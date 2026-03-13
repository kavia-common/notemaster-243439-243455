import os
from dataclasses import dataclass

from sqlalchemy import create_engine
from sqlalchemy.engine import Engine


@dataclass(frozen=True)
class DbSettings:
    """Database settings derived from environment variables."""

    url: str


def _build_postgres_url_from_parts() -> str:
    """
    Build a SQLAlchemy Postgres URL from POSTGRES_* env vars.

    Expected env vars (provided by platform for the DB container):
    - POSTGRES_URL (host)
    - POSTGRES_USER
    - POSTGRES_PASSWORD
    - POSTGRES_DB
    - POSTGRES_PORT
    """
    host = os.getenv("POSTGRES_URL")
    user = os.getenv("POSTGRES_USER")
    password = os.getenv("POSTGRES_PASSWORD")
    db = os.getenv("POSTGRES_DB")
    port = os.getenv("POSTGRES_PORT")

    missing = [k for k, v in {
        "POSTGRES_URL": host,
        "POSTGRES_USER": user,
        "POSTGRES_PASSWORD": password,
        "POSTGRES_DB": db,
        "POSTGRES_PORT": port,
    }.items() if not v]

    if missing:
        raise RuntimeError(
            "Missing required database environment variables: "
            + ", ".join(missing)
            + ". Ask orchestrator to set them in the backend .env."
        )

    return f"postgresql+psycopg2://{user}:{password}@{host}:{port}/{db}"


# PUBLIC_INTERFACE
def get_db_settings() -> DbSettings:
    """Return resolved database settings for the application."""
    # Prefer a single DATABASE_URL style var if present.
    db_url = os.getenv("DATABASE_URL")
    if db_url:
        # Allow either sqlalchemy URL or raw postgres URL; normalize driver if needed.
        if db_url.startswith("postgresql://"):
            db_url = "postgresql+psycopg2://" + db_url[len("postgresql://") :]
        return DbSettings(url=db_url)

    return DbSettings(url=_build_postgres_url_from_parts())


# PUBLIC_INTERFACE
def create_db_engine() -> Engine:
    """Create and return a SQLAlchemy engine for the app."""
    settings = get_db_settings()
    return create_engine(settings.url, pool_pre_ping=True)
