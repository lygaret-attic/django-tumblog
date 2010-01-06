"""Library to access del.icio.us data via Python.

An introduction to the project is given in the README.
pydelicious is released under the BSD license. See license.txt for details
and the copyright holders.

THIS SOFTWARE IS PROVIDED BY THE COPYRIGHT HOLDERS AND CONTRIBUTORS "AS IS" AND
ANY EXPRESS OR IMPLIED WARRANTIES, INCLUDING, BUT NOT LIMITED TO, THE IMPLIED
WARRANTIES OF MERCHANTABILITY AND FITNESS FOR A PARTICULAR PURPOSE ARE
DISCLAIMED. IN NO EVENT SHALL THE COPYRIGHT OWNER OR CONTRIBUTORS BE LIABLE FOR
ANY DIRECT, INDIRECT, INCIDENTAL, SPECIAL, EXEMPLARY, OR CONSEQUENTIAL DAMAGES
(INCLUDING, BUT NOT LIMITED TO, PROCUREMENT OF SUBSTITUTE GOODS OR SERVICES;
LOSS OF USE, DATA, OR PROFITS; OR BUSINESS INTERRUPTION) HOWEVER CAUSED AND ON
ANY THEORY OF LIABILITY, WHETHER IN CONTRACT, STRICT LIABILITY, OR TORT
(INCLUDING NEGLIGENCE OR OTHERWISE) ARISING IN ANY WAY OUT OF THE USE OF THIS
SOFTWARE, EVEN IF ADVISED OF THE POSSIBILITY OF SUCH DAMAGE.

TODO:
 - distribute license, readme docs via setup.py?
 - automatic release build?
"""
import sys
import os
import time
import datetime
import locale
import httplib
import urllib2
from urllib import urlencode, quote_plus
from StringIO import StringIO
from pprint import pformat

v = sys.version_info
if v[0] >= 2 and v[1] >= 5:
    from hashlib import md5
else:
    from md5 import md5

try:
    from elementtree.ElementTree import parse as parse_xml
except ImportError:
    # Python 2.5 and higher
    from xml.etree.ElementTree import parse as parse_xml

try:
    import feedparser
except ImportError:
    print >>sys.stderr, \
        "Feedparser not available, no RSS parsing."
    feedparser = None


### Static config

__version__ = '0.5.3'
__author__ = 'Frank Timmermann <regenkind_at_gmx_dot_de>'
    # GP: does not respond to emails
__contributors__ = [
    'Greg Pinero',
    'Berend van Berkum <berend+pydelicious@dotmpe.com>']
__url__ = 'http://code.google.com/p/pydelicious/'
# Old URL: 'http://deliciouspython.python-hosting.com/'
__author_email__ = ""
__docformat__ = "restructuredtext en"
__description__ = "pydelicious.py allows you to access the web service of " \
    "del.icio.us via it's API through Python."
__long_description__ = "The goal is to design an easy to use and fully " \
    "functional Python interface to del.icio.us."

DLCS_OK_MESSAGES = ('done', 'ok')
"Known text values of positive del.icio.us <result/> answers"
DLCS_WAIT_TIME = 4
"Time to wait between API requests"
DLCS_REQUEST_TIMEOUT = 444
"Seconds before socket triggers timeout"
#DLCS_API_REALM = 'del.icio.us API'
DLCS_API_HOST = 'api.del.icio.us'
DLCS_API_PATH = 'v1'
DLCS_API = "https://%s/%s" % (DLCS_API_HOST, DLCS_API_PATH)
DLCS_RSS = 'http://del.icio.us/rss/'
DLCS_FEEDS = 'http://feeds.delicious.com/v2/'

PREFERRED_ENCODING = locale.getpreferredencoding()
# XXX: might need to check sys.platform/encoding combinations here, ie
#if sys.platform == 'darwin' || PREFERRED_ENCODING == 'macroman:
#   PREFERRED_ENCODING = 'utf-8'
if not PREFERRED_ENCODING:
    PREFERRED_ENCODING = 'iso-8859-1'

ISO_8601_DATETIME = '%Y-%m-%dT%H:%M:%SZ'

USER_AGENT = 'pydelicious/%s %s' % (__version__, __url__)

DEBUG = 0
if 'DLCS_DEBUG' in os.environ:
    DEBUG = int(os.environ['DLCS_DEBUG'])
    if DEBUG:
        print >>sys.stderr, \
            "Set DEBUG to %i from DLCS_DEBUG env." % DEBUG

HTTP_PROXY = None
if 'HTTP_PROXY' in os.environ:
    HTTP_PROXY = os.environ['HTTP_PROXY']
    if DEBUG:
        print >>sys.stderr, \
            "Set HTTP_PROXY to %i from env." % HTTP_PROXY

### Timeoutsocket hack taken from FeedParser.py

# timeoutsocket allows feedparser to time out rather than hang forever on ultra-
# slow servers. Python 2.3 now has this functionality available in the standard
# socket library, so under 2.3 you don't need to install anything.  But you
# probably should anyway, because the socket module is buggy and timeoutsocket
# is better.
try:
    import timeoutsocket # http://www.timo-tasi.org/python/timeoutsocket.py
    timeoutsocket.setDefaultSocketTimeout(DLCS_REQUEST_TIMEOUT)
except ImportError:
    import socket
    if hasattr(socket, 'setdefaulttimeout'):
        socket.setdefaulttimeout(DLCS_REQUEST_TIMEOUT)
if DEBUG: print >>sys.stderr, \
    "Set socket timeout to %s seconds" % DLCS_REQUEST_TIMEOUT


### Utility classes

class _Waiter:
    """Waiter makes sure a certain amount of time passes between
    successive calls of `Waiter()`.

    Some attributes:
    :last: time of last call
    :wait: the minimum time needed between calls
    :waited: the number of calls throttled

    pydelicious.Waiter is an instance created when the module is loaded.
    """
    def __init__(self, wait):
        self.wait = wait
        self.waited = 0
        self.lastcall = 0;

    def __call__(self):
        tt = time.time()
        wait = self.wait

        timeago = tt - self.lastcall

        if timeago < wait:
            wait = wait - timeago
            if DEBUG>0: print >>sys.stderr, "Waiting %s seconds." % wait
            time.sleep(wait)
            self.waited += 1
            self.lastcall = tt + wait
        else:
            self.lastcall = tt

Waiter = _Waiter(DLCS_WAIT_TIME)


class PyDeliciousException(Exception):
    """Standard pydelicious error"""
class PyDeliciousThrottled(Exception): pass
class PyDeliciousUnauthorized(Exception): pass

class DeliciousError(Exception):
    """Raised when the server responds with a negative answer"""

    @staticmethod
    def raiseFor(error_string, path, **params):
        if error_string == 'item already exists':
            raise DeliciousItemExistsError, params['url']
        else:
            raise DeliciousError, "%s, while calling <%s?%s>" % (error_string,
                    path, urlencode(params))

class DeliciousItemExistsError(DeliciousError):
    """Raised then adding an already existing post."""


class HTTPErrorHandler(urllib2.HTTPDefaultErrorHandler):

    def http_error_401(self, req, fp, code, msg, headers):
        raise PyDeliciousUnauthorized, "Check credentials."

    def http_error_503(self, req, fp, code, msg, headers):
        # Retry-After?
        errmsg = "Try again later."
        if 'Retry-After' in headers:
            errmsg = "You may try again after %s" % headers['Retry-After']
        raise PyDeliciousThrottled, errmsg


### Utility functions

def dict0(d):
    "Removes empty string values from dictionary"
    return dict([(k,v) for k,v in d.items()
            if v=='' and isinstance(v, basestring)])


def delicious_datetime(str):
    """Parse a ISO 8601 formatted string to a Python datetime ...
    """
    return datetime.datetime(*time.strptime(str, ISO_8601_DATETIME)[0:6])


def http_request(url, user_agent=USER_AGENT, retry=4, opener=None):
    """Retrieve the contents referenced by the URL using urllib2.

    Retries up to four times (default) on exceptions.
    """
    request = urllib2.Request(url, headers={'User-Agent':user_agent})

    if not opener:
        opener = urllib2.build_opener()

    # Remember last error
    e = None

    # Repeat request on time-out errors
    tries = retry;
    while tries:
        try:
            return opener.open(request)

        except urllib2.HTTPError, e:
            # reraise unexpected protocol errors as PyDeliciousException
            raise PyDeliciousException, "%s" % e

        except urllib2.URLError, e:
            # xxx: Ugly check for time-out errors
            #if len(e)>0 and 'timed out' in arg[0]:
            print >> sys.stderr, "%s, %s tries left." % (e, tries)
            Waiter()
            tries = tries - 1
            #else:
            #	tries = None

    # Give up
    raise PyDeliciousException, \
            "Unable to retrieve data at '%s', %s" % (url, e)


def build_api_opener(host, user, passwd, extra_handlers=() ):
    """
    Build a urllib2 style opener with HTTP Basic authorization for one host
    and additional error handling. If HTTP_PROXY is set a proxyhandler is also
    added.
    """

    global DEBUG

    if DEBUG: httplib.HTTPConnection.debuglevel = 1

    password_manager = urllib2.HTTPPasswordMgrWithDefaultRealm()
    password_manager.add_password(None, host, user, passwd)
    auth_handler = urllib2.HTTPBasicAuthHandler(password_manager)

    extra_handlers += ( HTTPErrorHandler(), )
    if HTTP_PROXY:
        extra_handlers += ( urllib2.ProxyHandler( {'http': HTTP_PROXY} ), )

    return urllib2.build_opener(auth_handler, *extra_handlers)


def dlcs_api_opener(user, passwd):
    "Build an opener for DLCS_API_HOST, see build_api_opener()"

    return build_api_opener(DLCS_API_HOST, user, passwd)


def dlcs_api_request(path, params='', user='', passwd='', throttle=True,
        opener=None):
    """Retrieve/query a path within the del.icio.us API.

    This implements a minimum interval between calls to avoid
    throttling. [#]_ Use param 'throttle' to turn this behaviour off.

    .. [#] http://del.icio.us/help/api/
    """
    if throttle:
        Waiter()

    if params:
        url = "%s/%s?%s" % (DLCS_API, path, urlencode(params))
    else:
        url = "%s/%s" % (DLCS_API, path)

    if DEBUG: print >>sys.stderr, \
            "dlcs_api_request: %s" % url

    if not opener:
        opener = dlcs_api_opener(user, passwd)

    fl = http_request(url, opener=opener)

    if DEBUG>2: print >>sys.stderr, \
            pformat(fl.info().headers)

    return fl


def dlcs_encode_params(params, usercodec=PREFERRED_ENCODING):
    """Turn all param values (int, list, bool) into utf8 encoded strings.
    """

    if params:
        for key in params.keys():
            if isinstance(params[key], bool):
                if params[key]:
                    params[key] = 'yes'
                else:
                    params[key] = 'no'

            elif isinstance(params[key], int):
                params[key] = str(params[key])

            elif not params[key]:
                # strip/ignore empties other than False or 0
                del params[key]
                continue

            elif isinstance(params[key], list):
                params[key] = " ".join(params[key])

            elif not isinstance(params[key], unicode):
                params[key] = params[key].decode(usercodec)

            assert isinstance(params[key], basestring)

        params = dict([ (k, v.encode('utf8'))
                for k, v in params.items() if v])

    return params


def dlcs_parse_xml(data, split_tags=False):
    """Parse any del.icio.us XML document and return Python data structure.

    Recognizes all XML document formats as returned by the version 1 API and
    translates to a JSON-like data structure (dicts 'n lists).

    Returned instance is always a dictionary. Examples::

     {'posts': [{'url':'...','hash':'...',},],}
     {'tags':['tag1', 'tag2',]}
     {'dates': [{'count':'...','date':'...'},], 'tag':'', 'user':'...'}
     {'result':(True, "done")}
     # etcetera.
    """
    # TODO: split_tags is not implemented

    if DEBUG>3: print >>sys.stderr, "dlcs_parse_xml: parsing from ", data

    if not hasattr(data, 'read'):
        data = StringIO(data)

    doc = parse_xml(data)
    root = doc.getroot()
    fmt = root.tag

    # Split up into three cases: Data, Result or Update
    if fmt in ('tags', 'posts', 'dates', 'bundles'):

        # Data: expect a list of data elements, 'resources'.
        # Use `fmt` (without last 's') to find data elements, elements
        # don't have contents, attributes contain all the data we need:
        # append to list
        elist = [el.attrib for el in doc.findall(fmt[:-1])]

        # Return list in dict, use tagname of rootnode as keyname.
        data = {fmt: elist}

        # Root element might have attributes too, append dict.
        data.update(root.attrib)

        return data

    elif fmt == 'result':

        # Result: answer to operations
        if root.attrib.has_key('code'):
            msg = root.attrib['code']
        else:
            msg = root.text

        # XXX: Return {'result':(True, msg)} for /known/ O.K. messages,
        # use (False, msg) otherwise. Move this to DeliciousAPI?
        v = msg in DLCS_OK_MESSAGES
        return {fmt: (v, msg)}

    elif fmt == 'update':

        # Update: "time"
        return {fmt: {
            'time':time.strptime(root.attrib['time'], ISO_8601_DATETIME) }}

    else:
        raise PyDeliciousException, "Unknown XML document format '%s'" % fmt


def dlcs_rss_request(tag="", popular=0, user="", url=''):
    """Parse a RSS request.

    This requests old (now undocumented?) URL paths that still seem to work.
    """

    tag = quote_plus(tag)
    user = quote_plus(user)

    if url != '':
        # http://del.icio.us/rss/url/efbfb246d886393d48065551434dab54
        url = DLCS_RSS + 'url/%s' % md5(url).hexdigest()

    elif user != '' and tag != '':
        url = DLCS_RSS + '%(user)s/%(tag)s' % {'user':user, 'tag':tag}

    elif user != '' and tag == '':
        # http://del.icio.us/rss/delpy
        url = DLCS_RSS + '%s' % user

    elif popular == 0 and tag == '':
        url = DLCS_RSS

    elif popular == 0 and tag != '':
        # http://del.icio.us/rss/tag/apple
        # http://del.icio.us/rss/tag/web2.0
        url = DLCS_RSS + "tag/%s" % tag

    elif popular == 1 and tag == '':
        url = DLCS_RSS + 'popular/'

    elif popular == 1 and tag != '':
        url = DLCS_RSS + 'popular/%s' % tag

    if DEBUG:
        print 'dlcs_rss_request', url

    rss = http_request(url).read()

    # assert feedparser, "dlcs_rss_request requires feedparser to be installed."
    if not feedparser:
        return rss

    rss = feedparser.parse(rss)

    posts = []
    for e in rss.entries:
        if e.has_key("links") and e["links"]!=[] and e["links"][0].has_key("href"):
            url = e["links"][0]["href"]
        elif e.has_key("link"):
            url = e["link"]
        elif e.has_key("id"):
            url = e["id"]
        else:
            url = ""
        if e.has_key("title"):
            description = e['title']
        elif e.has_key("title_detail") and e["title_detail"].has_key("title"):
            description = e["title_detail"]['value']
        else:
            description = ''
        try: tags = e['categories'][0][1]
        except:
            try: tags = e["category"]
            except: tags = ""
        if e.has_key("modified"):
            dt = e['modified']
        else:
            dt = ""
        if e.has_key("summary"):
            extended = e['summary']
        elif e.has_key("summary_detail"):
            e['summary_detail']["value"]
        else:
            extended = ""
        if e.has_key("author"):
            user = e['author']
        else:
            user = ""
        #  time = dt ist weist auf ein problem hin
        # die benennung der variablen ist nicht einheitlich
        #  api senden und
        #  xml bekommen sind zwei verschiedene schuhe :(
        posts.append({'url':url, 'description':description, 'tags':tags,
                'dt':dt, 'extended':extended, 'user':user})
    return posts


delicious_v2_feeds = {
    #"Bookmarks from the hotlist"
    '': "%(format)s",
    #"Recent bookmarks"
    'recent': "%(format)s/recent",
    #"Recent bookmarks by tag"
    'tagged': "%(format)s/tag/%(tags)s",
    #"Popular bookmarks"
    'popular': "%(format)s/popular",
    #"Popular bookmarks by tag"
    'popular_tagged': "%(format)s/popular/%(tag)s",
    #"Recent site alerts (as seen in the top-of-page alert bar on the site)"
    'alerts': "%(format)s/alerts",
    #"Bookmarks for a specific user"
    'user': "%(format)s/%(username)s",
    #"Bookmarks for a specific user by tag(s)"
    'user_tagged': "%(format)s/%(username)s/%(tags)s",
    #"Public summary information about a user (as seen in the network badge)"
    'user_info': "%(format)s/userinfo/%(username)s",
    #"A list of all public tags for a user"
    'user_tags': "%(format)s/tags/%(username)s",
    #"Bookmarks from a user's subscriptions"
    'user_subscription': "%(format)s/subscriptions/%(username)s",
    #"Private feed for a user's inbox bookmarks from others"
    'user_inbox': "%(format)s/inbox/%(username)s?private=%(key)s",
    #"Bookmarks from members of a user's network"
    'user_network': "%(format)s/network/%(username)s",
    #"Bookmarks from members of a user's network by tag"
    'user_network_tagged': "%(format)s/network/%(username)s/%(tags)s",
    #"A list of a user's network members"
    'user_network_member': "%(format)s/networkmembers/%(username)s",
    #"A list of a user's network fans"
    'user_network_fan': "%(format)s/networkfans/%(username)s",
    #"Recent bookmarks for a URL"
    'url': "%(format)s/url/%(urlmd5)s",
    #"Summary information about a URL (as seen in the tagometer)"
    'urlinfo': "json/urlinfo/%(urlmd5)s",
}

def dlcs_feed(name_or_url, url_map=delicious_v2_feeds, count=15, **params):

    """
    Request and parse a feed. See delicious_v2_feeds for available names and
    required parameters. Format defaults to json.
    """

# http://delicious.com/help/feeds
# TODO: plain or fancy

    format = params.setdefault('format', 'json')
    if count == 'all':
# TODO: fetch all
        print >>sys.stderr, "! Maxcount 100 "
        count = 100

    if name_or_url in url_map:
        params['count'] = count
        url = DLCS_FEEDS + url_map[name_or_url] % params

    else:
        url = name_or_url

    if DEBUG:
        print 'dlcs_feed', url

    feed = http_request(url).read()

    if format == 'rss':
        if feedparser:
            rss = feedparser.parse(feed)
            return rss

        else:
            return feed

    elif format == 'json':
        return feed


### Main module class

class DeliciousAPI:

    """A single-user Python facade to the del.icio.us HTTP API.

    See http://delicious.com/help/api.

    Methods ``request`` and ``request_raw`` represent the core. For all API
    paths there are furthermore methods (e.g. posts_add for 'posts/all') with
    an explicit declaration of parameters and documentation. 
    """

    def __init__(self, user, passwd, codec=PREFERRED_ENCODING,
            api_request=dlcs_api_request, xml_parser=dlcs_parse_xml,
            build_opener=dlcs_api_opener, encode_params=dlcs_encode_params):

        """Initialize access to the API for ``user`` with ``passwd``.

        ``codec`` sets the encoding of the arguments, which defaults to the
        users preferred locale.

        The ``api_request`` and ``xml_parser`` parameters by default point to
        functions within this package with standard implementations which
        request and parse a resource. See ``dlcs_api_request()`` and
        ``dlcs_parse_xml()``.

        Parameter ``build_opener`` is a callable that, provided with the 
        credentials, should build a urllib2 opener for the delicious API server
        with HTTP authentication. See ``dlcs_api_opener()`` for the default
        implementation.

        ``encode_params`` finally preprocesses API parameters before
        they are passed to ``api_request``.
        """

        assert user != ""
        self.user = user
        self.passwd = passwd
        self.codec = codec

        # Implement communication to server and parsing of respons messages:
        assert callable(encode_params)
        self._encode_params = encode_params
        assert callable(build_opener)
        self._opener = build_opener(user, passwd)
        assert callable(api_request)
        self._api_request = api_request
        assert callable(xml_parser)
        self._parse_response = xml_parser

    ### Core functionality

    def request(self, path, _raw=False, **params):
        """Sends a request message to `path` in the API, and parses the results
        from XML. Use with ``_raw=True`` or ``call request_raw()`` directly
        to get the filehandler and process the response message manually.

        Calls to some paths will return a `result` message, i.e.::

            <result code="..." />

        or::

            <result>...</result>

        These should all be parsed to ``{'result':(Boolean, MessageString)}``,
        this method raises a ``DeliciousError`` on negative `result` answers.
        Positive answers are silently accepted and nothing is returned.

        Using ``_raw=True`` bypasses all parsing and never raises
        ``DeliciousError``.

        See ``dlcs_parse_xml()`` and ``self.request_raw()``."""

        if _raw:
            # return answer
            return self.request_raw(path, **params)

        else:
            params = self._encode_params(params, self.codec)

            # get answer and parse
            fl = self._api_request(path, params=params, opener=self._opener)
            rs = self._parse_response(fl)

            if type(rs) == dict and 'result' in rs:
                if not rs['result'][0]:
                    # Raise an error for negative 'result' answers
                    errmsg = ""
                    if len(rs['result'])>0:
                        errmsg = rs['result'][1]
                    DeliciousError.raiseFor(errmsg, path, **params)

                else:
                    # not out-of-the-oridinary result, OK
                    return

            return rs

    def request_raw(self, path, **params):
        """Calls the path in the API, returns the filehandle. Returned file-
        like instances have an ``HTTPMessage`` instance with HTTP header
        information available. Use ``filehandle.info()`` or refer to the
        ``urllib2.openurl`` documentation.
        """
        # see `request()` on how the response can be handled
        params = self._encode_params(params, self.codec)
        return self._api_request(path, params=params, opener=self._opener)

    ### Explicit declarations of API paths, their parameters and docs

    # Tags
    def tags_get(self, **kwds):
        """Returns a list of tags and the number of times it is used by the
        user.
        ::

            <tags>
                <tag tag="TagName" count="888">
        """
        return self.request("tags/get", **kwds)

    def tags_delete(self, tag, **kwds):
        """Delete an existing tag.

        &tag={TAG}
            (required) Tag to delete
        """
        return self.request('tags/delete', tag=tag, **kwds)

    def tags_rename(self, old, new, **kwds):
        """Rename an existing tag with a new tag name. Returns a `result`
        message or raises an ``DeliciousError``. See ``self.request()``.

        &old={TAG}
            (required) Tag to rename.
        &new={TAG}
            (required) New tag name.
        """
        return self.request("tags/rename", old=old, new=new, **kwds)

    # Posts
    def posts_update(self, **kwds):
        """Returns the last update time for the user. Use this before calling
        `posts_all` to see if the data has changed since the last fetch.
        ::

            <update time="CCYY-MM-DDThh:mm:ssZ">
        """
        return self.request("posts/update", **kwds)

    def posts_dates(self, tag="", **kwds):
        """Returns a list of dates with the number of posts at each date.
        ::

            <dates>
                <date date="CCYY-MM-DD" count="888">

        &tag={TAG}
            (optional) Filter by this tag
        """
        return self.request("posts/dates", tag=tag, **kwds)

    def posts_get(self, tag="", dt="", url="", hashes=[], meta=True, **kwds):
        """Returns posts matching the arguments. If no date or url is given,
        most recent date will be used.
        ::

            <posts dt="CCYY-MM-DD" tag="..." user="...">
                <post ...>

        &tag={TAG} {TAG} ... {TAG}
            (optional) Filter by this/these tag(s).
        &dt={CCYY-MM-DDThh:mm:ssZ}
            (optional) Filter by this date, defaults to the most recent date on
            which bookmarks were saved.
        &url={URL}
            (optional) Fetch a bookmark for this URL, regardless of date.
        &hashes={MD5} {MD5} ... {MD5}
            (optional) Fetch multiple bookmarks by one or more URL MD5s
            regardless of date.
        &meta=yes
            (optional) Include change detection signatures on each item in a
            'meta' attribute. Clients wishing to maintain a synchronized local
            store of bookmarks should retain the value of this attribute - its
            value will change when any significant field of the bookmark
            changes.
        """
        return self.request("posts/get", tag=tag, dt=dt, url=url,
                hashes=hashes, meta=meta, **kwds)

    def posts_recent(self, tag="", count="", **kwds):
        """Returns a list of the most recent posts, filtered by argument.
        ::

            <posts tag="..." user="...">
                <post ...>

        &tag={TAG}
            (optional) Filter by this tag.
        &count={1..100}
            (optional) Number of items to retrieve (Default:15, Maximum:100).
        """
        return self.request("posts/recent", tag=tag, count=count, **kwds)

    def posts_all(self, tag="", start=None, results=None, fromdt=None,
            todt=None, meta=True, hashes=False, **kwds):
        """Returns all posts. Please use sparingly. Call the `posts_update`
        method to see if you need to fetch this at all.
        ::

            <posts tag="..." user="..." update="CCYY-MM-DDThh:mm:ssZ">
                <post ...>

        &tag
            (optional) Filter by this tag.
        &start={#}
            (optional) Start returning posts this many results into the set.
        &results={#}
            (optional) Return this many results.
        &fromdt={CCYY-MM-DDThh:mm:ssZ}
            (optional) Filter for posts on this date or later
        &todt={CCYY-MM-DDThh:mm:ssZ}
            (optional) Filter for posts on this date or earlier
        &meta=yes
            (optional) Include change detection signatures on each item in a
            'meta' attribute. Clients wishing to maintain a synchronized local
            store of bookmarks should retain the value of this attribute - its
            value will change when any significant field of the bookmark
            changes.
        &hashes
            (optional, exclusive) Do not fetch post details but a posts
            manifest with url- and meta-hashes. Other options do not apply.
        """
        if hashes:
            return self.request("posts/all", hashes=hashes, **kwds)
        else:
            return self.request("posts/all", tag=tag, fromdt=fromdt, todt=todt,
                    start=start, results=results, meta=meta, **kwds)

    def posts_add(self, url, description, extended="", tags="", dt="",
            replace=False, shared=True, **kwds):
        """Add a post to del.icio.us. Returns a `result` message or raises an
        ``DeliciousError``. See ``self.request()``.

        &url (required)
            the url of the item.
        &description (required)
            the description of the item.
        &extended (optional)
            notes for the item.
        &tags (optional)
            tags for the item (space delimited).
        &dt (optional)
            datestamp of the item (format "CCYY-MM-DDThh:mm:ssZ").
            Requires a LITERAL "T" and "Z" like in ISO8601 at
            http://www.cl.cam.ac.uk/~mgk25/iso-time.html for example:
            "1984-09-01T14:21:31Z"
        &replace=no (optional) - don't replace post if given url has already
            been posted.
        &shared=yes (optional) - wether the item is public.
        """
        return self.request("posts/add", url=url, description=description,
                extended=extended, tags=tags, dt=dt,
                replace=replace, shared=shared, **kwds)

    def posts_delete(self, url, **kwds):
        """Delete a post from del.icio.us. Returns a `result` message or
        raises an ``DeliciousError``. See ``self.request()``.

        &url (required)
            the url of the item.
        """
        return self.request("posts/delete", url=url, **kwds)

    # Bundles
    def bundles_all(self, **kwds):
        """Retrieve user bundles from del.icio.us.
        ::

            <bundles>
                <bundel name="..." tags=...">
        """
        return self.request("tags/bundles/all", **kwds)

    def bundles_set(self, bundle, tags, **kwds):
        """Assign a set of tags to a single bundle, wipes away previous
        settings for bundle. Returns a `result` messages or raises an
        ``DeliciousError``. See ``self.request()``.

        &bundle (required)
            the bundle name.
        &tags (required)
            list of tags.
        """
        if type(tags)==list:
            tags = " ".join(tags)
        return self.request("tags/bundles/set", bundle=bundle, tags=tags,
                **kwds)

    def bundles_delete(self, bundle, **kwds):
        """Delete a bundle from del.icio.us. Returns a `result` message or
        raises an ``DeliciousError``. See ``self.request()``.

        &bundle (required)
            the bundle name.
        """
        return self.request("tags/bundles/delete", bundle=bundle, **kwds)

    ### Utils

    # Lookup table for del.icio.us url-path to DeliciousAPI method.
    paths = {
        'tags/get': 'tags_get',
        'tags/delete': 'tags_delete',
        'tags/rename': 'tags_rename',
        'posts/update': 'posts_update',
        'posts/dates': 'posts_dates',
        'posts/get': 'posts_get',
        'posts/recent': 'posts_recent',
        'posts/all': 'posts_all',
        'posts/add': 'posts_add',
        'posts/delete': 'posts_delete',
        'tags/bundles/all': 'bundles_all',
        'tags/bundles/set': 'bundles_set',
        'tags/bundles/delete': 'bundles_delete',
    }
    def get_method(self, path):
        return getattr(self, self.paths[path])

    def get_url(self, url):
        """Return the del.icio.us url at which the HTML page with posts for
        ``url`` can be found.
        """
        return "http://del.icio.us/url/?url=%s" % (url,)

    def __repr__(self):
        return "DeliciousAPI(%s)" % self.user


### Convenience functions on this package

def apiNew(user, passwd):
    "Creates a new DeliciousAPI object, requires user(name) and passwd."
    return DeliciousAPI(user=user, passwd=passwd)

def add(user, passwd, url, description, tags="", extended="", dt=None,
        replace=False):
    apiNew(user, passwd).posts_add(url=url, description=description,
            extended=extended, tags=tags, dt=dt, replace=replace)

def get(user, passwd, tag="", dt=None, count=0, hashes=[]):
    "Returns a list of posts for the user"
    posts = apiNew(user, passwd).posts_get(
            tag=tag, dt=dt, hashes=hashes)['posts']
    if count: posts = posts[:count]
    return posts

def get_update(user, passwd):
    "Returns the last update time for the user."
    return apiNew(user, passwd).posts_update()['update']['time']

def get_all(user, passwd, tag="", start=0, results=100, fromdt=None,
        todt=None):
    "Returns a list with all posts. Please use sparingly. See `get_updated`"
    return apiNew(user, passwd).posts_all(tag=tag, start=start,
            results=results, fromdt=fromdt, todt=todt, meta=True)['posts']

def get_tags(user, passwd):
    "Returns a list with all tags for user."
    return apiNew(user=user, passwd=passwd).tags_get()['tags']

def delete(user, passwd, url):
    "Delete the URL from the del.icio.us account."
    apiNew(user, passwd).posts_delete(url=url)

def rename_tag(user, passwd, oldtag, newtag):
    "Rename the tag for the del.icio.us account."
    apiNew(user=user, passwd=passwd).tags_rename(old=oldtag, new=newtag)


### RSS functions

def getrss(tag="", popular=0, url='', user=""):
    """Get posts from del.icio.us via parsing RSS.

    tag (opt) sort by tag
    popular (opt) look for the popular stuff
    user (opt) get the posts by a user, this striks popular
    url (opt) get the posts by url
    """
    return dlcs_rss_request(tag=tag, popular=popular, user=user, url=url)

def get_userposts(user):
    "parse RSS for user"
    return getrss(user=user)

def get_tagposts(tag):
    "parse RSS for tag"
    return getrss(tag=tag)

def get_urlposts(url):
    "parse RSS for URL"
    return getrss(url=url)

def get_popular(tag=""):
    "parse RSS for popular URLS for tag"
    return getrss(tag=tag, popular=1)


### JSON feeds
# TODO: untested

def json_posts(user, count=15, tag=None, raw=True):
    """
    user
    count=###   the number of posts you want to get (default is 15, maximum 
                is 100)
    raw         a raw JSON object is returned, instead of an object named 
                Delicious.posts
    """
    url = "http://del.icio.us/feeds/json/" + \
            dlcs_encode_params({0:user})[0]
    if tag: url += '/'+dlcs_encode_params({0:tag})[0]

    return dlcs_feed(url, count=count, raw=raw)


def json_tags(user, atleast, count, sort='alpha', raw=True, callback=None):
    """
    user
    atleast=###         include only tags for which there are at least ### 
                        number of posts.
    count=###           include ### tags, counting down from the top.
    sort={alpha|count}  construct the object with tags in alphabetic order 
                        (alpha), or by count of posts (count).
    callback=NAME       wrap the object definition in a function call NAME(...),
                        thus invoking that function when the feed is executed.
    raw                 a pure JSON object is returned, instead of code that 
                        will construct an object named Delicious.tags.
    """
    url = 'http://del.icio.us/feeds/json/tags/' + \
            dlcs_encode_params({0:user})[0]
    return dlcs_feed(url, atleast=atleast, count=count, sort=sort, raw=raw, 
            callback=callback)


def json_network(user, raw=True, callback=None):
    """
    callback=NAME       wrap the object definition in a function call NAME(...)
    ?raw                a raw JSON object is returned, instead of an object named 
                        Delicious.posts
    """
    url = 'http://del.icio.us/feeds/json/network/' + \
            dlcs_encode_params({0:user})[0]
    return dlcs_feed(url, raw=raw, callback=callback)


def json_fans(user, raw=True, callback=None):
    """
    callback=NAME       wrap the object definition in a function call NAME(...)
    ?raw                a pure JSON object is returned, instead of an object named 
                        Delicious.
    """
    url = 'http://del.icio.us/feeds/json/fans/' + \
            dlcs_encode_params({0:user})[0]
    return dlcs_feed(url, raw=raw, callback=callback)


### delicious V2 feeds

def getfeed(name, **params):
    return dlcs_feed(name, **params)

