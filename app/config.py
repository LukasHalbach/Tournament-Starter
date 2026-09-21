import os


def _bool_env(name, default=False):
    val = os.environ.get(name)
    if val is None:
        return default
    return val.strip().lower() in ("1", "true", "yes", "on")


class Config:
    SECRET_KEY = os.environ.get("SECRET_KEY", "dev-secret-key-change-me")

    _database_url = os.environ.get("DATABASE_URL")
    if _database_url and _database_url.startswith("postgres://"):
        # SQLAlchemy needs the postgresql:// scheme.
        _database_url = _database_url.replace("postgres://", "postgresql://", 1)
    SQLALCHEMY_DATABASE_URI = _database_url or "sqlite:///" + os.path.join(
        os.getcwd(), "instance", "tournament.db"
    )
    SQLALCHEMY_TRACK_MODIFICATIONS = False

    ADMIN_PASSWORD = os.environ.get("ADMIN_PASSWORD", "")

    UPLOAD_DIR = os.environ.get("UPLOAD_DIR", os.path.join(os.getcwd(), "instance", "uploads"))
    MAX_UPLOAD_SIZE_BYTES = int(os.environ.get("MAX_UPLOAD_SIZE_BYTES", 1024 * 1024 * 1024))
    ALLOWED_UPLOAD_EXTENSIONS = {
        "pdf", "ai", "eps", "psd", "svg", "png", "jpg", "jpeg", "tif", "tiff", "zip",
    }

    CATALOG_PATH = os.environ.get("CATALOG_PATH", os.path.join(os.getcwd(), "catalog.yaml"))
    DEFAULT_COURSE_HOLES = int(os.environ.get("DEFAULT_COURSE_HOLES", 18))

    SMTP_HOST = os.environ.get("SMTP_HOST")
    SMTP_PORT = int(os.environ.get("SMTP_PORT", 587))
    SMTP_USERNAME = os.environ.get("SMTP_USERNAME")
    SMTP_PASSWORD = os.environ.get("SMTP_PASSWORD")
    SMTP_FROM = os.environ.get("SMTP_FROM")
    TSI_NOTIFY_EMAIL = os.environ.get("TSI_NOTIFY_EMAIL")

    WTF_CSRF_TIME_LIMIT = None


class TestConfig(Config):
    TESTING = True
    SQLALCHEMY_DATABASE_URI = "sqlite:///:memory:"
    WTF_CSRF_ENABLED = False
