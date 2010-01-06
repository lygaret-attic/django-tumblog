from django.db import models
from utils.fields import AutoMarkdownTextField
from tagging.models import Tag
from datetime import datetime

class Blog(models.Model):
    """ Tumblog Model """
    slug            = models.SlugField()
    title           = models.CharField(max_length = 200)
    description_raw = models.TextField()
    description     = AutoMarkdownTextField(prepopulate_from = "description_raw")

    class Meta:
        app_label   = 'tumblog'

    def __unicode__(self):
        return "Blog %s" % self.title

    @property
    def tags(self):
        tags = Tag.objects.usage_for_queryset(self.post_set.all(), counts = True)
        tags.sort(lambda x, y: cmp(y.count, x.count))
        return tags

    @property
    def archive_months(self):
        return self.posts.dates('pubtime', 'month', order="DESC")

    @property
    def posts(self):
        return self.post_set.filter(pubtime__lte = datetime.now())

