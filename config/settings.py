"""Django settings for the dropship system."""
import os
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent


def _load_dotenv(path):
    """Minimal .env loader (KEY=VALUE per line) to avoid extra dependencies."""
    if not path.exists():
        return
    for line in path.read_text().splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        value = value.strip().strip('"').strip("'").replace("\\n", "\n")
        os.environ.setdefault(key.strip(), value)


_load_dotenv(BASE_DIR / ".env")


def env(key, default=""):
    return os.environ.get(key, default)


SECRET_KEY = env("DJANGO_SECRET_KEY", "dev-insecure-change-me-in-production")
DEBUG = env("DJANGO_DEBUG", "1") == "1"
ALLOWED_HOSTS = [h for h in env("DJANGO_ALLOWED_HOSTS", "127.0.0.1,localhost,testserver").split(",") if h]
CSRF_TRUSTED_ORIGINS = [o for o in env("DJANGO_CSRF_TRUSTED_ORIGINS", "").split(",") if o]

INSTALLED_APPS = [
    "django.contrib.admin",
    "django.contrib.auth",
    "django.contrib.contenttypes",
    "django.contrib.sessions",
    "django.contrib.messages",
    "django.contrib.staticfiles",
    "django.contrib.humanize",
    "accounts",
    "catalog",
    "orders",
    "payments",
    "payouts",
    "dashboard",
]

MIDDLEWARE = [
    "django.middleware.security.SecurityMiddleware",
    "django.contrib.sessions.middleware.SessionMiddleware",
    "django.middleware.common.CommonMiddleware",
    "django.middleware.csrf.CsrfViewMiddleware",
    "django.contrib.auth.middleware.AuthenticationMiddleware",
    "django.contrib.messages.middleware.MessageMiddleware",
    "django.middleware.clickjacking.XFrameOptionsMiddleware",
]

ROOT_URLCONF = "config.urls"

TEMPLATES = [
    {
        "BACKEND": "django.template.backends.django.DjangoTemplates",
        "DIRS": [BASE_DIR / "templates"],
        "APP_DIRS": True,
        "OPTIONS": {
            "context_processors": [
                "django.template.context_processors.debug",
                "django.template.context_processors.request",
                "django.contrib.auth.context_processors.auth",
                "django.contrib.messages.context_processors.messages",
                "catalog.context_processors.stock_freshness",
            ],
        },
    },
]

WSGI_APPLICATION = "config.wsgi.application"

DATABASES = {
    "default": {
        "ENGINE": "django.db.backends.sqlite3",
        "NAME": BASE_DIR / "db.sqlite3",
    }
}

AUTH_USER_MODEL = "accounts.User"
AUTH_PASSWORD_VALIDATORS = [
    {"NAME": "django.contrib.auth.password_validation.UserAttributeSimilarityValidator"},
    {"NAME": "django.contrib.auth.password_validation.MinimumLengthValidator"},
    {"NAME": "django.contrib.auth.password_validation.CommonPasswordValidator"},
    {"NAME": "django.contrib.auth.password_validation.NumericPasswordValidator"},
]
LOGIN_URL = "accounts:login"
LOGIN_REDIRECT_URL = "accounts:home"
LOGOUT_REDIRECT_URL = "accounts:login"

LANGUAGE_CODE = "en-us"
TIME_ZONE = "Asia/Kuala_Lumpur"
USE_I18N = True
USE_TZ = True

STATIC_URL = "static/"
STATIC_ROOT = BASE_DIR / "staticfiles"
MEDIA_URL = "/media/"
MEDIA_ROOT = BASE_DIR / "media"

DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"

# --- Business rules -------------------------------------------------------
STOCK_STALE_HOURS = int(env("STOCK_STALE_HOURS", "24"))
ORDER_PAYMENT_TIMEOUT_MINUTES = int(env("ORDER_PAYMENT_TIMEOUT_MINUTES", "30"))
ORDER_AUTO_COMPLETE_DAYS = int(env("ORDER_AUTO_COMPLETE_DAYS", "14"))

# --- Payment gateway ------------------------------------------------------
PAYMENT_GATEWAY = env("PAYMENT_GATEWAY", "dummy")  # "dummy" | "chip"
CHIP_API_BASE = env("CHIP_API_BASE", "https://gate.chip-in.asia/api/v1")
CHIP_SECRET_KEY = env("CHIP_SECRET_KEY", "")
CHIP_BRAND_ID = env("CHIP_BRAND_ID", "")
CHIP_PUBLIC_KEY = env("CHIP_PUBLIC_KEY", "")  # optional; fetched from /public_key/ if empty
SITE_URL = env("SITE_URL", "http://127.0.0.1:8000").rstrip("/")

CACHES = {"default": {"BACKEND": "django.core.cache.backends.locmem.LocMemCache"}}

# --- Affiliate commission & CHIP Send Payouts -----------------------------
from decimal import Decimal
DROPSHIP_COMMISSION_PERCENT = Decimal(env("DROPSHIP_COMMISSION_PERCENT", "15.0"))
MINIMUM_PAYOUT_AMOUNT = Decimal(env("MINIMUM_PAYOUT_AMOUNT", "10.00"))

CHIP_SEND_SIMULATOR = env("CHIP_SEND_SIMULATOR", "1") == "1"
CHIP_SEND_API_BASE = env("CHIP_SEND_API_BASE", "https://staging-api.chip-in.asia/api").rstrip("/")
CHIP_SEND_API_KEY = env("CHIP_SEND_API_KEY", "")
CHIP_SEND_API_SECRET = env("CHIP_SEND_API_SECRET", "")

LOGGING = {
    "version": 1,
    "disable_existing_loggers": False,
    "handlers": {"console": {"class": "logging.StreamHandler"}},
    "loggers": {
        "payments": {"handlers": ["console"], "level": "INFO"},
        "payouts": {"handlers": ["console"], "level": "INFO"},
    },
}
