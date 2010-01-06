from datetime import datetime
from django.db import models
from tagging.models import TaggedItem

class PublishedPostManager(models.Manager):
    """
    Only show published posts. This is the default manager for posts.
    """
    def get_query_set(self):
        return super(PublishedPostManager, self).get_query_set().filter(pubtime__lte = datetime.now())

    def by_date(self, year, month=None, day=None):
        """ Return all posts in the given time period """
        if month is None:
            return self.filter( pubtime__lt = datetime(year + 1, 1, 1), \
                                pubtime__gte = datetime(year, 1, 1) )
        elif day is None:
            if (month == 12):
                next_year = year + 1
                next_month = 1
            else:
                next_year = year
                next_month = month + 1

            return self.filter( pubtime__lt = datetime(next_year, next_month, 1), \
                                pubtime__gte = datetime(year, month, 1) )
        else:
            return self.filter( pubtime__lte = datetime(year, month, day, 23, 59), \
                                pubtime__gte = datetime(year, month, day, 0, 0) )

    def by_tag(self, tagname):
        """ Return all posts tagged with any of the tags in the taglist """
        return TaggedItem.objects.get_by_model(self, tagname)
