from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent

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
STATICFILES_DIRS = [BASE_DIR]

DEFAULT_AUTO_FIELD = 'django.db.models.BigAutoField'

# CORS — разрешаем все источники в режиме DEBUG
CORS_ALLOW_ALL_ORIGINS = DEBUG

# Discord webhooks
DISCORD_WEBHOOK_URL        = 'https://discord.com/api/webhooks/1478693170542936184/SFQlxMJii2cG52Eh3rfhb-xNAf3XB_f4hl9koAXFWvzdkW7qsPWD5vjW3Q3Qlotn6KUz'  # заявки
DISCORD_CLAN_WEBHOOK_URL   = 'https://discord.com/api/webhooks/1478885072592437279/4W7AGtOImnnzbisvP0oJ66iSt7zcmtz0Uy6pCdX8m8cP67rsvIpQiRyofgODW-qt4zq3'  # вайпы + регистрации
DISCORD_ROSTER_WEBHOOK_URL = 'https://discord.com/api/webhooks/1478887988850327713/XDEFpiavVScpUuHI6fKtoFnOvBCJjhJwLJ5CxvRdinmLbAeM49SuPd8NQdEWnE8zK5dh'  # состав клана

REST_FRAMEWORK = {
    'DEFAULT_RENDERER_CLASSES': [
        'rest_framework.renderers.JSONRenderer',
    ],
    'DEFAULT_AUTHENTICATION_CLASSES': [],
    'DEFAULT_PERMISSION_CLASSES': [],
}
