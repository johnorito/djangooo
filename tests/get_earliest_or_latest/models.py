from django.db import models


class Article(models.Model):
    headline = models.CharField(max_length=100)
    pub_date = models.DateField()
    expire_date = models.DateField()

    class Meta:
        get_latest_by = 'pub_date'


class Person(models.Model):
    name = models.CharField(max_length=30)
    birthday = models.DateField()
    # Note that this model doesn't have "get_latest_by" set.


# Ticket #23555

class IndexErrorQuerySet(models.QuerySet):
    """
    Raises IndexError on __iter__() call.

    This emulates the case when some internal code raises unexpected IndexError
    that should not be considered as a signal of the element absense.
    """
    def __iter__(self):
        raise IndexError


class IndexErrorArticle(Article):
    objects = IndexErrorQuerySet.as_manager()
