import datetime
from django.core.paginator import QuerySetPaginator
from django.views.generic import list_detail, date_based
from django.conf import settings
from django.http import Http404

from tagging.models import TaggedItem
from tumblog.models import Blog, Post

def _paginated_archive(request, queryset, page=1, extra_context={}, template_name=None):
    paginator = QuerySetPaginator(queryset, settings.PAGINATION_COUNT)

    # if we're requesting a page, make sure there are enough for it
    if not int(page) in paginator.page_range:
        raise Http404

    options = {
        'queryset': queryset,
        'paginate_by': settings.PAGINATION_COUNT,
        'page': page,
        'extra_context': extra_context,
    }

    return list_detail.object_list(request, **options)

def archive_index(request, blogslug, page=1, extra_context={}, template_name=None):
    """ index view of posts """
    blog = Blog.objects.get(slug=blogslug)
    return _paginated_archive(request, blog.posts, page, dict(extra_context, **{'blog': blog}), template_name)

def archive_year(request, blogslug, year, page=1, extra_context={}, template_name=None):
    """ date based index of tumblog posts. """
    blog = Blog.objects.get(slug=blogslug)
    queryset = blog.posts.filter(pubtime__year = year)
    viewname = "posted during %s" % year
    return _paginated_archive(request, queryset, page, dict(extra_context, **{'blog': blog, 'viewname': viewname}), template_name)

def archive_month(request,blogslug,  year, month, page=1, extra_context={}, template_name=None):
    """ date based index of tumblog posts. """
    blog = Blog.objects.get(slug=blogslug)
    queryset = blog.posts.filter(pubtime__year = year, pubtime__month = month)
    viewname = "posted during %s/%s" % (year, month)
    return _paginated_archive(request, queryset, page, dict(extra_context, **{'blog': blog, 'viewname': viewname}), template_name)

def archive_day(request, blogslug, year, month, day, page=1, extra_context={}, template_name=None):
    """ date based index of tumblog posts. """
    blog = Blog.objects.get(slug=blogslug)
    queryset = blog.posts.filter(pubtime__year = year, pubtime__month = month, pubtime__day = day)
    viewname = "posted on %s/%s/%s" % (year, month, day)
    return _paginated_archive(request, queryset, page, dict(extra_context, **{'blog': blog, 'viewname': viewname}), template_name)

def archive_tagged(request, blogslug, tag, page=1, extra_context={}, template_name=None):
    blog = Blog.objects.get(slug=blogslug)
    queryset = TaggedItem.objects.get_by_model(blog.posts, tag)
    viewname = "tagged: '%s'" % tag
    return _paginated_archive(request, queryset, page, dict(extra_context, **{'blog': blog, 'viewname': viewname}), template_name)

def archive_detail(request, blogslug, year, month, day, slug, extra_context={}, template_name=None):
    blog = Blog.objects.get(slug=blogslug)
    queryset = blog.posts.filter(pubtime__year = year, pubtime__month = month, pubtime__day = day)
    context = dict(extra_context, **{'blog': blog})
    return list_detail.object_detail(request, queryset, **{'slug': slug, 'slug_field': 'slug', 'extra_context': context})

