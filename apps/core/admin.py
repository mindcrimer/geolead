# -*- coding: utf-8 -*-
from django.contrib import admin
from django.contrib.auth.models import Group

admin.site.unregister(Group)
