from pathlib import Path
import dj_database_url
import os

BASE_DIR = Path(__file__).resolve().parent.parent

SECRET_KEY = 'django-insecure-xn*7_bv!q0bnm)-p54^-@2(9$0b&qv7)b^2^vrb7py@wb%$#)0'

DEBUG = os.environ.get('DEBUG', 'False') == 'True'

ALLOWED_HOSTS =['visitasmedicasdiphasac-production.up.railway.app']
CSRF_TRUSTED_ORIGINS = ['https://visitasmedicasdiphasac-production.up.railway.app']

AUTH_USER_MODEL = 'usuarios.Usuario'
LOGIN_REDIRECT_URL = 'inicio'
LOGOUT_REDIRECT_URL = '/'

# Application definition

INSTALLED_APPS = [
    'django.contrib.admin',
    'django.contrib.auth',
    'django.contrib.contenttypes',
    'django.contrib.sessions',
    'django.contrib.messages',
    'django.contrib.staticfiles',
    'apps.usuarios',
    'apps.doctores',
    'apps.asistencia',
    'apps.productos',
    'apps.rutas',
    'apps.visitas',
    'apps.ubicaciones',
]

MIDDLEWARE = [
    'django.middleware.security.SecurityMiddleware',
    'django.contrib.sessions.middleware.SessionMiddleware',
    'django.middleware.common.CommonMiddleware',
    'django.middleware.csrf.CsrfViewMiddleware',
    'django.contrib.auth.middleware.AuthenticationMiddleware',
    'django.contrib.messages.middleware.MessageMiddleware',
    'django.middleware.clickjacking.XFrameOptionsMiddleware',
    'apps.usuarios.middlewares.PasswordChangeMiddleware',
]

ROOT_URLCONF = 'visitas_medicas.urls'

TEMPLATES = [
    {
        'BACKEND': 'django.template.backends.django.DjangoTemplates',
        'DIRS': [os.path.join(BASE_DIR, 'templates')],
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

WSGI_APPLICATION = 'visitas_medicas.wsgi.application'


# Database

DATABASES = {
    'default': dj_database_url.config(default=os.environ.get('DATABASE_URL'))
}


# Password validation

AUTH_PASSWORD_VALIDATORS = [
    {
        'NAME': 'django.contrib.auth.password_validation.UserAttributeSimilarityValidator',
    },
    {
        'NAME': 'django.contrib.auth.password_validation.MinimumLengthValidator',
    },
    {
        'NAME': 'django.contrib.auth.password_validation.CommonPasswordValidator',
    },
    {
        'NAME': 'django.contrib.auth.password_validation.NumericPasswordValidator',
    },
]


# Internationalization

LANGUAGE_CODE = 'en-us'

TIME_ZONE = 'America/Lima'

USE_I18N = True

USE_TZ = True


# Static files (CSS, JavaScript, Images)

STATIC_URL = 'static/'

# Default primary key field type

DEFAULT_AUTO_FIELD = 'django.db.models.BigAutoField'

STATICFILES_DIRS = [
    BASE_DIR / "static",
]
