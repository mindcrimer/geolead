# -*- coding: utf-8 -*-
def public(funct):
    funct.is_public_http_method = True
    return funct
