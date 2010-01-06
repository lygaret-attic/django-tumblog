from django.conf.urls.defaults import *
from tumblog.views.admin import *

urlpatterns = patterns('',
    (r'^(?P<blogslug>[-\w]+)/create/$', create, {}, 'tumblog.admin.create'),
)
