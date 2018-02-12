from django.core import management, serializers
from django.db import connection
from django.test import TestCase

from .models import FKDataNaturalKey, Foo, NaturalKeyAnchor
from .tests import register_tests


class NaturalKeySerializerTests(TestCase):
    pass


def natural_key_serializer_test(self, format):
    # Create all the objects defined in the test data
    with connection.constraint_checks_disabled():
        objects = [
            NaturalKeyAnchor.objects.create(id=1100, data="Natural Key Anghor"),
            FKDataNaturalKey.objects.create(id=1101, data_id=1100),
            FKDataNaturalKey.objects.create(id=1102, data_id=None),
        ]
    # Serialize the test database
    serialized_data = serializers.serialize(format, objects, indent=2, use_natural_foreign_keys=True)

    for obj in serializers.deserialize(format, serialized_data):
        obj.save()

    # Assert that the deserialized data is the same
    # as the original source
    for obj in objects:
        instance = obj.__class__.objects.get(id=obj.pk)
        self.assertEqual(
            obj.data, instance.data,
            "Objects with PK=%d not equal; expected '%s' (%s), got '%s' (%s)" % (
                obj.pk, obj.data, type(obj.data), instance, type(instance.data),
            )
        )


def natural_key_test(self, format):
    book1 = {
        'data': '978-1590597255',
        'title': 'The Definitive Guide to Django: Web Development Done Right',
    }
    book2 = {'data': '978-1590599969', 'title': 'Practical Django Projects'}

    # Create the books.
    adrian = NaturalKeyAnchor.objects.create(**book1)
    james = NaturalKeyAnchor.objects.create(**book2)

    # Serialize the books.
    string_data = serializers.serialize(
        format, NaturalKeyAnchor.objects.all(), indent=2,
        use_natural_foreign_keys=True, use_natural_primary_keys=True,
    )

    # Delete one book (to prove that the natural key generation will only
    # restore the primary keys of books found in the database via the
    # get_natural_key manager method).
    james.delete()

    # Deserialize and test.
    books = list(serializers.deserialize(format, string_data))
    self.assertEqual(len(books), 2)
    self.assertEqual(books[0].object.title, book1['title'])
    self.assertEqual(books[0].object.pk, adrian.pk)
    self.assertEqual(books[1].object.title, book2['title'])
    self.assertIsNone(books[1].object.pk)


class NaturalKeyWhenPkHasDefaultValueTestCase(TestCase):
    """
    Verify that deserializer does not ignore natural keys when primary key
    has a default value (ticket `28385`).

    Test to prove that deserializer gets `pk` via `natural key` and
    updates object instead of create new one.
    """

    def test_load_data_natural_key(self):
        """
        Test natural key behavior during loading fixture data.
        """
        self.assertEqual(Foo.objects.all().count(), 0)

        management.call_command("loaddata", "fixture.json", verbosity=0)
        self.assertEqual(Foo.objects.all().count(), 1)

        first_import_pk = Foo.objects.first().pk

        management.call_command("loaddata", "fixture.json", verbosity=0)
        self.assertEqual(Foo.objects.all().count(), 1)

        second_import_pk = Foo.objects.first().pk

        self.assertEqual(first_import_pk, second_import_pk)


# Dynamically register tests for each serializer
register_tests(NaturalKeySerializerTests, 'test_%s_natural_key_serializer', natural_key_serializer_test)
register_tests(NaturalKeySerializerTests, 'test_%s_serializer_natural_keys', natural_key_test)
