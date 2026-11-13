import os

DATABASE_URL = os.getenv("DATABASE_URL", "sqlite:///./zeladoria.db")
APP_VERSION = os.getenv("APP_VERSION", "dev")
