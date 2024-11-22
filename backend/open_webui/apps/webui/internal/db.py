import logging
from contextlib import contextmanager
from sqlalchemy import create_engine
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import NullPool
from typing import Generator
import os

log = logging.getLogger(__name__)
log.setLevel(logging.INFO)

# Lấy DATABASE_URL từ biến môi trường hoặc mặc định là SQLite
DATABASE_URL = os.environ.get("DATABASE_URL", "sqlite:///data/webui.db")

# Tạo engine chỉ khi DATABASE_URL được thiết lập
if DATABASE_URL:
    # Thay thế "postgres://" thành "postgresql://"
    if "postgres://" in DATABASE_URL:
        DATABASE_URL = DATABASE_URL.replace("postgres://", "postgresql://")
    
    engine = create_engine(
        DATABASE_URL,
        poolclass=NullPool,
        connect_args={"check_same_thread": False} if "sqlite" in DATABASE_URL else {}
    )
    log.info(f"Database engine created for URL: {DATABASE_URL}")
else:
    engine = None
    log.warning("DATABASE_URL is not set. Database operations will not work.")

Base = declarative_base()

# Tạo sessionmaker nếu engine tồn tại
SessionLocal = sessionmaker(
    autocommit=False, autoflush=False, bind=engine
) if engine else None


@contextmanager
def get_db() -> Generator:
    """
    Context manager để lấy session database.
    Trả về None nếu không có DATABASE_URL.
    """
    if not SessionLocal:
        log.warning("No database session created as DATABASE_URL is not set.")
        yield None
        return
    
    db = SessionLocal()
    try:
        yield db
    except Exception as e:
        log.error(f"Database session error: {e}")
        db.rollback()
    finally:
        db.close()


def handle_migrations():
    """
    Xử lý migrations bằng Alembic nếu DATABASE_URL được thiết lập.
    """
    if not DATABASE_URL:
        log.warning("No DATABASE_URL provided. Skipping migrations.")
        return

    log.info("Running database migrations...")
    try:
        from alembic import command
        from alembic.config import Config

        alembic_cfg = Config("alembic.ini")
        command.upgrade(alembic_cfg, "head")
        log.info("Database migrations completed successfully.")
    except Exception as e:
        log.error(f"Error running migrations: {e}")


# Chạy migrations nếu DATABASE_URL tồn tại
if DATABASE_URL:
    handle_migrations()
else:
    log.warning("Skipping database initialization due to missing DATABASE_URL.")
