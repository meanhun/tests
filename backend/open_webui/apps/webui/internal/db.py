import logging
from contextlib import contextmanager
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import NullPool
from typing import Generator

log = logging.getLogger(__name__)
log.setLevel(logging.INFO)

# Không sử dụng DATABASE_URL
DATABASE_URL = None  # Thay đổi nếu bạn muốn sử dụng cơ sở dữ liệu

# Không khởi tạo engine nếu không có DATABASE_URL
engine = None
Base = declarative_base()

# Không tạo session nếu không có engine
SessionLocal = sessionmaker(
    autocommit=False, autoflush=False, bind=engine, expire_on_commit=False
) if engine else None

# Hàm để lấy session nếu có engine
@contextmanager
def get_db() -> Generator[None, None, None]:
    """
    Context manager for database session. Returns None if no DATABASE_URL is set.
    """
    if not SessionLocal:
        log.warning("No database session created as DATABASE_URL is not set.")
        yield None  # Trả về None nếu không có session
        return
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


# Hàm giả lập để xử lý migrations nếu cần thiết
def handle_migrations():
    """
    Placeholder for handling migrations.
    Skips migration logic if DATABASE_URL is not set.
    """
    if not DATABASE_URL:
        log.info("No DATABASE_URL provided. Skipping migrations.")
        return
    # Thực hiện các bước migration thực sự nếu cần
    log.info("Migrations would be handled here if DATABASE_URL is set.")


# Gọi hàm xử lý migration nếu DATABASE_URL được cung cấp
if DATABASE_URL:
    handle_migrations()
else:
    log.info("Skipping database initialization due to missing DATABASE_URL.")
