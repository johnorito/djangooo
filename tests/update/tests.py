from django.core.exceptions import FieldError
from django.db.models import Count, F, Max, OuterRef, Subquery
from django.db.models.functions import Concat, Lower
from django.test import TestCase

from .models import (
    A, B, Bar, Company, D, DataPoint, Employee, Foo, RelatedPoint
)


class SimpleTest(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.a1 = A.objects.create()
        cls.a2 = A.objects.create()
        for x in range(20):
            B.objects.create(a=cls.a1)
            D.objects.create(a=cls.a1)

    def test_nonempty_update(self):
        """
        Update changes the right number of rows for a nonempty queryset
        """
        num_updated = self.a1.b_set.update(y=100)
        self.assertEqual(num_updated, 20)
        cnt = B.objects.filter(y=100).count()
        self.assertEqual(cnt, 20)

    def test_empty_update(self):
        """
        Update changes the right number of rows for an empty queryset
        """
        num_updated = self.a2.b_set.update(y=100)
        self.assertEqual(num_updated, 0)
        cnt = B.objects.filter(y=100).count()
        self.assertEqual(cnt, 0)

    def test_nonempty_update_with_inheritance(self):
        """
        Update changes the right number of rows for an empty queryset
        when the update affects only a base table
        """
        num_updated = self.a1.d_set.update(y=100)
        self.assertEqual(num_updated, 20)
        cnt = D.objects.filter(y=100).count()
        self.assertEqual(cnt, 20)

    def test_empty_update_with_inheritance(self):
        """
        Update changes the right number of rows for an empty queryset
        when the update affects only a base table
        """
        num_updated = self.a2.d_set.update(y=100)
        self.assertEqual(num_updated, 0)
        cnt = D.objects.filter(y=100).count()
        self.assertEqual(cnt, 0)

    def test_foreign_key_update_with_id(self):
        """
        Update works using <field>_id for foreign keys
        """
        num_updated = self.a1.d_set.update(a_id=self.a2)
        self.assertEqual(num_updated, 20)
        self.assertEqual(self.a2.d_set.count(), 20)


class AdvancedTests(TestCase):

    @classmethod
    def setUpTestData(cls):
        cls.d0 = DataPoint.objects.create(name="d0", value="apple")
        cls.d2 = DataPoint.objects.create(name="d2", value="banana")
        cls.d3 = DataPoint.objects.create(name="d3", value="banana")
        cls.r1 = RelatedPoint.objects.create(name="r1", data=cls.d3)

    def test_update(self):
        """
        Objects are updated by first filtering the candidates into a queryset
        and then calling the update() method. It executes immediately and
        returns nothing.
        """
        resp = DataPoint.objects.filter(value="apple").update(name="d1")
        self.assertEqual(resp, 1)
        resp = DataPoint.objects.filter(value="apple")
        self.assertEqual(list(resp), [self.d0])

    def test_update_multiple_objects(self):
        """
        We can update multiple objects at once.
        """
        resp = DataPoint.objects.filter(value='banana').update(value='pineapple')
        self.assertEqual(resp, 2)
        self.assertEqual(DataPoint.objects.get(name="d2").value, 'pineapple')

    def test_update_fk(self):
        """
        Foreign key fields can also be updated, although you can only update
        the object referred to, not anything inside the related object.
        """
        resp = RelatedPoint.objects.filter(name="r1").update(data=self.d0)
        self.assertEqual(resp, 1)
        resp = RelatedPoint.objects.filter(data__name="d0")
        self.assertEqual(list(resp), [self.r1])

    def test_update_multiple_fields(self):
        """
        Multiple fields can be updated at once
        """
        resp = DataPoint.objects.filter(value="apple").update(
            value="fruit", another_value="peach")
        self.assertEqual(resp, 1)
        d = DataPoint.objects.get(name="d0")
        self.assertEqual(d.value, 'fruit')
        self.assertEqual(d.another_value, 'peach')

    def test_update_all(self):
        """
        In the rare case you want to update every instance of a model, update()
        is also a manager method.
        """
        self.assertEqual(DataPoint.objects.update(value='thing'), 3)
        resp = DataPoint.objects.values('value').distinct()
        self.assertEqual(list(resp), [{'value': 'thing'}])

    def test_update_slice_fail(self):
        """
        We do not support update on already sliced query sets.
        """
        method = DataPoint.objects.all()[:2].update
        msg = 'Cannot update a query once a slice has been taken.'
        with self.assertRaisesMessage(AssertionError, msg):
            method(another_value='another thing')

    def test_update_respects_to_field(self):
        """
        Update of an FK field which specifies a to_field works.
        """
        a_foo = Foo.objects.create(target='aaa')
        b_foo = Foo.objects.create(target='bbb')
        bar = Bar.objects.create(foo=a_foo)
        self.assertEqual(bar.foo_id, a_foo.target)
        bar_qs = Bar.objects.filter(pk=bar.pk)
        self.assertEqual(bar_qs[0].foo_id, a_foo.target)
        bar_qs.update(foo=b_foo)
        self.assertEqual(bar_qs[0].foo_id, b_foo.target)

    def test_update_m2m_field(self):
        msg = (
            'Cannot update model field '
            '<django.db.models.fields.related.ManyToManyField: m2m_foo> '
            '(only non-relations and foreign keys permitted).'
        )
        with self.assertRaisesMessage(FieldError, msg):
            Bar.objects.update(m2m_foo='whatever')

    def test_update_annotated_queryset(self):
        """
        Update of a queryset that's been annotated.
        """
        # Trivial annotated update
        qs = DataPoint.objects.annotate(alias=F('value'))
        self.assertEqual(qs.update(another_value='foo'), 3)
        # Update where annotation is used for filtering
        qs = DataPoint.objects.annotate(alias=F('value')).filter(alias='apple')
        self.assertEqual(qs.update(another_value='foo'), 1)
        # Update where annotation is used in update parameters
        qs = DataPoint.objects.annotate(alias=F('value'))
        self.assertEqual(qs.update(another_value=F('alias')), 3)
        # Update where aggregation annotation is used in update parameters
        qs = DataPoint.objects.annotate(max=Max('value'))
        msg = (
            'Aggregate functions are not allowed in this query '
            '(another_value=Max(Col(update_datapoint, update.DataPoint.value))).'
        )
        with self.assertRaisesMessage(FieldError, msg):
            qs.update(another_value=F('max'))

    def test_update_annotated_multi_table_queryset(self):
        """
        Update of a queryset that's been annotated and involves multiple tables.
        """
        # Trivial annotated update
        qs = DataPoint.objects.annotate(related_count=Count('relatedpoint'))
        self.assertEqual(qs.update(value='Foo'), 3)
        # Update where annotation is used for filtering
        qs = DataPoint.objects.annotate(related_count=Count('relatedpoint'))
        self.assertEqual(qs.filter(related_count=1).update(value='Foo'), 1)
        # Update where aggregation annotation is used in update parameters
        qs = RelatedPoint.objects.annotate(max=Max('data__value'))
        msg = 'Joined field references are not permitted in this query'
        with self.assertRaisesMessage(FieldError, msg):
            qs.update(name=F('max'))

    def test_update_with_joined_field_annotation(self):
        msg = 'Joined field references are not permitted in this query'
        for annotation in (
            F('data__name'),
            Lower('data__name'),
            Concat('data__name', 'data__value'),
        ):
            with self.subTest(annotation=annotation):
                with self.assertRaisesMessage(FieldError, msg):
                    RelatedPoint.objects.annotate(new_name=annotation).update(name=F('new_name'))

    def test_update_with_join_in_outerref(self):

        e1 = Employee.objects.create(
            firstname='A_first',
            lastname='A_last',
            salary=100
        )
        e2 = Employee.objects.create(
            firstname='B_first',
            lastname='B_last',
            salary=200
        )
        e3 = Employee.objects.create(
            firstname='C_first',
            lastname='C_last',
            salary=200
        )
        c1 = Company.objects.create(
            name='ABC Corp',
            num_employees=10,
            num_chairs=20,
            ceo=e3,
        )
        
        inner = Employee.objects.filter(
            salary=OuterRef('ceo__salary')
        ).order_by('id')
        outer = Company.objects.filter(
            num_employees__gt=2
        ).update(num_chairs=Subquery(inner.values('salary')[:1]))

        self.assertEqual(
            list(Company.objects.filter(id=c1.id).values_list('num_chairs', flat=True)),
            [200]
        )
