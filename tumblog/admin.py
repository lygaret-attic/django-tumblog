from tumblog.models import *
from django.contrib import admin

class PostAdmin(admin.ModelAdmin):
    date_hierarchy = 'modtime'
    exclude = ('body', 'quote', 'citation', 'description', 'caption', 'post_type', 'slug',)

class PhotoInline(admin.StackedInline):
    model = Photo
    exclude = ('caption',)

class PhotoPostAdmin(PostAdmin):
    inlines = [ PhotoInline, ]

class BlogAdmin(admin.ModelAdmin):
    exclude = ('description',)

admin.site.register(Blog, BlogAdmin)
admin.site.register(TextPost, PostAdmin)
admin.site.register(QuotePost, PostAdmin)
admin.site.register(LinkPost, PostAdmin)
admin.site.register(PhotoPost, PhotoPostAdmin)
