#!/usr/bin/env python

from distutils.core import setup

setup(
        name='django-tumblog',
        version='0.1',
        description='Django Tumblr clonse',
        author='Jon Raphaelson',
        author_email='jonraphaelson@gmail.com',
        url='http://www.github.com/lygaret/django-tumblog',
        packages=[
            'tumblog',
            'tumblog.models',
            'tumblog.templatetags',
            'tumblog.urls',
            'tumblog.views',
            'tumblog.tools',
        ]
)
