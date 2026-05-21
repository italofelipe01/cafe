import os


class Config:
    BASE_DIR = os.path.abspath(os.path.dirname(__file__))
    PROJECT_ROOT = BASE_DIR
    INSTANCE_DIR = os.path.join(PROJECT_ROOT, "instance")

    SECRET_KEY = os.environ.get("SECRET_KEY", "dev-only-secret-key")
    DEBUG = os.environ.get("DEBUG") == "True"
    SQLALCHEMY_DATABASE_URI = os.environ.get("DATABASE_URL", "sqlite:///:memory:")
    SQLALCHEMY_TRACK_MODIFICATIONS = False
    AUTO_CREATE_DB = True
    APP_HOST = os.environ.get("APP_HOST", "127.0.0.1")
    APP_PORT = int(os.environ.get("APP_PORT", "5000"))
    WAITRESS_THREADS = int(os.environ.get("WAITRESS_THREADS", "4"))
    SESSION_COOKIE_HTTPONLY = True
    SESSION_COOKIE_SAMESITE = os.environ.get("SESSION_COOKIE_SAMESITE", "Lax")
    SESSION_COOKIE_SECURE = (
        os.environ.get("SESSION_COOKIE_SECURE", "false").strip().lower()
        in {"1", "true", "yes", "on"}
    )


class DevelopmentConfig(Config):
    DEBUG = True


class TestingConfig(Config):
    TESTING = True
    SQLALCHEMY_DATABASE_URI = "sqlite:///:memory:"


class ProductionConfig(Config):
    DEBUG = False
    AUTO_CREATE_DB = os.environ.get("AUTO_CREATE_DB") == "True"


CONFIG_BY_NAME = {
    "development": DevelopmentConfig,
    "testing": TestingConfig,
    "production": ProductionConfig,
    "default": Config,
}
