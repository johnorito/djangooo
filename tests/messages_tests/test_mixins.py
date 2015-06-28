from django.core.urlresolvers import reverse
from django.test import SimpleTestCase, override_settings

from .urls import ContactFormViewWithMsg


@override_settings(
    ROOT_URLCONF='messages_tests.urls',
    MESSAGE_STORAGE='django.contrib.messages.storage.cookie.CookieStorage',
)
class SuccessMessageMixinTests(SimpleTestCase):

    def test_set_messages_success(self):
        author = {'name': 'John Doe',
                  'slug': 'success-msg'}
        add_url = reverse('add_success_msg')
        req = self.client.post(add_url, author)
        self.assertIn(ContactFormViewWithMsg.success_message % author,
                      req.cookies['messages'].value)
