from django.core import checks
from django.core.checks.settings_deprecation import check_deprecated_settings
from django.test import SimpleTestCase, override_settings


class SettingsDeprecationCheckTests(SimpleTestCase):
    @override_settings(TRANSACTIONS_MANAGED=True)
    def test_deprecated_settings_variables(self):
        warning_list = check_deprecated_settings()

        self.assertEqual(len(warning_list), 1)

        first_warning_message = warning_list[0]
        self.assertEqual(
            first_warning_message,
            checks.Warning(
                "You still use 'TRANSACTIONS_MANAGED' in your Django settings "
                "file. This attribute is deprecated.",
                hint="Please refer to the documentation and remove/replace "
                "this attribute.",
                id="settings.W001",
            ),
        )
