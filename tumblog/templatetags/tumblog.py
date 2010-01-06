from django import template
from django.template import loader, Context

register = template.Library()

def do_post(parser, token):
    try:
        tag_name, blog, post = token.split_contents()
    except ValueError:
        raise Exception, "%r tag requires exactly 2 argument!" % token.contents.split()[0]

    return DoPostNode(blog, post)

class DoPostNode(template.Node):
    def __init__(self, blog, post):
        self.blog = template.Variable(blog)
        self.post = template.Variable(post)

    def render(self, context):
        blog = self.blog.resolve(context)
        post = self.post.resolve(context)
        t = loader.get_template(post.template_name)
        return t.nodelist.render(Context({'blog': blog, 'post': post}, autoescape=context.autoescape))

register.tag('post', do_post)
