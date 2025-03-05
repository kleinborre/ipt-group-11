"""
Django settings for connectly_project project.

Generated by 'django-admin startproject' using Django 5.1.5.

For more information on this file, see
https://docs.djangoproject.com/en/5.1/topics/settings/

For the full list of settings and their values, see
https://docs.djangoproject.com/en/5.1/ref/settings/
"""

from datetime import timedelta
from pathlib import Path
import os
from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv()

# Build paths inside the project like this: BASE_DIR / 'subdir'.
BASE_DIR = Path(__file__).resolve().parent.parent


# Quick-start development settings - unsuitable for production
# See https://docs.djangoproject.com/en/5.1/howto/deployment/checklist/

# SECURITY WARNING: keep the secret key used in production secret!
SECRET_KEY = 'django-insecure-(!)f&p@=!yj6sv92#d@2qdzu-8fqz(^=6dl&5%5d9_r=6(4j-4'

# SECURITY WARNING: don't run with debug turned on in production!
DEBUG = True

ALLOWED_HOSTS = []


# Application definition

INSTALLED_APPS = [
    'django.contrib.admin',
    'django.contrib.auth',
    'django.contrib.contenttypes',
    'django.contrib.sessions',
    'django.contrib.messages',
    'django.contrib.staticfiles',

    # Instructed apps to be installed
    'rest_framework',
    'posts',
    'sslserver',

    # Added apps for testing
    'auditlog',
    'django_extensions', # CAMU Activity 9 # run server using this code: python manage.py runserver_plus --cert-file cert.pem --key-file key.pem
    'rest_framework.authtoken',

    # Optional: For Logout
    'rest_framework_simplejwt.token_blacklist',

    # Google OAuth
    'social_django',
    'dj_rest_auth',
    'django.contrib.sites',  # Required for Django Allauth
    'allauth',
    'allauth.account',
    'allauth.socialaccount',
    'allauth.socialaccount.providers.google',

    # Filters
    'django_filters',
]

MIDDLEWARE = [
    'django.middleware.security.SecurityMiddleware',
    'django.contrib.sessions.middleware.SessionMiddleware',
    'django.middleware.common.CommonMiddleware',
    'django.middleware.csrf.CsrfViewMiddleware',
    'django.contrib.auth.middleware.AuthenticationMiddleware',
    'django.contrib.messages.middleware.MessageMiddleware',
    'django.middleware.clickjacking.XFrameOptionsMiddleware',
    'allauth.account.middleware.AccountMiddleware',
]

MIDDLEWARE.insert(0, 'corsheaders.middleware.CorsMiddleware')

ROOT_URLCONF = 'connectly_project.urls'

TEMPLATES = [
    {
        'BACKEND': 'django.template.backends.django.DjangoTemplates',
        'DIRS': [],
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

WSGI_APPLICATION = 'connectly_project.wsgi.application'


# Database
# https://docs.djangoproject.com/en/5.1/ref/settings/#databases

DATABASES = {
    'default': {
        'ENGINE': 'django.db.backends.sqlite3',
        'NAME': BASE_DIR / 'db.sqlite3',
    }
}


# Password validation
# https://docs.djangoproject.com/en/5.1/ref/settings/#auth-password-validators

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
# https://docs.djangoproject.com/en/5.1/topics/i18n/

LANGUAGE_CODE = 'en-us'

TIME_ZONE = 'UTC'

USE_I18N = True

USE_TZ = True


# Static files (CSS, JavaScript, Images)
# https://docs.djangoproject.com/en/5.1/howto/static-files/

STATIC_URL = 'static/'

# Default primary key field type
# https://docs.djangoproject.com/en/5.1/ref/settings/#default-auto-field

DEFAULT_AUTO_FIELD = 'django.db.models.BigAutoField'



# List of added commands

# Force HTTPS Redirect
SECURE_SSL_REDIRECT = True  
SESSION_COOKIE_SECURE = True  
CSRF_COOKIE_SECURE = True  
SECURE_HSTS_SECONDS = 31536000  # 1 year  
SECURE_HSTS_INCLUDE_SUBDOMAINS = True  
SECURE_HSTS_PRELOAD = True

PASSWORD_HASHERS = [
    'django.contrib.auth.hashers.Argon2PasswordHasher', # Argon2 for Hashing
    'django.contrib.auth.hashers.BCryptSHA256PasswordHasher',  # BCrypt for Salting # Removed this because of issues with Authentication
    'django.contrib.auth.hashers.PBKDF2PasswordHasher',
    'django.contrib.auth.hashers.PBKDF2SHA1PasswordHasher',
    'django.contrib.auth.hashers.BCryptPasswordHasher',
]

REST_FRAMEWORK = {
    'DEFAULT_AUTHENTICATION_CLASSES': (
        'rest_framework.authentication.SessionAuthentication',  # Enables login via API
        'rest_framework_simplejwt.authentication.JWTAuthentication',
        
    ),
    'DEFAULT_PERMISSION_CLASSES': (
        'rest_framework.permissions.IsAuthenticated',  # Secure all endpoints
    )
}

AUTHENTICATION_BACKENDS = (
    'django.contrib.auth.backends.ModelBackend',
    'social_core.backends.google.GoogleOAuth2',
)

# Control Token Expiry

SIMPLE_JWT = {
    'ACCESS_TOKEN_LIFETIME': timedelta(minutes=15),  # Access token expiry
    'REFRESH_TOKEN_LIFETIME': timedelta(minutes=15),  # Refresh token expiry
    'ROTATE_REFRESH_TOKENS': True,  # Rotate refresh tokens
    'BLACKLIST_AFTER_ROTATION': False,  # Blacklist the old refresh token after rotation
}

# Media configuration
MEDIA_URL = '/media/'
MEDIA_ROOT = BASE_DIR / 'media'

LOGIN_REDIRECT_URL = '/feed/'  # Redirect users to posts after login
LOGOUT_REDIRECT_URL = '/'  # Redirect users back to login after logout

# Google OAuth2 Configuration
SOCIAL_AUTH_GOOGLE_OAUTH2_KEY = os.getenv("GOOGLE_CLIENT_ID")
SOCIAL_AUTH_GOOGLE_OAUTH2_SECRET = os.getenv("GOOGLE_CLIENT_SECRET")
SOCIAL_AUTH_GOOGLE_OAUTH2_SCOPE = ['email', 'profile']
SOCIAL_AUTH_GOOGLE_OAUTH2_EXTRA_DATA = ['first_name', 'last_name']

# CSRF Settings
CSRF_COOKIE_NAME = "csrftoken"
CSRF_TRUSTED_ORIGINS = ["http://127.0.0.1:8000"]
SESSION_COOKIE_SECURE = False
CSRF_COOKIE_SECURE = False  # Change to True in production

# Simple JWT
SIMPLE_JWT['AUTH_TOKEN_CLASSES'] = ("rest_framework_simplejwt.tokens.AccessToken",)

SITE_ID = 1  # Required for Django Allauth

# Google OAuth2 Configuration
SOCIALACCOUNT_PROVIDERS = {
    "google": {
        "SCOPE": ["email", "profile"],
        "AUTH_PARAMS": {"access_type": "online"},
    }
}