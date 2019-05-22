"""
Django settings for wewillfixyourpc_bot project.

Generated by 'django-admin startproject' using Django 2.1.3.

For more information on this file, see
https://docs.djangoproject.com/en/2.1/topics/settings/

For the full list of settings and their values, see
https://docs.djangoproject.com/en/2.1/ref/settings/
"""

import os
import json

# Build paths inside the project like this: os.path.join(BASE_DIR, ...)
BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


# Quick-start development settings - unsuitable for production
# See https://docs.djangoproject.com/en/2.1/howto/deployment/checklist/

# SECURITY WARNING: keep the secret key used in production secret!
with open(os.path.join(BASE_DIR, "SECRET_KEY")) as f:
    SECRET_KEY = f.read()

# SECURITY WARNING: don't run with debug turned on in production!
DEBUG = False

ALLOWED_HOSTS = ["cardifftec.uk"]


# Application definition

INSTALLED_APPS = [
    'django.contrib.admin',
    'django.contrib.auth',
    'django.contrib.contenttypes',
    'django.contrib.sessions',
    'django.contrib.messages',
    'django.contrib.staticfiles',
    'djsingleton',
    'phonenumber_field',
    'fulfillment',
    'facebook',
    'twitter',
    'operator_interface',
    'dialogflow_client',
]

MIDDLEWARE = [
    'django.middleware.security.SecurityMiddleware',
    'django.contrib.sessions.middleware.SessionMiddleware',
    'django.middleware.common.CommonMiddleware',
    'django.middleware.csrf.CsrfViewMiddleware',
    'django.contrib.auth.middleware.AuthenticationMiddleware',
    'django.contrib.messages.middleware.MessageMiddleware',
    'django.middleware.clickjacking.XFrameOptionsMiddleware',
]

ROOT_URLCONF = 'wewillfixyourpc_bot.urls'

TEMPLATES = [
    {
        'BACKEND': 'django.template.backends.django.DjangoTemplates',
        'DIRS': [os.path.join(BASE_DIR, 'templates')]
        ,
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

WSGI_APPLICATION = 'wewillfixyourpc_bot.wsgi.application'


# Database
# https://docs.djangoproject.com/en/2.1/ref/settings/#databases

DATABASES = {
    'default': {
        'ENGINE': 'django.db.backends.mysql',
        'HOST': 'localhost',
        'NAME': 'bot',
        'USER': 'bot',
        'PASSWORD': open('DB_PASS').read().strip(),
        'OPTIONS': {
            'read_default_file': '/path/to/my.cnf',
        },
    }
}


# Password validation
# https://docs.djangoproject.com/en/2.1/ref/settings/#auth-password-validators

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
# https://docs.djangoproject.com/en/2.1/topics/i18n/

LANGUAGE_CODE = 'en-us'

TIME_ZONE = 'UTC'

USE_I18N = True

USE_L10N = True

USE_TZ = True


# Static files (CSS, JavaScript, Images)
# https://docs.djangoproject.com/en/2.1/howto/static-files/

STATIC_URL = 'https://cardifftec.uk/static/'
STATIC_ROOT = os.path.join(BASE_DIR, 'static')

MEDIA_URL = 'https://cardifftec.uk/media/'
MEDIA_ROOT = os.path.join(BASE_DIR, 'media')

EXTERNAL_URL_BASE = "https://cardifftec.uk/"

PHONENUMBER_DEFAULT_REGION = "GB"

CELERY_RESULT_BACKEND = "redis://localhost"
CELERY_BROKER_URL = "pyamqp://"
CELERY_TASK_SERIALIZER = "json"
CELERY_ACCEPT_CONTENT = ["json"]

with open(os.path.join(BASE_DIR, "facebook.json")) as f:
    facebook_conf = json.load(f)
with open(os.path.join(BASE_DIR, "twitter.json")) as f:
    twitter_conf = json.load(f)

FACEBOOK_VERIFY_TOKEN = facebook_conf["verify_token"]
FACEBOOK_ACCESS_TOKEN = facebook_conf["access_token"]

TWITTER_CONSUMER_KEY = twitter_conf["consumer_key"]
TWITTER_CONSUMER_SECRET = twitter_conf["consumer_secret"]
TWITTER_ACCESS_TOKEN = twitter_conf["access_token"]
TWITTER_ACCESS_TOKEN_SECRET = twitter_conf["access_token_secret"]

TWITTER_ENVNAME = "main"

GOOGLE_CREDENTIALS_FILE = "WeWillFixYourPC.json"
GOOGLE_PROJECT_ID = "wewillfixyourpc-8df73"

LOGGING = {
    'version': 1,
    'disable_existing_loggers': False,
    'handlers': {
        'console': {
            'level': 'DEBUG',
            'filters': None,
            'class': 'logging.StreamHandler',
        },
    },
    'loggers': {
        'django': {
            'handlers': ['console'],
            'level': 'INFO',
        },
        'twitter': {
            'handlers': ['console'],
            'level': 'DEBUG',
        },
        'facebook': {
            'handlers': ['console'],
            'level': 'DEBUG',
        },
        'dialogflow_client': {
            'handlers': ['console'],
            'level': 'DEBUG',
        },
        'fulfillment_client': {
            'handlers': ['console'],
            'level': 'DEBUG',
        },
    },
}
