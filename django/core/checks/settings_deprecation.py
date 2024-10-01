from django.conf import settings
from django.core import checks


def deprecated_settings_variables(*args, **kwargs):
    """
    This check warns users who still use deprecated settings variables.
    """

    deprecated_settings_list = (
        # Django 1.4
        "TRANSACTIONS_MANAGED",
        # Django 1.5
        "SITE_ID",
        "AUTH_PROFILE_MODULE",
        "CSRF_COOKIE_PATH",
        # Django 1.6
        "DATABASE_ENGINE",
        # Django 1.7
        "SOUTH_DATABASE_ADAPTER",
        "SOUTH_DATABASE_ADAPTERS",
        "SOUTH_AUTO_FREEZE_APP",
        "SOUTH_TESTS_MIGRATE",
        "SOUTH_LOGGING_ON",
        "SOUTH_LOGGING_FILE",
        "SOUTH_MIGRATION_MODULES",
        "SOUTH_USE_PYC",
        # Django 1.8
        "TEMPLATE_DIRS",
        "TEMPLATE_CONTEXT_PROCESSORS",
        "TEMPLATE_LOADERS",
        "TEMPLATE_DEBUG",
        "ALLOWED_INCLUDE_ROOTS",
        "USE_ETAGS",
        # Django 1.9
        "FILE_UPLOAD_HANDLERS",
        # Django 1.10
        "SECURE_PROXY_SSL_HEADER",
        # Django 2.0
        "DEFAULT_CONTENT_TYPE",
        "FILE_CHARSET",
        # Django 2.1
        "SECURE_BROWSER_XSS_FILTER",
        # Django 3.0
        "PASSWORD_RESET_TIMEOUT_DAYS",
        # Django 3.1
        "DEFAULT_FILE_STORAGE",
        # Django 4.0
        "USE_L10N",
        "DEFAULT_HASHING_ALGORITHM",
        # Django 4.1
        "PASSWORD_RESET_TIMEOUT_DAYS",
        "DEFAULT_STORAGE_CLASS",
        # Django 4.2
        "MIDDLEWARE_CLASSES",
        "FILE_UPLOAD_HANDLERS",
        "ADMINS",
        "MANAGERS",
        # Django 5.0
        "USE_DEPRECATED_PYTZ",
        "DATABASE_OPTIONS",
        "DEFAULT_FILE_STORAGE",
        "STATICFILES_STORAGE",
    )

    warning_list = []
    for attribute, _ in vars(settings).items():
        if attribute in deprecated_settings_list:
            warning_list.append(
                checks.Warning(
                    f'You still use {attribute!r} in your Django settings file. This attribute is deprecated.',
                    hint="Please refer to the documentation and remove/replace this attribute.",
                    id="settings.W001",
                )
            )

    return warning_list
