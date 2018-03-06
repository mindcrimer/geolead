# -*- coding: utf-8 -*-
from collections import OrderedDict, defaultdict
import datetime
import time

import xlwt
from django.utils.timezone import utc

from base.exceptions import ReportException
from reports import forms
from reports.jinjaglobals import date, render_timedelta
from reports.utils import parse_wialon_report_datetime, get_wialon_report_template_id, \
    cleanup_and_request_report, exec_report, get_report_rows, local_to_utc_time, utc_to_local_time
from reports.views.base import BaseReportView, WIALON_NOT_LOGINED, WIALON_USER_NOT_FOUND, \
    REPORT_ROW_HEIGHT
from snippets.jinjaglobals import date as date_format, floatcomma
from ura.models import Job
from users.models import User
from wialon.api import get_units
from wialon.exceptions import WialonException


class DrivingStyleView(BaseReportView):
    """Стиль вождения"""
    form_class = forms.DrivingStyleForm
    template_name = 'reports/driving_style.html'
    report_name = 'Отчет нарушений ПДД и инструкции по эксплуатации техники'
    can_download = True
    xls_heading_merge = 4

    def __init__(self, *args, **kwargs):
        super(DrivingStyleView, self).__init__(*args, **kwargs)
        self.form = None

    def get_default_form(self):
        data = self.request.POST if self.request.method == 'POST' else {
            'dt_from': datetime.datetime.now().replace(hour=0, minute=0, second=0, tzinfo=utc),
            'dt_to': datetime.datetime.now().replace(hour=23, minute=59, second=59, tzinfo=utc),
            'normal_rating': 10,
            'bad_rating': 30
        }
        return self.form_class(data)

    @staticmethod
    def get_new_grouping():
        return {
            'unit_name': '',
            'periods': []
        }

    @staticmethod
    def get_new_period(dt_from, dt_to, job=None):
        return {
            'dt_from': dt_from,
            'dt_to': dt_to,
            't_from': int(dt_from.timestamp()),
            't_to': int(dt_to.timestamp()),
            'job': job,
            'total_time': (dt_to - dt_from).total_seconds(),
            'facts': {
                'speed': {
                    'count': 0,
                    'seconds': .0
                },
                'lights': {
                    'count': 0,
                    'seconds': .0
                },
                'belt': {
                    'count': 0,
                    'seconds': .0
                },
                'devices': {
                    'count': 0,
                    'seconds': .0
                }
            },
            'percentage': {
                'speed': .0,
                'lights': .0,
                'belt': .0,
                'devices': .0
            },
            'rating': 100.0,
            'details': []
        }

    @staticmethod
    def parse_time_delta(value):
        delta = datetime.timedelta(seconds=0)
        parts = value.split(' ')
        digits = 0

        for part in parts:

            if part.isdigit():
                digits = int(part)
                continue

            if ':' in part:
                hours, minutes, seconds = [int(x) for x in part.split(':')]
                delta += datetime.timedelta(seconds=((hours * 3600) + (minutes * 60) + seconds))

            elif 'day' in part or 'дн' in part or 'ден' in part:
                delta += datetime.timedelta(days=digits)

            elif 'week' in part or 'недел' in part:
                delta += datetime.timedelta(days=digits * 7)

            elif 'month' in part or 'месяц' in part:
                delta += datetime.timedelta(days=digits * 30)

            elif 'year' in part or 'год' in part or 'лет' in part:
                delta += datetime.timedelta(days=digits * 365)

        return delta

    def get_context_data(self, **kwargs):
        kwargs = super(DrivingStyleView, self).get_context_data(**kwargs)
        self.form = kwargs['form']
        kwargs['today'] = datetime.date.today()

        if self.request.POST:
            report_data = OrderedDict()

            if self.form.is_valid():
                sess_id = self.request.session.get('sid')
                if not sess_id:
                    raise ReportException(WIALON_NOT_LOGINED)

                user = User.objects.filter(is_active=True) \
                    .filter(wialon_username=self.request.session.get('user')).first()

                if not user:
                    raise ReportException(WIALON_USER_NOT_FOUND)

                try:
                    units_list = get_units(sess_id=sess_id, extra_fields=True)
                except WialonException as e:
                    raise ReportException(str(e))

                units_dict = OrderedDict((u['id'], u['name']) for u in units_list)

                dt_from_utc = local_to_utc_time(self.form.cleaned_data['dt_from'], user.wialon_tz)
                dt_to_utc = local_to_utc_time(
                    self.form.cleaned_data['dt_to'].replace(second=59), user.wialon_tz
                )

                ura_user = user.ura_user if user.ura_user_id else user
                jobs = Job.objects.filter(
                    user=ura_user, date_begin__lt=dt_to_utc, date_end__gt=dt_from_utc
                ).order_by('date_begin', 'date_end')

                jobs_cache = defaultdict(list)
                for job in jobs:
                    try:
                        jobs_cache[int(job.unit_id)].append(job)
                    except ValueError:
                        pass

                template_id = get_wialon_report_template_id('driving_style_individual', user)

                print('Всего ТС: %s' % len(units_dict))

                i = 0
                for unit_id, unit_name in units_dict.items():
                    i += 1
                    print('%s) %s' % (i, unit_name))

                    if unit_id not in report_data:
                        report_data[unit_id] = self.get_new_grouping()
                    report_row = report_data[unit_id]
                    report_row['unit_name'] = unit_name

                    unit_jobs = jobs_cache.get(unit_id)
                    if not unit_jobs:
                        report_row['periods'].append(self.get_new_period(dt_from_utc, dt_to_utc))
                    else:
                        if unit_jobs[0].date_begin > dt_from_utc:
                            # если начало периода не попадает на смену
                            report_row['periods'].append(
                                self.get_new_period(dt_from_utc, unit_jobs[0].date_begin)
                            )

                        previous_job = None
                        for unit_job in unit_jobs:
                            # если между сменами есть перерыв, то тоже добавляем период
                            if previous_job and unit_job.date_begin > previous_job.date_end:
                                report_row['periods'].append(
                                    self.get_new_period(previous_job.date_end, unit_job.date_begin)
                                )

                            report_row['periods'].append(
                                self.get_new_period(
                                    unit_job.date_begin, unit_job.date_end, unit_job
                                )
                            )

                            previous_job = unit_job

                        if unit_jobs[-1].date_end < dt_to_utc:
                            # если смена закончилась до конца периода
                            report_row['periods'].append(
                                self.get_new_period(unit_jobs[-1].date_end, dt_to_utc)
                            )

                    # получим полный диапазон запроса
                    dt_from = int(time.mktime(report_row['periods'][0]['dt_from'].timetuple()))
                    dt_to = int(time.mktime(report_row['periods'][-1]['dt_to'].timetuple()))

                    cleanup_and_request_report(user, template_id, sess_id=sess_id)
                    r = exec_report(
                        user, template_id, dt_from, dt_to,
                        sess_id=sess_id, object_id=unit_id
                    )

                    wialon_report_rows = []
                    for table_index, table_info in enumerate(r['reportResult']['tables']):

                        if table_info['name'] != 'unit_ecodriving':
                            continue

                        wialon_report_rows = get_report_rows(
                            user,
                            table_index,
                            table_info['rows'],
                            level=1,
                            sess_id=sess_id
                        )

                    for row in wialon_report_rows:
                        detail_data = {
                            'speed': {
                                'count': 0,
                                'seconds': .0
                            },
                            'lights': {
                                'count': 0,
                                'seconds': .0
                            },
                            'belt': {
                                'count': 0,
                                'seconds': .0
                            },
                            'devices': {
                                'count': 0,
                                'seconds': .0
                            },
                            'dt': ''
                        }
                        violation = row['c'][1].lower() if row['c'][1] else ''
                        if 'свет' in violation or 'фар' in violation:
                            viol_key = 'lights'
                        elif 'скорост' in violation or 'превышен' in violation:
                            viol_key = 'speed'
                        elif 'ремн' in violation or 'ремен' in violation:
                            viol_key = 'belt'
                        elif 'кму' in violation:
                            viol_key = 'devices'
                        else:
                            viol_key = ''

                        if viol_key:
                            if detail_data:
                                detail_data['dt'] = parse_wialon_report_datetime(
                                    row['c'][2]['t']
                                    if isinstance(row['c'][2], dict)
                                    else row['c'][2]
                                )

                                for period in report_row['periods']:
                                    if period['t_from'] < row['t2'] and period['t_to'] > row['t1']:
                                        delta = min(row['t2'], period['t_to']) - \
                                                max(row['t1'], period['t_from'])
                                        detail_data[viol_key]['seconds'] = delta
                                        period['details'].append(detail_data)
                                        period['facts'][viol_key]['count'] += 1
                                        period['facts'][viol_key]['seconds'] += delta

                    for period in report_row['periods']:
                        period['dt_from'] = utc_to_local_time(period['dt_from'], user.wialon_tz)
                        period['dt_to'] = utc_to_local_time(period['dt_to'], user.wialon_tz)

                        for viol_key in ('speed', 'lights', 'belt', 'devices'):
                            percentage = period['facts'][viol_key]['seconds'] / \
                                         period['total_time'] * 100
                            period['percentage'][viol_key] = percentage
                            period['rating'] -= percentage

            kwargs.update(
                report_data=report_data,
                render_background=self.render_background,
                enumerate=enumerate
            )

        return kwargs

    def render_background(self, value, cleaned_data=None, style=False):
        if cleaned_data is None:
            cleaned_data = self.form.cleaned_data

        if value is None:
            if style:
                return self.styles['border_right_style']
            return '#FFF'

        if value < cleaned_data.get('normal_rating', 10):
            # green
            if style:
                return self.styles['border_right_green_style']
            return '#90EE90'

        elif value < cleaned_data.get('bad_rating', 30):
            # yellow
            if style:
                return self.styles['border_right_yellow_style']
            return '#FFFF00'

        # red
        if style:
            return self.styles['border_right_red_style']
        return '#FF4500'

    def write_xls_data(self, worksheet, context):
        worksheet = super(DrivingStyleView, self).write_xls_data(worksheet, context)
        cleaned_data = context['cleaned_data']

        self.styles.update({
            'border_right_green_style': xlwt.easyxf(
                'borders: bottom thin, left thin, right thin, top thin;'
                'align: vert centre, horiz right'
            ),
            'border_right_yellow_style': xlwt.easyxf(
                'borders: bottom thin, left thin, right thin, top thin;'
                'align: vert centre, horiz right'
            ),
            'border_right_red_style': xlwt.easyxf(
                'borders: bottom thin, left thin, right thin, top thin;'
                'align: vert centre, horiz right'
            ),
        })

        pattern = xlwt.Pattern()
        pattern.pattern = xlwt.Pattern.SOLID_PATTERN
        pattern.pattern_back_colour = xlwt.Style.colour_map['green']
        self.styles['border_right_green_style'].pattern = pattern

        pattern = xlwt.Pattern()
        pattern.pattern = xlwt.Pattern.SOLID_PATTERN
        pattern.pattern_back_colour = xlwt.Style.colour_map['yellow']
        self.styles['border_right_yellow_style'].pattern = pattern

        pattern = xlwt.Pattern()
        pattern.pattern = xlwt.Pattern.SOLID_PATTERN
        pattern.pattern_back_colour = xlwt.Style.colour_map['red']
        self.styles['border_right_red_style'].pattern = pattern

        worksheet.set_portrait(False)
        worksheet.col(0).width = 5000
        worksheet.col(1).width = 6000
        worksheet.col(2).width = 8000
        worksheet.col(3).width = 4000
        worksheet.col(4).width = 3000
        worksheet.col(5).width = 3000
        worksheet.col(6).width = 3000
        worksheet.col(7).width = 3000
        worksheet.col(8).width = 3000
        worksheet.col(9).width = 3000
        worksheet.col(10).width = 3000
        worksheet.col(11).width = 3000
        worksheet.col(12).width = 3000
        worksheet.col(13).width = 3000
        worksheet.col(14).width = 3000
        worksheet.col(15).width = 3200
        worksheet.col(16).width = 3000

        # header
        worksheet.write_merge(
            1, 1, 0, 16, 'За период: %s - %s' % (
                date_format(context['cleaned_data']['dt_from'], 'd.m.Y H:i'),
                date_format(context['cleaned_data']['dt_to'], 'd.m.Y H:i')
            )
        )

        worksheet.write_merge(
            2, 2, 0, 2, 'ФИО ответственного за разбор событий:',
            style=self.styles['left_center_style']
        )
        worksheet.write_merge(2, 2, 3, 9, '', style=self.styles['bottom_border_style'])

        worksheet.write_merge(
            3, 3, 0, 16, 'Детализация нарушений ПДД и инструкции по эксплуатации техники:',
            style=self.styles['right_center_style']
        )

        # head
        worksheet.write_merge(4, 6, 0, 0, ' Время', style=self.styles['border_center_style'])
        worksheet.write_merge(4, 6, 1, 1, ' ФИО', style=self.styles['border_center_style'])
        worksheet.write_merge(4, 6, 2, 2, ' № ТС', style=self.styles['border_center_style'])
        worksheet.write_merge(
            4, 6, 3, 3, ' Суммарное\nвремя\nв движении\nза период, ч',
            style=self.styles['border_center_style']
        )

        worksheet.write_merge(4, 4, 4, 11, ' Нарушения', style=self.styles['border_center_style'])
        worksheet.write_merge(
            5, 5, 4, 5, ' Превышение скоростного\nрежима, км/ч',
            style=self.styles['border_center_style']
        )
        worksheet.write_merge(
            5, 5, 6, 7, ' Выключенный свет фар\nпри движении',
            style=self.styles['border_center_style']
        )
        worksheet.write_merge(
            5, 5, 8, 9, ' Непристегнутый ремень\nбезопасности при движении',
            style=self.styles['border_center_style']
        )
        worksheet.write_merge(
            5, 5, 10, 11, ' Не транспортное положение\nоборудования при движении',
            style=self.styles['border_center_style']
        )
        worksheet.write(6, 4, ' Кол-во\nслучаев', style=self.styles['border_center_style'])
        worksheet.write(6, 5, ' Часов\nнарушения', style=self.styles['border_center_style'])
        worksheet.write(6, 6, ' Кол-во\nслучаев', style=self.styles['border_center_style'])
        worksheet.write(6, 7, ' Часов\nнарушения', style=self.styles['border_center_style'])
        worksheet.write(6, 8, ' Кол-во\nслучаев', style=self.styles['border_center_style'])
        worksheet.write(6, 9, ' Часов\nнарушения', style=self.styles['border_center_style'])
        worksheet.write(6, 10, ' Кол-во\nслучаев', style=self.styles['border_center_style'])
        worksheet.write(6, 11, ' Часов\nнарушения', style=self.styles['border_center_style'])

        worksheet.write_merge(
            4, 4, 12, 15, ' % нарушений', style=self.styles['border_center_style']
        )
        worksheet.write_merge(
            5, 6, 12, 12, ' Скоростной\nрежим', style=self.styles['border_center_style']
        )
        worksheet.write_merge(5, 6, 13, 13, ' Свет', style=self.styles['border_center_style'])
        worksheet.write_merge(5, 6, 14, 14, ' Ремень', style=self.styles['border_center_style'])
        worksheet.write_merge(
            5, 6, 15, 15, ' Доп.\nоборудование', style=self.styles['border_center_style']
        )
        worksheet.write_merge(
            4, 6, 16, 16, ' Оценка\nвождения, %', style=self.styles['border_center_style']
        )

        for i in range(17):
            worksheet.write(7, i, str(i + 1), style=self.styles['border_center_style'])

        for i in range(1, 8):
            worksheet.row(i).height = REPORT_ROW_HEIGHT
        worksheet.row(6).height = 520
        worksheet.row(5).height = 520

        # body
        i = 7
        for row in context['report_data'].values():
            for period in row['periods']:
                i += 1
                worksheet.row(i).level = 1
                # worksheet.row(i).collapse = 2

                worksheet.write(i, 0, '%s - %s' % (
                    date(period['dt_from'], 'Y-m-d H:i:s'),
                    date(period['dt_to'], 'Y-m-d H:i:s')
                ), style=self.styles['border_left_style'])

                worksheet.write(
                    i, 1, period['job'].driver_fio if period.get('job') else '',
                    style=self.styles['border_left_style']
                )

                worksheet.write(i, 2, row['unit_name'], style=self.styles['border_left_style'])

                worksheet.write(
                    i, 3, render_timedelta(period['total_time']),
                    style=self.styles['border_left_style']
                )
                worksheet.write(
                    i, 4, period['facts']['speed']['count']
                    if period['facts']['speed']['count'] else '',
                    style=self.styles['border_right_style']
                )
                worksheet.write(
                    i, 5, render_timedelta(period['facts']['speed']['seconds']),
                    style=self.styles['border_left_style']
                )
                worksheet.write(
                    i, 6, period['facts']['lights']['count']
                    if period['facts']['lights']['count'] else '',
                    style=self.styles['border_right_style']
                )
                worksheet.write(
                    i, 7, render_timedelta(period['facts']['lights']['seconds']),
                    style=self.styles['border_left_style']
                )
                worksheet.write(
                    i, 8, period['facts']['belt']['count']
                    if period['facts']['belt']['count'] else '',
                    style=self.styles['border_right_style']
                )
                worksheet.write(
                    i, 9, render_timedelta(period['facts']['belt']['seconds']),
                    style=self.styles['border_left_style']
                )
                worksheet.write(
                    i, 10, period['facts']['devices']['count']
                    if period['facts']['devices']['count'] else '',
                    style=self.styles['border_right_style']
                )
                worksheet.write(
                    i, 11, render_timedelta(period['facts']['devices']['seconds']),
                    style=self.styles['border_left_style']
                )
                worksheet.write(
                    i, 12, floatcomma(period['percentage']['speed'], -2)
                    if period['percentage']['speed'] else '',
                    style=self.render_background(
                        period['percentage']['speed'], style=True, cleaned_data=cleaned_data
                    )
                )
                worksheet.write(
                    i, 13, floatcomma(period['percentage']['lights'], -2)
                    if period['percentage']['lights'] else '',
                    style=self.render_background(
                        period['percentage']['lights'], style=True, cleaned_data=cleaned_data
                    )
                )
                worksheet.write(
                    i, 14, floatcomma(period['percentage']['belt'], -2)
                    if period['percentage']['belt'] else '',
                    style=self.render_background(
                        period['percentage']['belt'], style=True, cleaned_data=cleaned_data
                    )
                )
                worksheet.write(
                    i, 15, floatcomma(period['percentage']['devices'], -2)
                    if period['percentage']['devices'] else '',
                    style=self.render_background(
                        period['percentage']['devices'], style=True, cleaned_data=cleaned_data
                    )
                )
                worksheet.write(
                    i, 16, floatcomma(period['rating'], -2),
                    style=self.styles['border_right_style']
                )

                worksheet.row(i).height = 520

                for detail in period['details']:
                    i += 1
                    worksheet.row(i).level = 2
                    # worksheet.row(i).collapse = 2

                    worksheet.write(
                        i, 0, date(detail['dt'], 'Y-m-d H:i:s') or '',
                        style=self.styles['border_left_style']
                    )

                    worksheet.write(
                        i, 1, period['job'].driver_fio if period.get('job') else '',
                        style=self.styles['border_left_style']
                    )

                    worksheet.write(i, 2, row['unit_name'], style=self.styles['border_left_style'])
                    worksheet.write(i, 3, '', style=self.styles['border_left_style'])

                    worksheet.write(
                        i, 4, detail['speed']['count']
                        if detail['speed']['count'] else '',
                        style=self.styles['border_right_style']
                    )
                    worksheet.write(
                        i, 5, render_timedelta(detail['speed']['seconds']),
                        style=self.styles['border_left_style']
                    )
                    worksheet.write(
                        i, 6, detail['lights']['count']
                        if detail['lights']['count'] else '',
                        style=self.styles['border_right_style']
                    )
                    worksheet.write(
                        i, 7, render_timedelta(detail['lights']['seconds']),
                        style=self.styles['border_left_style']
                    )
                    worksheet.write(
                        i, 8, detail['belt']['count']
                        if detail['belt']['count'] else '',
                        style=self.styles['border_right_style']
                    )
                    worksheet.write(
                        i, 9, render_timedelta(detail['belt']['seconds']),
                        style=self.styles['border_left_style']
                    )
                    worksheet.write(
                        i, 10, detail['devices']['count']
                        if detail['devices']['count'] else '',
                        style=self.styles['border_right_style']
                    )
                    worksheet.write(
                        i, 11, render_timedelta(detail['devices']['seconds']),
                        style=self.styles['border_left_style']
                    )
                    worksheet.write(i, 12, '', style=self.styles['border_left_style'])
                    worksheet.write(i, 13, '', style=self.styles['border_left_style'])
                    worksheet.write(i, 14, '', style=self.styles['border_left_style'])
                    worksheet.write(i, 15, '', style=self.styles['border_left_style'])
                    worksheet.write(i, 16, '', style=self.styles['border_left_style'])

                    worksheet.row(i).height = 520

        return worksheet
