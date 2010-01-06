from django.shortcuts import render_to_response
from tumblog.models import *

def create(request, blogslug):
    blog = Blog.objects.get(slug=blogslug)
    return render_to_response('tumblog/admin_create.html', {'blog': blog})
