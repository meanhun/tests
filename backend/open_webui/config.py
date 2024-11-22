import json
import logging
import os
import shutil
from datetime import datetime
from pathlib import Path
from typing import Optional
from urllib.parse import urlparse

from open_webui.apps.webui.internal.db import Base, get_db
from open_webui.env import (
    OPEN_WEBUI_DIR,
    DATA_DIR,
    ENV,
    FRONTEND_BUILD_DIR,
    WEBUI_AUTH,
    WEBUI_FAVICON_URL,
    WEBUI_NAME,
    log,
)
from sqlalchemy import JSON, Column, DateTime, Integer, func

class EndpointFilter(logging.Filter):
    def filter(self, record: logging.LogRecord) -> bool:
        return "/health" not in record.getMessage()

# Filter out /health endpoint logs
logging.getLogger("uvicorn.access").addFilter(EndpointFilter())

####################################
# Config helpers
####################################

class Config(Base):
    __tablename__ = "config"

    id = Column(Integer, primary_key=True)
    data = Column(JSON, nullable=False)
    version = Column(Integer, nullable=False, default=0)
    created_at = Column(DateTime, nullable=False, server_default=func.now())
    updated_at = Column(DateTime, nullable=True, onupdate=func.now())


DEFAULT_CONFIG = {
    "version": 0,
    "ui": {
        "default_locale": "",
        "prompt_suggestions": [
            {
                "title": ["Help me study", "vocabulary for a college entrance exam"],
                "content": "Help me study vocabulary: write a sentence for me to fill in the blank, and I'll try to pick the correct option.",
            },
            {
                "title": ["Tell me a fun fact", "about the Roman Empire"],
                "content": "Tell me a random fun fact about the Roman Empire",
            },
        ],
    },
}


def get_config():
    """
    Retrieve configuration from the database if available, otherwise return the default configuration.
    """
    with get_db() as db:
        if db is None:  # Nếu không có kết nối database
            log.warning("No database connection. Returning default configuration.")
            return DEFAULT_CONFIG

        # Truy vấn config từ database
        config_entry = db.query(Config).order_by(Config.id.desc()).first()
        return config_entry.data if config_entry else DEFAULT_CONFIG


def save_to_db(data):
    """
    Save configuration data to the database. If no database connection, log a warning.
    """
    with get_db() as db:
        if db is None:  # Không có database
            log.warning("No database connection. Configuration not saved.")
            return

        # Lưu dữ liệu vào database
        existing_config = db.query(Config).first()
        if not existing_config:
            new_config = Config(data=data, version=0)
            db.add(new_config)
        else:
            existing_config.data = data
            existing_config.updated_at = datetime.now()
            db.add(existing_config)
        db.commit()


def reset_config():
    """
    Reset the configuration by deleting all entries in the database.
    """
    with get_db() as db:
        if db is None:  # Không có database
            log.warning("No database connection. Configuration reset skipped.")
            return

        db.query(Config).delete()
        db.commit()


# Load initial configuration from config.json if it exists
if os.path.exists(f"{DATA_DIR}/config.json"):
    with open(f"{DATA_DIR}/config.json", "r") as file:
        initial_data = json.load(file)
        save_to_db(initial_data)
    os.rename(f"{DATA_DIR}/config.json", f"{DATA_DIR}/old_config.json")


CONFIG_DATA = get_config()

def get_config_value(config_path: str) -> Optional[dict]:
    """
    Get a specific configuration value by path.
    """
    path_parts = config_path.split(".")
    cur_config = CONFIG_DATA
    for key in path_parts:
        if key in cur_config:
            cur_config = cur_config[key]
        else:
            return None
    return cur_config


####################################
# CORS Validation
####################################

def validate_cors_origins(origins):
    for origin in origins:
        if origin != "*":
            validate_cors_origin(origin)


def validate_cors_origin(origin):
    parsed_url = urlparse(origin)

    # Check if the scheme is either http or https
    if parsed_url.scheme not in ["http", "https"]:
        raise ValueError(
            f"Invalid scheme in CORS_ALLOW_ORIGIN: '{origin}'. Only 'http' and 'https' are allowed."
        )

    # Ensure that the netloc (domain + port) is present, indicating it's a valid URL
    if not parsed_url.netloc:
        raise ValueError(f"Invalid URL structure in CORS_ALLOW_ORIGIN: '{origin}'.")


CORS_ALLOW_ORIGIN = os.environ.get("CORS_ALLOW_ORIGIN", "*").split(";")

if "*" in CORS_ALLOW_ORIGIN:
    log.warning(
        "\n\nWARNING: CORS_ALLOW_ORIGIN IS SET TO '*' - NOT RECOMMENDED FOR PRODUCTION DEPLOYMENTS.\n"
    )

validate_cors_origins(CORS_ALLOW_ORIGIN)


####################################
# Static Files Setup
####################################

STATIC_DIR = Path(os.getenv("STATIC_DIR", OPEN_WEBUI_DIR / "static")).resolve()

frontend_favicon = FRONTEND_BUILD_DIR / "static" / "favicon.png"
if frontend_favicon.exists():
    try:
        shutil.copyfile(frontend_favicon, STATIC_DIR / "favicon.png")
    except Exception as e:
        logging.error(f"An error occurred: {e}")
else:
    logging.warning(f"Frontend favicon not found at {frontend_favicon}")

frontend_splash = FRONTEND_BUILD_DIR / "static" / "splash.png"
if frontend_splash.exists():
    try:
        shutil.copyfile(frontend_splash, STATIC_DIR / "splash.png")
    except Exception as e:
        logging.error(f"An error occurred: {e}")
else:
    logging.warning(f"Frontend splash not found at {frontend_splash}")
