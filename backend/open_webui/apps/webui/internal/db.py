import json
import logging
from contextlib import contextmanager
from typing import Any, Optional
from sqlalchemy import Dialect, create_engine, types
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import scoped_session, sessionmaker
from sqlalchemy.pool import QueuePool, NullPool
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


def handle_peewee_migration(database_url):
    if not database_url:
        log.info("Skipping database migration as DATABASE_URL is not provided.")
        return

    try:
        db = register_connection(database_url.replace("postgresql://", "postgres://"))
        migrate_dir = OPEN_WEBUI_DIR / "apps" / "webui" / "internal" / "migrations"
        router = Router(db, logger=log, migrate_dir=migrate_dir)
        router.run()
        db.close()
    except Exception as e:
        log.error(f"Failed to initialize the database connection: {e}")
        raise
    finally:
        if db and not db.is_closed():
            db.close()


SQLALCHEMY_DATABASE_URL = DATABASE_URL
engine = None
if SQLALCHEMY_DATABASE_URL:
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
else:
    log.warning("No valid DATABASE_URL provided. Database engine not initialized.")

SessionLocal = sessionmaker(
    autocommit=False, autoflush=False, bind=engine, expire_on_commit=False
) if engine else None

Session = scoped_session(SessionLocal) if SessionLocal else None
Base = declarative_base()

def get_session():
    if not SessionLocal:
        log.warning("No database session created as DATABASE_URL is not set.")
        yield None
        return
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

get_db = contextmanager(get_session)

if DATABASE_URL:
    handle_peewee_migration(DATABASE_URL)
else:
    log.info("Skipping peewee migration due to missing DATABASE_URL.")
