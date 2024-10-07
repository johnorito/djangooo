from django.apps import apps
from django.core import checks
from django.test import SimpleTestCase, override_settings


class SettingsDeprecationCheckTests(SimpleTestCase):
    @override_settings(TRANSACTIONS_MANAGED=True)
    def test_deprecated_settings_variables(self):
        all_issues = checks.run_checks(app_configs=apps.get_app_configs())

        self.assertEqual(len(all_issues), 1)

        first_warning_message = all_issues[0]
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
