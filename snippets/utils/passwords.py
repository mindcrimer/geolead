# -*- coding: utf-8 -*-
import random
import string


DEFAULT_TOKEN_SAMPLE = string.ascii_letters + string.digits


def generate_random_string(length=16, sample=DEFAULT_TOKEN_SAMPLE):
    """
    Создание хэша (токена, случайного пароля, пр.), где length - длина строки
    """
    lst = [random.choice(sample) for n in range(length)]
    return ''.join(lst)
