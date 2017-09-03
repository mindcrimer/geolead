# -*- coding: utf-8 -*-
import datetime

from snippets.template_backends.jinja2 import jinjafilter


@jinjafilter
def render_timedelta(value):
    result = str(datetime.timedelta(seconds=value))
    if 'day' in result:
        result = result.replace('days', 'day')

        try:
            days_count = int(result.split(' ')[0])
        except (ValueError, IndexError):
            days_count = 0

        if days_count:
            last_digit = int(str(days_count)[-1])
            if last_digit == 1:
                result = result.replace('day', 'день')

            elif 0 < last_digit < 5:
                result = result.replace('day', 'дня')

            else:
                result = result.replace('days', 'дней')

    return result


@jinjafilter
def render_background(value):
    if value is None:
        return '#FFF'

    if value < 10:
        return '#90EE90'

    elif value < 30:
        return '#FFFF00'

    return '#FF4500'
