from datetime import timedelta
from pathlib import Path
import os
from urllib.parse import urlparse
import warnings
from dotenv import load_dotenv

BASE_DIR = Path(__file__).resolve().parent.parent
load_dotenv(BASE_DIR.parent / '.env')
SECRET_KEY = os.getenv('SECRET_KEY', 'dev-secret-key-change-before-production')
JWT_SIGNING_KEY = os.getenv('JWT_SIGNING_KEY', SECRET_KEY)
DEBUG = os.getenv('DEBUG', 'True').lower() == 'true'
if not DEBUG and (len(SECRET_KEY.encode()) < 50 or len(JWT_SIGNING_KEY.encode()) < 50):
    raise RuntimeError('Set strong SECRET_KEY and JWT_SIGNING_KEY values (at least 50 characters) before running with DEBUG=False.')
if DEBUG and len(JWT_SIGNING_KEY.encode()) < 32:
    warnings.warn('JWT_SIGNING_KEY is shorter than 32 bytes; use a generated secret of at least 50 characters.', RuntimeWarning)
ALLOWED_HOSTS = [host.strip() for host in os.getenv('ALLOWED_HOSTS', 'localhost,127.0.0.1').split(',') if host.strip()]

INSTALLED_APPS = [
    'django.contrib.admin',
    'django.contrib.auth',
    'django.contrib.contenttypes',
    'django.contrib.sessions',
    'django.contrib.messages',
    'django.contrib.staticfiles',
    'corsheaders',
    'rest_framework',
    'rest_framework_simplejwt',
    'drf_spectacular',
    'accounts',
    'games',
    'catalog',
    'inventory',
    'orders',
    'payments',
    'delivery',
    'integrations',
    'support',
    'audit',
    'api',
]

MIDDLEWARE = [
    'django.middleware.security.SecurityMiddleware',
    'whitenoise.middleware.WhiteNoiseMiddleware',
    'corsheaders.middleware.CorsMiddleware',
    'django.contrib.sessions.middleware.SessionMiddleware',
    'django.middleware.common.CommonMiddleware',
    'django.middleware.csrf.CsrfViewMiddleware',
    'django.contrib.auth.middleware.AuthenticationMiddleware',
    'django.contrib.messages.middleware.MessageMiddleware',
    'django.middleware.clickjacking.XFrameOptionsMiddleware',
]

ROOT_URLCONF = 'config.urls'

TEMPLATES = [
    {
        'BACKEND': 'django.template.backends.django.DjangoTemplates',
        'DIRS': [BASE_DIR / 'templates'],
        'APP_DIRS': True,
        'OPTIONS': {
            'context_processors': [
                'django.template.context_processors.request',
                'django.contrib.auth.context_processors.auth',
                'django.contrib.messages.context_processors.messages',
            ],
        },
    },
]

WSGI_APPLICATION = 'config.wsgi.application'

DATABASE_URL = os.getenv('DATABASE_URL', 'sqlite:///' + str(BASE_DIR / 'db.sqlite3'))
if DATABASE_URL.startswith('sqlite'):
    DATABASES = {'default': {'ENGINE': 'django.db.backends.sqlite3', 'NAME': BASE_DIR / 'db.sqlite3'}}
else:
    parsed_database_url = urlparse(DATABASE_URL)
    DATABASES = {
        'default': {
            'ENGINE': 'django.db.backends.postgresql',
            'NAME': os.getenv('POSTGRES_DB', parsed_database_url.path.lstrip('/') or 'buldrop'),
            'USER': os.getenv('POSTGRES_USER', parsed_database_url.username or 'buldrop'),
            'PASSWORD': os.getenv('POSTGRES_PASSWORD', parsed_database_url.password or ''),
            'HOST': os.getenv('POSTGRES_HOST', parsed_database_url.hostname or 'localhost'),
            'PORT': os.getenv('POSTGRES_PORT', str(parsed_database_url.port or 5432)),
        }
    }

AUTH_PASSWORD_VALIDATORS = [
    {'NAME': 'django.contrib.auth.password_validation.UserAttributeSimilarityValidator'},
    {'NAME': 'django.contrib.auth.password_validation.MinimumLengthValidator', 'OPTIONS': {'min_length': 8}},
    {'NAME': 'django.contrib.auth.password_validation.CommonPasswordValidator'},
    {'NAME': 'django.contrib.auth.password_validation.NumericPasswordValidator'},
]

LANGUAGE_CODE = 'en-us'
TIME_ZONE = 'UTC'
USE_I18N = True
USE_TZ = True

STATIC_URL = '/static/'
STATIC_ROOT = BASE_DIR / 'staticfiles'
STATIC_ROOT.mkdir(parents=True, exist_ok=True)  # avoids WhiteNoise's missing-directory warning before collectstatic
DEFAULT_AUTO_FIELD = 'django.db.models.BigAutoField'
AUTH_USER_MODEL = 'accounts.User'
SESSION_COOKIE_SECURE = not DEBUG
CSRF_COOKIE_SECURE = not DEBUG
SECURE_SSL_REDIRECT = not DEBUG
SECURE_HSTS_SECONDS = 31_536_000 if not DEBUG else 0
SECURE_HSTS_INCLUDE_SUBDOMAINS = not DEBUG
SECURE_CONTENT_TYPE_NOSNIFF = True
X_FRAME_OPTIONS = 'DENY'

LOGGING = {
    'version': 1,
    'disable_existing_loggers': False,
    'formatters': {
        'standard': {
            'format': '{levelname} {asctime} {name}: {message}',
            'style': '{',
        },
    },
    'handlers': {
        'console': {
            'class': 'logging.StreamHandler',
            'formatter': 'standard',
        },
    },
    'loggers': {
        'django': {'handlers': ['console'], 'level': os.getenv('DJANGO_LOG_LEVEL', 'INFO')},
        'orders': {'handlers': ['console'], 'level': os.getenv('APP_LOG_LEVEL', 'INFO'), 'propagate': False},
        'payments': {'handlers': ['console'], 'level': os.getenv('APP_LOG_LEVEL', 'INFO'), 'propagate': False},
        'delivery': {'handlers': ['console'], 'level': os.getenv('APP_LOG_LEVEL', 'INFO'), 'propagate': False},
    },
}

REST_FRAMEWORK = {
    'DEFAULT_AUTHENTICATION_CLASSES': [
        'rest_framework_simplejwt.authentication.JWTAuthentication',
        'rest_framework.authentication.SessionAuthentication',
    ],
    'DEFAULT_PERMISSION_CLASSES': [
        'rest_framework.permissions.IsAuthenticated',
    ],
    'DEFAULT_PAGINATION_CLASS': 'rest_framework.pagination.PageNumberPagination',
    'PAGE_SIZE': 20,
    'DEFAULT_SCHEMA_CLASS': 'drf_spectacular.openapi.AutoSchema',
}

SIMPLE_JWT = {
    'SIGNING_KEY': JWT_SIGNING_KEY,
    'ACCESS_TOKEN_LIFETIME': timedelta(days=1),
    'REFRESH_TOKEN_LIFETIME': timedelta(days=7),
    'ROTATE_REFRESH_TOKENS': True,
}

SPECTACULAR_SETTINGS = {
    'TITLE': 'BulDrop API',
    'DESCRIPTION': 'Gaming digital goods marketplace API',
    'VERSION': '1.0.0',
    'SERVE_INCLUDE_SCHEMA': False,
}

CORS_ALLOWED_ORIGINS = [
    origin.strip()
    for origin in os.getenv('CORS_ALLOWED_ORIGINS', 'http://localhost:3000,http://localhost:8080').split(',')
    if origin.strip()
]
CSRF_TRUSTED_ORIGINS = [
    origin.strip()
    for origin in os.getenv('CSRF_TRUSTED_ORIGINS', 'http://localhost:3000,http://localhost:8080').split(',')
    if origin.strip()
]
SECURE_PROXY_SSL_HEADER = ('HTTP_X_FORWARDED_PROTO', 'https')
USE_X_FORWARDED_HOST = True

CELERY_BROKER_URL = os.getenv('REDIS_URL', 'redis://localhost:6379/0')
CELERY_RESULT_BACKEND = CELERY_BROKER_URL
CELERY_TASK_ALWAYS_EAGER = os.getenv('CELERY_TASK_ALWAYS_EAGER', str(DEBUG).lower()).lower() == 'true'
CELERY_TASK_EAGER_PROPAGATES = True
CELERY_ACCEPT_CONTENT = ['json']
CELERY_TASK_SERIALIZER = 'json'
CELERY_RESULT_SERIALIZER = 'json'
CELERY_TIMEZONE = TIME_ZONE

PLAYPAY_API_URL = os.getenv('PLAYPAY_API_URL', 'https://playpay.uz/app/api')
PLAYPAY_API_KEY = os.getenv('PLAYPAY_API_KEY', '')


def _configured(value):
    """A credential counts as configured only when it is non-empty and not the 'demo' placeholder."""
    return bool(value) and value.strip().lower() != 'demo'


# --- Click (SHOP API) -------------------------------------------------------
CLICK_SERVICE_ID = os.getenv('CLICK_SERVICE_ID', '')
CLICK_MERCHANT_ID = os.getenv('CLICK_MERCHANT_ID', '')
CLICK_MERCHANT_USER_ID = os.getenv('CLICK_MERCHANT_USER_ID', '')
CLICK_SECRET_KEY = os.getenv('CLICK_SECRET_KEY', '')
CLICK_CHECKOUT_URL = os.getenv('CLICK_CHECKOUT_URL', 'https://my.click.uz/services/pay')
CLICK_ENABLED = all(_configured(v) for v in (CLICK_SERVICE_ID, CLICK_MERCHANT_ID, CLICK_SECRET_KEY))

# --- Payme (Merchant API) ---------------------------------------------------
# PAYME_MERCHANT_KEY is the merchant (cash register) id used in the checkout link;
# PAYME_SECRET_KEY is the password Payme sends in Basic auth ("Paycom:<key>").
PAYME_MERCHANT_KEY = os.getenv('PAYME_MERCHANT_KEY', '')
PAYME_SECRET_KEY = os.getenv('PAYME_SECRET_KEY', '')
PAYME_CHECKOUT_URL = os.getenv('PAYME_CHECKOUT_URL', 'https://checkout.paycom.uz')
PAYME_ENABLED = all(_configured(v) for v in (PAYME_MERCHANT_KEY, PAYME_SECRET_KEY))

# Real providers settle in UZS only.
PROVIDER_CURRENCY = 'UZS'

PAYMENT_MODE = os.getenv('PAYMENT_MODE', 'test' if DEBUG else 'disabled')
TEST_PAYMENT_ENABLED = DEBUG and PAYMENT_MODE == 'test'

FRONTEND_URL = os.getenv('FRONTEND_URL', 'http://localhost:3000').rstrip('/')
ORDER_EXPIRY_MINUTES = int(os.getenv('ORDER_EXPIRY_MINUTES', '60'))

CELERY_BEAT_SCHEDULE = {
    'expire-pending-orders': {
        'task': 'orders.tasks.expire_pending_orders',
        'schedule': 300.0,
    },
}
