from django.db import models
from pydelicious import DeliciousAPI, ISO_8601_DATETIME
from time import gmtime as epoch_to_utc
from calendar import timegm as utc_to_epoch
from time import strptime, strftime
from datetime import datetime

from tumblog.models import *

class DeliciousUpdater(models.Model):
    blog = models.ForeignKey(Blog)
    username = models.CharField(max_length=255)
    password = models.CharField(max_length=255)

    tags = models.CharField(max_length=500)
    last_known_update_utc = models.IntegerField(default = 0)

    def _last_update_timestring(self):
        t = epoch_to_utc(self.last_known_update_utc)
        return strftime(ISO_8601_DATETIME, t)

    def _parse_time(self, timestr):
        t = strptime(timestr, ISO_8601_DATETIME)
        return utc_to_epoch(t)

    def _parse_datetime(self, timestr):
        t = strptime(timestr, ISO_8601_DATETIME)
        return datetime(*(t[0:6]))

    def update_links(self):

        api = DeliciousAPI(self.username, self.password)

        # get the latest update according to delicious
        latest_update_utc = api.posts_update()
        latest_update_utc = utc_to_epoch(latest_update_utc['update']['time'])

        if self.last_known_update_utc < latest_update_utc:
            posts = api.posts_all(fromdt=self._last_update_timestring())

            for p in posts['posts']:
                link = LinkPost()
                link.blog_id = self.blog_id
                link.title = p['description']
                link.link = p['href']
                link.description_raw = p['extended']
                link.publish(publish_time = self._parse_datetime(p['time']))

                link.tags = p['tag']
                link.save()

            self.last_known_update_utc = self._parse_time(posts['update']) + 1
            self.save()
