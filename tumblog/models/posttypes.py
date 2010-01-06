from django.db import models
from tumblog.models import Post
from autofields.fields import AutoMarkdownTextField
from django.conf import settings
from sorl.thumbnail.fields import ImageWithThumbnailsField

class TextPost(Post):
    """ Text post model """
    body_raw        = models.TextField()
    body            = AutoMarkdownTextField(prepopulate_from='body_raw')

    class Meta:
        app_label   = 'tumblog'

class LinkPost(Post):
    """ Link post model """
    link            = models.URLField()
    description_raw = models.TextField()
    description     = AutoMarkdownTextField(prepopulate_from='description_raw')

    class Meta:
        app_label   = 'tumblog'

class QuotePost(Post):
    """ Quote post model """
    quote_raw       = models.TextField()
    quote           = AutoMarkdownTextField(prepopulate_from='quote_raw')
    citation_raw    = models.CharField(max_length=255)
    citation        = AutoMarkdownTextField(prepopulate_from='citation_raw')

    class Meta:
        app_label   = 'tumblog'

class PhotoPost(Post):
    """ Photo post model. This can contain multiple photos. """
    description_raw = models.TextField()
    description     = AutoMarkdownTextField(prepopulate_from='description_raw')

    class Meta:
        app_label   = 'tumblog'

class Photo(models.Model):
    """ Individual image model, used in photo posts. """
    caption_raw     = models.TextField()
    caption         = AutoMarkdownTextField(prepopulate_from='caption_raw')
    source_url      = models.URLField(blank=True, null=True)
    image           = ImageWithThumbnailsField(
                        upload_to='photos',
                        generate_on_save=True,
                        thumbnail={'size': (100,100), 'extension': 'png'},
                        extra_thumbnails={'preview': {'size': (400, 400), 'extension': 'png'}},
                      )
    post            = models.ForeignKey(PhotoPost, related_name='photos')

    class Meta:
        app_label   = 'tumblog'
