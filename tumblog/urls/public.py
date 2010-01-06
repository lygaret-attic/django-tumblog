from django.conf import settings
from django.conf.urls.defaults import *
from django.views.generic import list_detail, date_based

from tagging import views as tagging_list

from tumblog.models import Post
from tumblog.views.public import *

date_info = {
    'queryset': Post.published.all(),
    'date_field': 'pubtime',
    'slug_field': 'slug',
    'month_format': '%m',
    'template_name_field': 'template_name',
}

tag_info = {
    'queryset_or_model': Post.published.all(),
    'paginate_by': settings.PAGINATION_COUNT,
}

urlpatterns = patterns('',
    (r'^(?P<blogslug>[-\w]+)/(?P<year>\d{4})/(?P<month>\d{1,2})/(?P<day>\d{1,2})/$', archive_day, {}, 'tumblog.day'),
    (r'^(?P<blogslug>[-\w]+)/(?P<year>\d{4})/(?P<month>\d{1,2})/(?P<day>\d{1,2})/p/(?P<page>\d+)/$', archive_day, {}, 'tumblog.day.page'),
    (r'^(?P<blogslug>[-\w]+)/(?P<year>\d{4})/(?P<month>\d{1,2})/(?P<day>\d{1,2})/(?P<slug>[-\w]+)/$', archive_detail, {}, 'tumblog.post'),
    (r'^(?P<blogslug>[-\w]+)/(?P<year>\d{4})/(?P<month>\d{1,2})/$', archive_month, {}, 'tumblog.month'),
    (r'^(?P<blogslug>[-\w]+)/(?P<year>\d{4})/(?P<month>\d{1,2})/p/(?P<page>\d+)/$', archive_month, {}, 'tumblog.month.page'),
    (r'^(?P<blogslug>[-\w]+)/(?P<year>\d{4})/$', archive_year),
    (r'^(?P<blogslug>[-\w]+)/(?P<year>\d{4})/p/(?P<page>\d+)/$', archive_year, {}, 'tumblog.year.page'),
    (r'^(?P<blogslug>[-\w]+)/(?P<tag>[-\w]+)/$', archive_tagged, {}, 'tumblog.tag'),
    (r'^(?P<blogslug>[-\w]+)/(?P<tag>[-\w]+)/p/(?P<page>\d+)/$', archive_tagged, {}, 'tumblog.tag.page'),
    (r'^(?P<blogslug>[-\w]+)/$', archive_index, {}, 'tumblog.index'),
    (r'^(?P<blogslug>[-\w]+)/p/(?P<page>\d+)/$', archive_index, {}, 'tumblog.index.page'),
)
