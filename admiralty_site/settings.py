"""
Admiralty — Standalone FOIA Workflow Tool
Django settings for standalone deployment at admiralty.docklabs.ai
"""
import os
from pathlib import Path
from dotenv import load_dotenv

load_dotenv()

BASE_DIR = Path(__file__).resolve().parent.parent

DEBUG = os.environ.get('DJANGO_DEBUG', 'False').lower() in ('true', '1', 'yes')

import secrets as _secrets

SECRET_KEY = os.environ.get('DJANGO_SECRET_KEY', '')
if not SECRET_KEY:
    if DEBUG:
        SECRET_KEY = _secrets.token_hex(25)
    else:
        from django.core.exceptions import ImproperlyConfigured
        raise ImproperlyConfigured('DJANGO_SECRET_KEY must be set in production')

# AI enrichment (Claude API)
ANTHROPIC_API_KEY = os.environ.get('ANTHROPIC_API_KEY', '')

# Demo mode
DEMO_MODE = os.environ.get('DEMO_MODE', 'False').lower() in ('true', '1', 'yes')
DEMO_ROLES = ['foia_officer', 'foia_attorney', 'admin']
DEMO_PASSWORD = os.environ.get('DEMO_PASSWORD', 'demo' + '2026!')

ALLOWED_HOSTS = os.environ.get('DJANGO_ALLOWED_HOSTS', 'localhost,127.0.0.1').split(',')

RAILWAY_DOMAIN = os.environ.get('RAILWAY_PUBLIC_DOMAIN', '')
if RAILWAY_DOMAIN:
    ALLOWED_HOSTS.append(RAILWAY_DOMAIN)
    ALLOWED_HOSTS.append('.railway.app')

CSRF_TRUSTED_ORIGINS = os.environ.get('CSRF_TRUSTED_ORIGINS', '').split(',')
if RAILWAY_DOMAIN:
    CSRF_TRUSTED_ORIGINS.append(f'https://{RAILWAY_DOMAIN}')
CSRF_TRUSTED_ORIGINS = [o for o in CSRF_TRUSTED_ORIGINS if o]

# Standalone site URL (used for email links)
ADMIRALTY_SITE_URL = os.environ.get('ADMIRALTY_SITE_URL', 'http://localhost:8000')

# ---------------------------------------------------------------------------
# Installed Apps — minimal set for standalone FOIA
# ---------------------------------------------------------------------------
INSTALLED_APPS = [
    'django.contrib.admin',
    'django.contrib.auth',
    'django.contrib.contenttypes',
    'django.contrib.sessions',
    'django.contrib.messages',
    'django.contrib.staticfiles',
    'django.contrib.humanize',
    # Keel shared platform
    'keel.core',
    'keel.security',
    'keel.notifications',
    'keel.comms',
    'keel.requests',
    # Third party
    'crispy_forms',
    'crispy_bootstrap5',
    # Admiralty core (notifications, preferences)
    'core.apps.AdmiraltyConfig',
    # FOIA app
    'foia.apps.FoiaConfig',
]

MIDDLEWARE = [
    'django.middleware.security.SecurityMiddleware',
    'keel.security.middleware.SecurityHeadersMiddleware',
    'keel.security.middleware.FailedLoginMonitor',
    'whitenoise.middleware.WhiteNoiseMiddleware',
    'django.contrib.sessions.middleware.SessionMiddleware',
    'django.middleware.common.CommonMiddleware',
    'django.middleware.csrf.CsrfViewMiddleware',
    'django.contrib.auth.middleware.AuthenticationMiddleware',
    'django.contrib.messages.middleware.MessageMiddleware',
    'django.middleware.clickjacking.XFrameOptionsMiddleware',
    'keel.core.middleware.AuditMiddleware',
]

ROOT_URLCONF = 'admiralty_site.urls'

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
                'keel.core.context_processors.site_context',
                'foia.context_processors.foia_context',
            ],
        },
    },
]

WSGI_APPLICATION = 'admiralty.wsgi.application'

# Database — separate from Beacon
import dj_database_url

DATABASES = {
    'default': dj_database_url.config(
        default=f'sqlite:///{BASE_DIR / "db_admiralty.sqlite3"}',
        conn_max_age=600,
    )
}

# Use Django's built-in User model (no core.User dependency)
# AUTH_USER_MODEL defaults to 'auth.User'

# Redirect migrations for foia app to standalone migration set
MIGRATION_MODULES = {
    'foia': 'admiralty_site.migrations.foia',
}

AUTH_PASSWORD_VALIDATORS = [
    {'NAME': 'django.contrib.auth.password_validation.UserAttributeSimilarityValidator'},
    {'NAME': 'django.contrib.auth.password_validation.MinimumLengthValidator'},
    {'NAME': 'django.contrib.auth.password_validation.CommonPasswordValidator'},
    {'NAME': 'django.contrib.auth.password_validation.NumericPasswordValidator'},
]
AUTH_PASSWORD_VALIDATORS[1]['OPTIONS'] = {'min_length': 10}

LANGUAGE_CODE = 'en-us'
TIME_ZONE = 'America/New_York'
USE_I18N = True
USE_TZ = True

# Static files
STATIC_URL = '/static/'
STATICFILES_DIRS = [BASE_DIR / 'static']
STATIC_ROOT = BASE_DIR / 'staticfiles_admiralty'
WHITENOISE_MANIFEST_STRICT = False
STORAGES = {
    "default": {
        "BACKEND": "django.core.files.storage.FileSystemStorage",
    },
    "staticfiles": {
        "BACKEND": "whitenoise.storage.CompressedManifestStaticFilesStorage"
        if not DEBUG
        else "django.contrib.staticfiles.storage.StaticFilesStorage",
    },
}

# Media files
MEDIA_URL = '/media/'
MEDIA_ROOT = BASE_DIR / 'media_admiralty'

# Crispy forms
CRISPY_ALLOWED_TEMPLATE_PACKS = 'bootstrap5'
CRISPY_TEMPLATE_PACK = 'bootstrap5'

# Login/Logout
LOGIN_URL = '/accounts/login/'
LOGIN_REDIRECT_URL = '/foia/dashboard/'
LOGOUT_REDIRECT_URL = '/accounts/login/'

# Email — Resend HTTP API for transactional emails (Railway blocks outbound SMTP)
if DEBUG:
    EMAIL_BACKEND = 'django.core.mail.backends.console.EmailBackend'
else:
    EMAIL_BACKEND = 'keel.notifications.backends.resend_backend.ResendEmailBackend'

DEFAULT_FROM_EMAIL = os.environ.get('DEFAULT_FROM_EMAIL', 'DockLabs <info@docklabs.ai>')
RESEND_API_KEY = os.environ.get('RESEND_API_KEY', '')

DEFAULT_AUTO_FIELD = 'django.db.models.BigAutoField'

# File upload limits
FILE_UPLOAD_MAX_MEMORY_SIZE = 10 * 1024 * 1024  # 10MB
DATA_UPLOAD_MAX_MEMORY_SIZE = 10 * 1024 * 1024

# Logging
LOGGING = {
    'version': 1,
    'disable_existing_loggers': False,
    'formatters': {
        'verbose': {
            'format': '{levelname} {asctime} {module} {message}',
            'style': '{',
        },
    },
    'handlers': {
        'console': {
            'class': 'logging.StreamHandler',
            'formatter': 'verbose',
        },
    },
    'root': {
        'handlers': ['console'],
        'level': 'WARNING',
    },
    'loggers': {
        'django': {'handlers': ['console'], 'level': 'INFO', 'propagate': False},
        'foia': {'handlers': ['console'], 'level': 'INFO', 'propagate': False},
    },
}

# ---------------------------------------------------------------------------
# Security Settings
# ---------------------------------------------------------------------------

SESSION_COOKIE_AGE = 3600
SESSION_SAVE_EVERY_REQUEST = True
SESSION_COOKIE_HTTPONLY = True
CSRF_COOKIE_HTTPONLY = True
SESSION_COOKIE_SAMESITE = 'Lax'

if not DEBUG:
    SECURE_SSL_REDIRECT = False  # Railway handles SSL at the proxy
    SECURE_PROXY_SSL_HEADER = ('HTTP_X_FORWARDED_PROTO', 'https')
    SESSION_COOKIE_SECURE = True
    CSRF_COOKIE_SECURE = True
    SECURE_HSTS_SECONDS = 31536000
    SECURE_HSTS_INCLUDE_SUBDOMAINS = True
    SECURE_HSTS_PRELOAD = True
    SECURE_CONTENT_TYPE_NOSNIFF = True
    SECURE_BROWSER_XSS_FILTER = True
    SECURE_REFERRER_POLICY = 'same-origin'
    X_FRAME_OPTIONS = 'DENY'

# ---------------------------------------------------------------------------
# Keel Configuration
# ---------------------------------------------------------------------------

KEEL_SECURITY_ALERT_RECIPIENTS = [
    os.environ.get('SECURITY_ALERT_EMAIL', 'security@docklabs.ai'),
]
KEEL_SECURITY_ALERT_WEBHOOK = os.environ.get('SECURITY_ALERT_WEBHOOK', '')
KEEL_FILE_SCANNING_ENABLED = not DEBUG
KEEL_CLAMAV_SOCKET = os.environ.get('CLAMAV_SOCKET', '/var/run/clamav/clamd.ctl')
KEEL_CLAMAV_FAIL_CLOSED = True
KEEL_MAX_UPLOAD_SIZE = 10 * 1024 * 1024  # 10MB
KEEL_LOGIN_MAX_FAILURES = 10
KEEL_LOGIN_LOCKOUT_WINDOW = 900       # 15 minutes
KEEL_LOGIN_LOCKOUT_DURATION = 1800    # 30 minutes
KEEL_LOGIN_PATHS = ['/accounts/login/', '/admin/login/']
KEEL_BUSINESS_HOURS = (8, 18)
KEEL_AUDIT_LOG_MODEL = 'core.AuditLog'
KEEL_PRODUCT_NAME = 'Admiralty'
KEEL_PRODUCT_ICON = 'bi-shield-lock'
KEEL_PRODUCT_SUBTITLE = 'FOIA Request Management'
KEEL_NOTIFICATION_MODEL = 'core.Notification'
KEEL_NOTIFICATION_PREFERENCE_MODEL = 'core.NotificationPreference'
KEEL_NOTIFICATION_LOG_MODEL = 'core.NotificationLog'

# Communications (keel.comms)
COMMS_MAIL_DOMAIN = os.environ.get('COMMS_MAIL_DOMAIN', 'mail.docklabs.ai')
COMMS_POSTMARK_SERVER_TOKEN = os.environ.get('COMMS_POSTMARK_SERVER_TOKEN', '')
COMMS_POSTMARK_WEBHOOK_TOKEN = os.environ.get('COMMS_POSTMARK_WEBHOOK_TOKEN', '')
KEEL_CSP_POLICY = "default-src 'self'; script-src 'self' 'unsafe-inline' https://cdn.jsdelivr.net; style-src 'self' 'unsafe-inline' https://cdn.jsdelivr.net https://fonts.googleapis.com; font-src 'self' https://fonts.gstatic.com https://cdn.jsdelivr.net; img-src 'self' data: https:; connect-src 'self'"
KEEL_ALLOWED_UPLOAD_EXTENSIONS = [
    '.pdf', '.doc', '.docx', '.xls', '.xlsx', '.csv',
    '.txt', '.rtf', '.odt', '.ods', '.ppt', '.pptx',
    '.png', '.jpg', '.jpeg', '.gif', '.tiff',
    '.zip', '.gz',
]
