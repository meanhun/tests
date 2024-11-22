import json
import logging
from contextlib import contextmanager
from typing import Any, Optional

from open_webui.apps.webui.internal.wrappers import register_connection
from open_webui.env import (
    OPEN_WEBUI_DIR,
    DATABASE_URL,
    SRC_LOG_LEVELS,
    DATABASE_POOL_MAX_OVERFLOW,
    DATABASE_POOL_RECYCLE,
    DATABASE_POOL_SIZE,
    DATABASE_POOL_TIMEOUT,
)
from peewee_migrate import Router
from sqlalchemy import Dialect, create_engine, types
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import scoped_session, sessionmaker
from sqlalchemy.pool import QueuePool, NullPool
from sqlalchemy.sql.type_api import _T
from typing_extensions import Self

log = logging.getLogger(__name__)
log.setLevel(SRC_LOG_LEVELS["DB"])


class JSONField(types.TypeDecorator):
    impl = types.Text
    cache_ok = True

    def process_bind_param(self, value: Optional[_T], dialect: Dialect) -> Any:
        return json.dumps(value)

    def process_result_value(self, value: Optional[_T], dialect: Dialect) -> Any:
        if value is not None:
            return json.loads(value)

    def copy(self, **kw: Any) -> Self:
        return JSONField(self.impl.length)

    def db_value(self, value):
        return json.dumps(value)

    def python_value(self, value):
        if value is not None:
            return json.loads(value)


# Workaround to handle the peewee migration
def handle_peewee_migration(database_url):
    if not database_url or "sqlite:///:memory:" in database_url:
        log.info("Skipping database migration due to missing or in-memory DATABASE_URL.")
        return

    db = None
    try:
        db = register_connection(database_url.replace("postgresql://", "postgres://"))
        migrate_dir = OPEN_WEBUI_DIR / "apps" / "webui" / "internal" / "migrations"
        router = Router(db, logger=log, migrate_dir=migrate_dir)
        router.run()
    except Exception as e:
        log.error(f"Failed to initialize the database connection: {e}")
    finally:
        if db and not db.is_closed():
            db.close()
        assert db.is_closed(), "Database connection is still open."


SQLALCHEMY_DATABASE_URL = DATABASE_URL
engine = None

if SQLALCHEMY_DATABASE_URL:  # Only initialize the engine if DATABASE_URL is valid
    if "sqlite" in SQLALCHEMY_DATABASE_URL:
        engine = create_engine(
            SQLALCHEMY_DATABASE_URL, connect_args={"check_same_thread": False}
        )
    elif DATABASE_POOL_SIZE > 0:
        engine = create_engine(
            SQLALCHEMY_DATABASE_URL,
            pool_size=DATABASE_POOL_SIZE,
            max_overflow=DATABASE_POOL_MAX_OVERFLOW,
            pool_timeout=DATABASE_POOL_TIMEOUT,
            pool_recycle=DATABASE_POOL_RECYCLE,
            pool_pre_ping=True,
            poolclass=QueuePool,
        )
    else:
        engine = create_engine(
            SQLALCHEMY_DATABASE_URL, pool_pre_ping=True, poolclass=NullPool
        )


SessionLocal = sessionmaker(
    autocommit=False, autoflush=False, bind=engine, expire_on_commit=False
) if engine else None

Base = declarative_base()
Session = scoped_session(SessionLocal) if SessionLocal else None


@contextmanager
def get_db():
    """A context manager to manage the database session."""
    db = None
    try:
        db = get_session()
        yield db
    finally:
        if db:
            db.close()


def get_session():
    if not SessionLocal:
        log.info("Skipping session creation as DATABASE_URL is not set.")
        return  # No action if DATABASE_URL is not set
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


# Call migration handling
if DATABASE_URL:
    handle_peewee_migration(DATABASE_URL)
else:
    log.info("No DATABASE_URL provided, skipping database migration and connection.")
