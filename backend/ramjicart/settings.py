import os

from pathlib import Path

import dj_database_url
from django.core.exceptions import ImproperlyConfigured
from dotenv import load_dotenv


BASE_DIR = Path(__file__).resolve().parent.parent
REPO_ROOT = BASE_DIR.parent
load_dotenv(BASE_DIR / ".env")
load_dotenv(REPO_ROOT / ".env")


def env_bool(name, default):
    return os.environ.get(name, str(default)).lower() in {"1", "true", "yes"}


GOOGLE_MAPS_API_KEY = os.environ.get("GOOGLE_MAPS_API_KEY", "").strip()
GOOGLE_MAPS_MAP_ID = os.environ.get("GOOGLE_MAPS_MAP_ID", "").strip()
FIREBASE_AUTH_ENABLED = env_bool("FIREBASE_AUTH_ENABLED", False)
FIREBASE_WEB_CONFIG = {
    "apiKey": os.environ.get("FIREBASE_API_KEY", "").strip(),
    "authDomain": os.environ.get("FIREBASE_AUTH_DOMAIN", "").strip(),
    "projectId": os.environ.get("FIREBASE_PROJECT_ID", "").strip(),
    "appId": os.environ.get("FIREBASE_APP_ID", "").strip(),
}
FIREBASE_JS_SDK_VERSION = os.environ.get("FIREBASE_JS_SDK_VERSION", "13.1.0").strip()
FIREBASE_SERVICE_ACCOUNT_FILE = os.environ.get(
    "FIREBASE_SERVICE_ACCOUNT_FILE",
    os.environ.get("GOOGLE_APPLICATION_CREDENTIALS", ""),
).strip()
FIREBASE_SERVICE_ACCOUNT_JSON = os.environ.get(
    "FIREBASE_SERVICE_ACCOUNT_JSON", ""
).strip()
if FIREBASE_AUTH_ENABLED:
    missing_firebase_config = [
        key for key, value in FIREBASE_WEB_CONFIG.items() if not value
    ]
    if missing_firebase_config:
        raise ImproperlyConfigured(
            "Firebase Authentication is enabled but its web config is incomplete."
        )
    if not FIREBASE_SERVICE_ACCOUNT_FILE and not FIREBASE_SERVICE_ACCOUNT_JSON:
        raise ImproperlyConfigured(
            "Firebase Authentication requires a service account file or JSON."
        )
    if FIREBASE_SERVICE_ACCOUNT_FILE and not Path(FIREBASE_SERVICE_ACCOUNT_FILE).is_file():
        raise ImproperlyConfigured("FIREBASE_SERVICE_ACCOUNT_FILE does not exist.")
DELIVERY_DISPATCH_RADIUS_KM = float(
    os.environ.get("DELIVERY_DISPATCH_RADIUS_KM", "10")
)
if DELIVERY_DISPATCH_RADIUS_KM <= 0:
    raise ImproperlyConfigured("DELIVERY_DISPATCH_RADIUS_KM must be greater than zero.")

CASHFREE_ENABLED = env_bool("CASHFREE_ENABLED", False)
CASHFREE_APP_ID = os.environ.get("CASHFREE_APP_ID", "").strip()
CASHFREE_SECRET_KEY = os.environ.get("CASHFREE_SECRET_KEY", "").strip()
CASHFREE_ENVIRONMENT = os.environ.get("CASHFREE_ENVIRONMENT", "sandbox").strip().lower()
CASHFREE_API_VERSION = os.environ.get("CASHFREE_API_VERSION", "2025-01-01").strip()
if CASHFREE_ENVIRONMENT not in {"sandbox", "production"}:
    raise ImproperlyConfigured("CASHFREE_ENVIRONMENT must be sandbox or production.")
if CASHFREE_ENABLED and (not CASHFREE_APP_ID or not CASHFREE_SECRET_KEY):
    raise ImproperlyConfigured(
        "Cashfree is enabled but CASHFREE_APP_ID or CASHFREE_SECRET_KEY is missing."
    )
DEBUG = env_bool("DJANGO_DEBUG", True)
SECRET_KEY = os.environ.get("DJANGO_SECRET_KEY")
if not SECRET_KEY:
    if not DEBUG:
        raise ImproperlyConfigured("DJANGO_SECRET_KEY must be set when DEBUG is disabled.")
    SECRET_KEY = "dev-only-change-this-secret"

ALLOWED_HOSTS = [
    host.strip()
    for host in os.environ.get(
        "DJANGO_ALLOWED_HOSTS", "127.0.0.1,localhost"
    ).split(",")
    if host.strip()
]

CSRF_TRUSTED_ORIGINS = [
    origin.strip()
    for origin in os.environ.get("DJANGO_CSRF_TRUSTED_ORIGINS", "").split(",")
    if origin.strip()
]
CORS_ALLOWED_ORIGINS = [
    origin.strip()
    for origin in os.environ.get("CORS_ALLOWED_ORIGINS", "").split(",")
    if origin.strip()
]
CORS_ALLOW_CREDENTIALS = True
CORS_URLS_REGEX = r"^/api/.*$"
DJANGO_CSRF_COOKIE_DOMAIN = os.environ.get("DJANGO_CSRF_COOKIE_DOMAIN", "").strip() or None

INSTALLED_APPS = [
    "django.contrib.admin",
    "django.contrib.auth",
    "django.contrib.contenttypes",
    "django.contrib.sessions",
    "django.contrib.messages",
    "django.contrib.staticfiles",
    "axes",
    "corsheaders",
    "orders.apps.OrdersConfig",
]

MIDDLEWARE = [
    "corsheaders.middleware.CorsMiddleware",
    "django.middleware.security.SecurityMiddleware",
    "whitenoise.middleware.WhiteNoiseMiddleware",
    "django.contrib.sessions.middleware.SessionMiddleware",
    "django.middleware.common.CommonMiddleware",
    "django.middleware.csrf.CsrfViewMiddleware",
    "django.contrib.auth.middleware.AuthenticationMiddleware",
    "django.contrib.messages.middleware.MessageMiddleware",
    "django.middleware.clickjacking.XFrameOptionsMiddleware",
    "axes.middleware.AxesMiddleware",
    # These two public/authenticated certificate views still return HTML for compatibility.
    "orders.middleware.GalaxyBackgroundMiddleware",
]

# Keep OAuth popups connected to their opener window so Firebase can return
# the Google sign-in result to the page that launched the popup.
SECURE_CROSS_ORIGIN_OPENER_POLICY = "same-origin-allow-popups"

AUTHENTICATION_BACKENDS = [
    "axes.backends.AxesStandaloneBackend",
    "django.contrib.auth.backends.ModelBackend",
]

# Five bad password attempts from one client IP trigger a temporary lockout.
# The reverse proxy forwards the original client IP in the left-most X-Forwarded-For entry.
AXES_FAILURE_LIMIT = 5
AXES_COOLOFF_TIME = 0.25  # 15 minutes, expressed in hours
AXES_USE_ATTEMPT_EXPIRATION = True
AXES_LOCKOUT_PARAMETERS = ["ip_address"]
AXES_IPWARE_META_PRECEDENCE_ORDER = ["HTTP_X_FORWARDED_FOR", "REMOTE_ADDR"]
AXES_IPWARE_PROXY_ORDER = "left-most"
AXES_HTTP_RESPONSE_CODE = 429
AXES_ENABLE_RETRY_AFTER_HEADER = True
AXES_LOCKOUT_CALLABLE = "ramjicart.security.login_lockout_response"

ROOT_URLCONF = "ramjicart.urls"

TEMPLATES = [
    {
        "BACKEND": "django.template.backends.django.DjangoTemplates",
        "DIRS": [],
        "APP_DIRS": True,
        "OPTIONS": {
            "context_processors": [
                "django.template.context_processors.request",
                "django.contrib.auth.context_processors.auth",
                "django.contrib.messages.context_processors.messages",
            ],
        },
    },
]

WSGI_APPLICATION = "ramjicart.wsgi.application"

database_url = os.environ.get("DATABASE_URL")
if database_url:
    DATABASES = {
        "default": dj_database_url.parse(
            database_url,
            conn_max_age=600,
            ssl_require=not DEBUG,
        )
    }
elif DEBUG:
    DATABASES = {
        "default": {
            "ENGINE": "django.db.backends.sqlite3",
            "NAME": REPO_ROOT / "db.sqlite3",
        }
    }
else:
    raise ImproperlyConfigured("DATABASE_URL must be set when DEBUG is disabled.")

AUTH_PASSWORD_VALIDATORS = [
    {"NAME": "django.contrib.auth.password_validation.UserAttributeSimilarityValidator"},
    {"NAME": "django.contrib.auth.password_validation.MinimumLengthValidator"},
    {"NAME": "django.contrib.auth.password_validation.CommonPasswordValidator"},
    {"NAME": "django.contrib.auth.password_validation.NumericPasswordValidator"},
]

LANGUAGE_CODE = "en-in"
TIME_ZONE = "Asia/Kolkata"
USE_I18N = True
USE_TZ = True

STATIC_URL = "/static/"
STATIC_ROOT = BASE_DIR / "staticfiles"
MEDIA_URL = "/media/"
MEDIA_ROOT = REPO_ROOT / "media"
STORAGES = {
    "default": {
        "BACKEND": "django.core.files.storage.FileSystemStorage",
    },
    "staticfiles": {
        "BACKEND": "whitenoise.storage.CompressedStaticFilesStorage",
    },
}
if not DEBUG:
    media_bucket = os.environ.get("AWS_STORAGE_BUCKET_NAME", "").strip()
    if not media_bucket:
        raise ImproperlyConfigured(
            "AWS_STORAGE_BUCKET_NAME must be set in production so uploaded media is not stored on ephemeral local disk."
        )
    STORAGES["default"] = {
        "BACKEND": "storages.backends.s3.S3Storage",
        "OPTIONS": {
            "bucket_name": media_bucket,
            "region_name": os.environ.get("AWS_S3_REGION_NAME", "").strip() or None,
            "default_acl": None,
        },
    }
DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"

if not DEBUG:
    SECURE_PROXY_SSL_HEADER = ("HTTP_X_FORWARDED_PROTO", "https")
    SECURE_SSL_REDIRECT = True
    SESSION_COOKIE_SECURE = True
    CSRF_COOKIE_SECURE = True
    SESSION_COOKIE_SAMESITE = "Lax"
    CSRF_COOKIE_SAMESITE = "Lax"
    CSRF_COOKIE_DOMAIN = DJANGO_CSRF_COOKIE_DOMAIN
    SECURE_HSTS_SECONDS = 31536000
    SECURE_HSTS_INCLUDE_SUBDOMAINS = True
