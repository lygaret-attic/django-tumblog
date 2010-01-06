from django.db import models
from django.db.models import permalink
from django.contrib.auth.models import User
from django.contrib.contenttypes.models import ContentType

from datetime import datetime
from tagging.models import Tag
from tagging.fields import TagField

from autofields.fields import AutoSlugField
from tumblog.managers import PublishedPostManager
from tumblog.models import Blog

class Post(models.Model):
    """ Tumblog Post Model """
    title           = models.CharField(max_length = 200)
    author          = models.ForeignKey(User, blank=True, null=True)
    slug            = AutoSlugField(prepopulate_from = 'title', unique = True)
    tags            = TagField()
    pubtime         = models.DateTimeField(null = True, blank = True)

    blog            = models.ForeignKey(Blog)

    modtime         = models.DateTimeField(auto_now = True)
    post_type       = models.ForeignKey(ContentType)

    published       = PublishedPostManager()
    objects         = models.Manager()

    class Meta:
        app_label   = 'tumblog'
        ordering    = ('-pubtime',)

    def __unicode__(self):
        return "%s: (published: %s)" % (self.title, self.pubtime.date if self.pubtime else "not published")

    def save(self, *args, **kwargs):
        if not self.pk:
            self.post_type = ContentType.objects.get_for_model(type(self))
        import pdb; pdb.set_trace()
        super(Post, self).save(*args, **kwargs)

    def get_tags(self):
        return Tag.objects.get_for_object(self)

    @property
    def inner_post(self):
        return self.post_type.get_object_for_this_type(id = self.id)

    @property
    def template_name(self):
        return "tumblog/post_%s.html" % self.post_type.model

    def publish(self, publish_time = None):
        """
        Publish is basically a wrapper for save, which adjusts the
        recorded publish time on the post. If the publish_time parameter
        is given, then the post will be "published" after that time. If
        publish_time parameter is _not_ given, the publish_time is now,
        and the item is immediately published.
        """
        if publish_time is None:
            publish_time = datetime.now()
        self.pubtime = publish_time
        self.save()

