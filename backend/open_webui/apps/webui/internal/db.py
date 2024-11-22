import logging
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import NullPool

log = logging.getLogger(__name__)
log.setLevel(logging.INFO)

# Không sử dụng DATABASE_URL
SQLALCHEMY_DATABASE_URL = None

# Không khởi tạo engine vì không sử dụng database
engine = None
Base = declarative_base()

# Không tạo session nếu không có engine
SessionLocal = sessionmaker(
    autocommit=False, autoflush=False, bind=engine, expire_on_commit=False
) if engine else None
Session = None  # Không cần sử dụng session


def get_session():
    """Hàm tạo session: Không thực hiện gì nếu không có DATABASE_URL."""
    log.warning("No database session created as DATABASE_URL is not set.")
    return None


def handle_peewee_migration(database_url):
    """Xử lý migration: Bỏ qua nếu không sử dụng DATABASE_URL."""
    if not database_url:
        log.info("Skipping database migration as DATABASE_URL is not provided.")
        return

    log.info("Database migration is skipped since the application doesn't require it.")


log.info("Database configuration is not provided. Database is not initialized.")
