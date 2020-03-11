"""
Django settings for wewillfixyourpc_bot project.

Generated by 'django-admin startproject' using Django 2.1.3.

For more information on this file, see
https://docs.djangoproject.com/en/2.1/topics/settings/

For the full list of settings and their values, see
https://docs.djangoproject.com/en/2.1/ref/settings/
"""

import os

# Build paths inside the project like this: os.path.join(BASE_DIR, ...)
BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


# Quick-start development settings - unsuitable for production
# See https://docs.djangoproject.com/en/2.1/howto/deployment/checklist/

# SECURITY WARNING: keep the secret key used in production secret!
SECRET_KEY = os.getenv("SECRET_KEY", "")

# SECURITY WARNING: don't run with debug turned on in production!
DEBUG = False

ALLOWED_HOSTS = [os.getenv("HOST", "bot.cardifftec.uk")]

# Application definition
INSTALLED_APPS = [
    "django.contrib.admin",
    "django.contrib.auth",
    "django_keycloak_auth",
    "django.contrib.contenttypes",
    "django.contrib.sessions",
    "django.contrib.messages",
    "django.contrib.staticfiles",
    "channels",
    "djsingleton",
    "phonenumber_field",
    "fulfillment",
    "facebook",
    "twitter",
    "telegram_bot",
    "azure_bot",
    "operator_interface",
    "customer_chat",
    "apple_business_chat",
    "sms",
    "customer_email",
    "whatsapp",
    "rasa_api",
    "api",
    "gactions",
    "corsheaders",
]

MIDDLEWARE = [
    "django.middleware.security.SecurityMiddleware",
    "django.contrib.sessions.middleware.SessionMiddleware",
    "django.middleware.http.ConditionalGetMiddleware",
    "corsheaders.middleware.CorsMiddleware",
    "django.middleware.common.CommonMiddleware",
    "django.middleware.csrf.CsrfViewMiddleware",
    "django.contrib.auth.middleware.AuthenticationMiddleware",
    "django_keycloak_auth.middleware.OIDCMiddleware",
    "django.contrib.messages.middleware.MessageMiddleware",
    "django.middleware.clickjacking.XFrameOptionsMiddleware",
]

ROOT_URLCONF = "wewillfixyourpc_bot.urls"

TEMPLATES = [
    {
        "BACKEND": "django.template.backends.django.DjangoTemplates",
        "DIRS": [os.path.join(BASE_DIR, "templates")],
        "APP_DIRS": True,
        "OPTIONS": {
            "context_processors": [
                "django.template.context_processors.debug",
                "django.template.context_processors.request",
                "django.contrib.auth.context_processors.auth",
                "django.contrib.messages.context_processors.messages",
            ]
        },
    }
]

WSGI_APPLICATION = "wewillfixyourpc_bot.wsgi.application"
ASGI_APPLICATION = "wewillfixyourpc_bot.routing.application"

AUTHENTICATION_BACKENDS = ["django_keycloak_auth.auth.KeycloakAuthorization"]

# Database
# https://docs.djangoproject.com/en/2.1/ref/settings/#databases

DATABASES = {
    "default": {
        "ENGINE": "django.db.backends.postgresql",
        "HOST": os.getenv("DB_HOST", "localhost"),
        "NAME": os.getenv("DB_NAME", "bot"),
        "USER": os.getenv("DB_USER", "bot"),
        "PASSWORD": os.getenv("DB_PASS"),
    }
}

CHANNEL_LAYERS = {
    "default": {
        "BACKEND": "channels_redis.core.RedisChannelLayer",
        "CONFIG": {"hosts": [("redis", 6379)]},
    }
}


# Password validation
# https://docs.djangoproject.com/en/2.1/ref/settings/#auth-password-validators

AUTH_PASSWORD_VALIDATORS = [
    {
        "NAME": "django.contrib.auth.password_validation.UserAttributeSimilarityValidator"
    },
    {"NAME": "django.contrib.auth.password_validation.MinimumLengthValidator"},
    {"NAME": "django.contrib.auth.password_validation.CommonPasswordValidator"},
    {"NAME": "django.contrib.auth.password_validation.NumericPasswordValidator"},
]


# Internationalization
# https://docs.djangoproject.com/en/2.1/topics/i18n/

LANGUAGE_CODE = "en-us"

TIME_ZONE = "UTC"

USE_I18N = True

USE_L10N = True

USE_TZ = True


# Static files (CSS, JavaScript, Images)
# https://docs.djangoproject.com/en/2.1/howto/static-files/

SENTRY_ENVIRONMENT = os.getenv("SENTRY_ENVIRONMENT", "dev")

EXTERNAL_URL_BASE = os.getenv("EXTERNAL_URL", f"https://{ALLOWED_HOSTS[0]}")

STATIC_URL = f"{EXTERNAL_URL_BASE}/static/"
STATIC_ROOT = os.path.join(BASE_DIR, "static")

MEDIA_URL = f"{EXTERNAL_URL_BASE}/media/"
MEDIA_ROOT = os.path.join(BASE_DIR, "media")

PHONENUMBER_DEFAULT_REGION = "GB"

CELERY_RESULT_BACKEND = os.getenv("CELERY_RESULT_BACKEND", "redis://localhost")
CELERY_BROKER_URL = os.getenv("CELERY_BROKER_URL", "pyamqp://")
CELERY_TASK_SERIALIZER = "json"
CELERY_ACCEPT_CONTENT = ["json"]

AZURE_APP_ID = os.getenv("AZURE_APP_ID")
AZURE_APP_PASSWORD = os.getenv("AZURE_APP_PASSWORD")

FACEBOOK_VERIFY_TOKEN = os.getenv("FACEBOOK_VERIFY_TOKEN")
FACEBOOK_ACCESS_TOKEN = os.getenv("FACEBOOK_ACCESS_TOKEN")
FACEBOOK_APP_SECRET = os.getenv("FACEBOOK_APP_SECRET")
FACEBOOK_OPTIN_SECRET = os.getenv("FACEBOOK_OPTIN_SECRET")

TWITTER_CONSUMER_KEY = os.getenv("TWITTER_CONSUMER_KEY")
TWITTER_CONSUMER_SECRET = os.getenv("TWITTER_CONSUMER_SECRET")
TWITTER_ACCESS_TOKEN = os.getenv("TWITTER_ACCESS_TOKEN")
TWITTER_ACCESS_TOKEN_SECRET = os.getenv("TWITTER_ACCESS_TOKEN_SECRET")
TWITTER_ENVNAME = "main"

TWILIO_ACCOUNT = os.getenv("TWILIO_ACCOUNT_ID")
TWILIO_TOKEN = os.getenv("TWILIO_TOKEN")
TWILIO_MSID = os.getenv("TWILIO_MSID")
TWILIO_WHATSAPP_NUMBER = os.getenv("TWILIO_WHATSAPP_NUMBER")

GOOGLE_PROJECT_ID = "we-will-fix-your-pc-c0198"

PUSH_PRIV_KEY = os.getenv("PUSH_PRIV_KEY")

BLIP_KEY = os.getenv("BLIP_KEY")

SENDGRID_KEY = os.getenv("SENDGRID_KEY")

RASA_HTTP_URL = os.getenv("RASA_HTTP_URL", "http://localhost:5005")
VSMS_URL = os.getenv("VSMS_URL", "http://vsms")

EMAIL_HOST = os.getenv("EMAIL_HOST")
EMAIL_PORT = int(os.getenv("EMAIL_PORT", 25))
EMAIL_HOST_USER = os.getenv("EMAIL_HOST_USER")
EMAIL_HOST_PASSWORD = os.getenv("EMAIL_HOST_PASSWORD")
EMAIL_USE_TLS = os.getenv("EMAIL_USE_TLS", False)
EMAIL_USE_SSL = os.getenv("EMAIL_USE_SSL", False)

KEYCLOAK_SERVER_URL = os.getenv("KEYCLOAK_SERVER_URL")
KEYCLOAK_REALM = os.getenv("KEYCLOAK_REALM")
OIDC_CLIENT_ID = os.getenv("KEYCLOAK_CLIENT_ID")
OIDC_CLIENT_SECRET = os.getenv("KEYCLOAK_CLIENT_SECRET")
OIDC_SCOPES = os.getenv("KEYCLOAK_SCOPES")

CORS_ORIGIN_ALLOW_ALL = True
CORS_ALLOW_CREDENTIALS = True
SESSION_COOKIE_SAMESITE = None
SESSION_COOKIE_SECURE = True
SESSION_COOKIE_AGE = 315_360_000

LOGGING = {
    "version": 1,
    "disable_existing_loggers": False,
    "handlers": {
        "console": {"level": "DEBUG", "filters": None, "class": "logging.StreamHandler"}
    },
    "loggers": {
        "django": {"handlers": ["console"], "level": "INFO"},
        "twitter": {"handlers": ["console"], "level": "INFO"},
        "facebook": {"handlers": ["console"], "level": "INFO"},
        "telegram_bot": {"handlers": ["console"], "level": "INFO"},
        "gactions": {"handlers": ["console"], "level": "INFO"},
        "rasa_api": {"handlers": ["console"], "level": "INFO"},
        "fulfillment": {"handlers": ["console"], "level": "INFO"},
        "django_keycloak_auth": {"handlers": ["console"], "level": "INFO"},
        "keycloak": {"handlers": ["console"], "level": "INFO"},
        "apple_business_chat": {"handlers": ["console"], "level": "INFO"},
        "sms": {"handlers": ["console"], "level": "INFO"},
        "customer_chat": {"handlers": ["console"], "level": "INFO"},
    },
}
