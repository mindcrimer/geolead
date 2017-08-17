# -*- coding: utf-8 -*-
from django.conf import settings

from snippets.template_backends.jinja2 import jinjaglobal, jinjafilter


@jinjaglobal
def discus_account():
    return settings.DISCUS_ACCOUNT


@jinjafilter
def preprocess_content(content):
    if '<table' not in content:
        return content

    content = content.replace('<table', '<div class="table-wrap"><table')\
        .replace('</table>', '</table></div>')

    return content
