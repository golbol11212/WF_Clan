import os
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent

# Загружаем .env файл если есть
_env_file = BASE_DIR / '.env'
if _env_file.exists():
    for _line in _env_file.read_text(encoding='utf-8').splitlines():
        _line = _line.strip()
        if _line and not _line.startswith('#') and '=' in _line:
            _k, _v = _line.split('=', 1)
            os.environ.setdefault(_k.strip(), _v.strip())

SECRET_KEY = 'wf-clan-secret-key-change-in-production-2025'

DEBUG = True

ALLOWED_HOSTS = ['*']

INSTALLED_APPS = [
    'django.contrib.admin',
    'django.contrib.auth',
    'django.contrib.contenttypes',
    'django.contrib.sessions',
    'django.contrib.messages',
    'django.contrib.staticfiles',
    'rest_framework',
    'rest_framework.authtoken',
    'corsheaders',
    'clan',
]

MIDDLEWARE = [
    'corsheaders.middleware.CorsMiddleware',
    'django.middleware.security.SecurityMiddleware',
    'django.contrib.sessions.middleware.SessionMiddleware',
    'django.middleware.common.CommonMiddleware',
    'django.middleware.csrf.CsrfViewMiddleware',
    'django.contrib.auth.middleware.AuthenticationMiddleware',
    'django.contrib.messages.middleware.MessageMiddleware',
    'django.middleware.clickjacking.XFrameOptionsMiddleware',
]

ROOT_URLCONF = 'wfproject.urls'

TEMPLATES = [
    {
        'BACKEND': 'django.template.backends.django.DjangoTemplates',
        'DIRS': [BASE_DIR],           # Ищем шаблоны прямо в корне проекта
        'APP_DIRS': True,
        'OPTIONS': {
            'context_processors': [
                'django.template.context_processors.debug',
                'django.template.context_processors.request',
                'django.contrib.auth.context_processors.auth',
                'django.contrib.messages.context_processors.messages',
            ],
        },
    },
]

WSGI_APPLICATION = 'wfproject.wsgi.application'

DATABASE_URL = os.environ.get('DATABASE_URL', '')
if DATABASE_URL:
    import urllib.parse
    _u = urllib.parse.urlparse(DATABASE_URL)
    DATABASES = {
        'default': {
            'ENGINE': 'django.db.backends.postgresql',
            'NAME': _u.path.lstrip('/'),
            'USER': _u.username,
            'PASSWORD': _u.password,
            'HOST': _u.hostname,
            'PORT': _u.port or 5432,
        }
    }
else:
    DATABASES = {
        'default': {
            'ENGINE': 'django.db.backends.sqlite3',
            'NAME': BASE_DIR / 'db.sqlite3',
        }
    }

LANGUAGE_CODE = 'ru-ru'
TIME_ZONE = 'Europe/Moscow'
USE_I18N = True
USE_TZ = True

STATIC_URL = '/static/'
STATIC_ROOT = BASE_DIR / 'staticfiles'
STATICFILES_DIRS = [BASE_DIR / 'clan' / 'static'] if (BASE_DIR / 'clan' / 'static').exists() else []

DEFAULT_AUTO_FIELD = 'django.db.models.BigAutoField'

# CORS — разрешаем все источники в режиме DEBUG
CORS_ALLOW_ALL_ORIGINS = DEBUG

# YouTube Data API v3 (нужен для автозаполнения просмотров/длительности/даты)
# Получить ключ: https://console.cloud.google.com/ → YouTube Data API v3
YOUTUBE_API_KEY = ''  # вставь сюда свой ключ

# Discord webhooks
DISCORD_WEBHOOK_URL        = 'https://discord.com/api/webhooks/1478693170542936184/SFQlxMJii2cG52Eh3rfhb-xNAf3XB_f4hl9koAXFWvzdkW7qsPWD5vjW3Q3Qlotn6KUz'  # заявки
DISCORD_CLAN_WEBHOOK_URL   = 'https://discord.com/api/webhooks/1478885072592437279/4W7AGtOImnnzbisvP0oJ66iSt7zcmtz0Uy6pCdX8m8cP67rsvIpQiRyofgODW-qt4zq3'  # вайпы + регистрации
DISCORD_ROSTER_WEBHOOK_URL = 'https://discord.com/api/webhooks/1478887988850327713/XDEFpiavVScpUuHI6fKtoFnOvBCJjhJwLJ5CxvRdinmLbAeM49SuPd8NQdEWnE8zK5dh'  # состав клана

# Discord бот (токен хранится в .env файле)
DISCORD_BOT_TOKEN = os.environ.get('DISCORD_BOT_TOKEN', '')

REST_FRAMEWORK = {
    'DEFAULT_RENDERER_CLASSES': [
        'rest_framework.renderers.JSONRenderer',
    ],
    'DEFAULT_AUTHENTICATION_CLASSES': [],
    'DEFAULT_PERMISSION_CLASSES': [],
}
