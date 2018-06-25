from collections import namedtuple
import datetime
import time

import xlwt

from base.exceptions import ReportException
from base.utils import parse_float
from reports import forms
from reports.utils import local_to_utc_time, get_wialon_report_template_id, exec_report, \
    cleanup_and_request_report, get_report_rows, parse_timedelta, parse_wialon_report_datetime, \
    format_timedelta
from reports.views.base import BaseVchmReportView, WIALON_NOT_LOGINED, WIALON_USER_NOT_FOUND
from snippets.jinjaglobals import date as date_format, floatcomma
from ura.models import Job
from users.models import User
from wialon.api import get_units, get_drive_rank_settings
from wialon.exceptions import WialonException


DRIVER_NO_NAME = 'Неизвестный'

RATING_TABLE = (
    ((0, 20), (100, 80)),
    ((20, 50), (80, 60)),
    ((50, 100), (60, 40)),
    ((100, 200), (40, 20)),
    ((200, 500), (20, 0))
)

ReportRow = namedtuple(
    'ReportRow', [
        'unit_name', 'violation_name', 'violation_count', 'duration', 'fine', 'rating',
        'from_dt', 'to_dt', 'mileage'
    ]
)


class VchmDrivingStyleView(BaseVchmReportView):
    """Отчет по БДД (ВЧМ)"""
    form_class = forms.VchmDrivingStyleForm
    template_name = 'reports/vchm_driving_style.html'
    report_name = 'Отчет по БДД'
    xls_heading_merge = 19

    def __init__(self, *args, **kwargs):
        super(VchmDrivingStyleView, self).__init__(*args, **kwargs)
        self.driver_cache = {}

    def get_default_form(self):
        data = self.request.POST if self.request.method == 'POST' else {
            'dt_from': datetime.date.today(),
            'dt_to': datetime.date.today()
        }
        return self.form_class(data)

    def render_background(self, scope, style=True):
        value = scope['rating']
        if value is None:
            if style:
                return self.styles['border_right_0_style']
            return '#FFF'

        if value < 25:
            # green
            if style:
                return self.styles['border_right_25_style']
            return '#FFFF00'

        elif value < 50:
            # yellow
            if style:
                return self.styles['border_right_50_style']
            return '#FFFF00'

        elif value < 75:
            # gold
            if style:
                return self.styles['border_right_75_style']
            return '#90EE90'

        # red
        if style:
            return self.styles['border_right_0_style']
        return '#FFF'

    @staticmethod
    def render_measure(row, field):
        scope = row['violations_measures'][field]
        return ' '.join([
            str(scope['count']),
            floatcomma(min(scope['total_time_percentage'], 100.0), -2) + '%',
            format_timedelta(scope['time_sec'])
        ]) if scope['count'] else ''

    def new_grouping(self, row, unit):
        return {
            'unit_name': row.unit_name,
            'unit_number': unit['number'] if unit['number'] else unit['name'],
            'driver_fio': self.driver_cache.get(unit['id'], DRIVER_NO_NAME),
            'total_mileage': row.mileage,
            'violations_measures': {
                'avg_overspeed': {
                    'count': 0,
                    'total_time_percentage': .0,
                    'time_sec': .0
                },
                'critical_overspeed': {
                    'count': 0,
                    'total_time_percentage': .0,
                    'time_sec': .0
                },
                'belt': {
                    'count': 0,
                    'total_time_percentage': .0,
                    'time_sec': .0
                },
                'lights': {
                    'count': 0,
                    'total_time_percentage': .0,
                    'time_sec': .0
                },
                'jib': {
                    'count': 0,
                    'total_time_percentage': .0,
                    'time_sec': .0
                }
            },
            'per_100km_count': {
                'brakings': {
                    'count': .0
                },
                'accelerations': {
                    'count': .0
                },
                'turns': {
                    'count': .0
                }
            },
            'rating': {
                'overspeed': {
                    'rating': 100,
                    'fine': 0
                },
                'belt': {
                    'rating': 100,
                    'fine': 0
                },
                'lights': {
                    'rating': 100,
                    'fine': 0
                },
                'brakings': {
                    'rating': 100,
                    'fine': 0
                },
                'accelerations': {
                    'rating': 100,
                    'fine': 0
                },
                'turns': {
                    'rating': 100,
                    'fine': 0
                },
                'jib': {
                    'rating': 100,
                    'fine': 0
                }
            },
            'rating_total': {
                'avg': {
                    'rating': 100,
                    'fine': 0
                },
                'critical_avg': {
                    'rating': 100,
                    'fine': 0
                }
            }
        }

    @staticmethod
    def calculate_rating(fine):
        rating = 0

        for segment, values in RATING_TABLE:
            if segment[0] <= fine <= segment[1]:
                ratio = (fine - segment[0]) / (segment[1] - segment[0])
                rating = values[0] - (ratio * (values[0] - values[1]))
                break

        return rating

    @staticmethod
    def parse_report_row(row, user):
        return ReportRow(
            row[0],  # unit_name
            row[1].lower().strip(),  # violation
            int(row[2]) if row[2] else 1,  # violation_count
            parse_timedelta(row[3]).total_seconds(),  # duration
            parse_float(row[4], default=.0),  # fine
            parse_float(row[5], default=.0),  # rating
            local_to_utc_time(
                parse_wialon_report_datetime(
                    row[6]['t'] if isinstance(row[6], dict) else row[6]
                ), user.wialon_tz
            ),  # from_dt
            local_to_utc_time(
                parse_wialon_report_datetime(
                    row[7]['t'] if isinstance(row[7], dict) else row[7]
                ), user.wialon_tz
            ),  # to_dt
            parse_float(row[9], default=.0)  # mileage_corrected
        )

    def get_context_data(self, **kwargs):
        kwargs = super(VchmDrivingStyleView, self).get_context_data(**kwargs)
        report_data = None
        form = kwargs['form']

        sess_id = self.request.session.get('sid')
        if not sess_id:
            raise ReportException(WIALON_NOT_LOGINED)

        try:
            units_list = get_units(sess_id=sess_id, extra_fields=True)
        except WialonException as e:
            raise ReportException(str(e))

        kwargs['units'] = units_list
        units_dict = {u['name']: u for u in units_list}

        if self.request.POST:

            if form.is_valid():
                report_data = []

                user = User.objects.filter(
                    is_active=True,
                    wialon_username=self.request.session.get('user')
                ).first()
                if not user:
                    raise ReportException(WIALON_USER_NOT_FOUND)

                dt_from = local_to_utc_time(datetime.datetime.combine(
                    form.cleaned_data['dt_from'],
                    datetime.time(0, 0, 0)
                ), user.wialon_tz)
                dt_to = local_to_utc_time(datetime.datetime.combine(
                    form.cleaned_data['dt_to'],
                    datetime.time(23, 59, 59)
                ), user.wialon_tz)

                ura_user = user.ura_user if user.ura_user_id else user
                jobs = Job.objects.filter(
                    user=ura_user, date_begin__lt=dt_to, date_end__gt=dt_from
                )
                self.driver_cache = {int(j.unit_id): j.driver_fio for j in jobs if j.unit_title}

                template_id = get_wialon_report_template_id('driving_style', user)

                mobile_vehicle_types = set()
                if user.wialon_mobile_vehicle_types:
                    mobile_vehicle_types = set(
                        x.strip() for x in user.wialon_mobile_vehicle_types.lower().split(',')
                    )

                cleanup_and_request_report(user, template_id, sess_id=sess_id)
                report_kwargs = {}
                if form.cleaned_data.get('unit'):
                    report_kwargs['object_id'] = form.cleaned_data['unit']

                r = exec_report(
                    user,
                    template_id,
                    int(time.mktime(dt_from.timetuple())),
                    int(time.mktime(dt_to.timetuple())),
                    sess_id=sess_id,
                    **report_kwargs
                )

                wialon_report_rows = {}
                for table_index, table_info in enumerate(r['reportResult']['tables']):
                    wialon_report_rows[table_info['name']] = get_report_rows(
                        user,
                        table_index,
                        table_info['rows'],
                        level=2 if table_info['name'] == 'unit_group_ecodriving' else 1,
                        sess_id=sess_id
                    )

                i = 0
                for row in wialon_report_rows.get('unit_group_ecodriving', []):
                    i += 1
                    violations = [self.parse_report_row(x['c'], user) for x in row['r']]
                    row = self.parse_report_row(row['c'], user)
                    unit = units_dict.get(row.unit_name)

                    if not unit:
                        print('%s) Unit not found: %s' % (i, row.unit_name))
                        continue

                    vehicle_type = unit['vehicle_type'].lower()
                    if mobile_vehicle_types and vehicle_type \
                            and vehicle_type not in mobile_vehicle_types:
                        print('%s) Skip vehicle type "%s" of item %s' % (
                            i, vehicle_type, row.unit_name
                        ))
                        continue

                    print('%s) Processing %s' % (i, row.unit_name))
                    ecodriving = get_drive_rank_settings(unit['id'], sess_id=sess_id)
                    ecodriving = {k.lower(): v for k, v in ecodriving.items()}
                    report_row = self.new_grouping(row, unit)

                    # собственно расчеты метрик
                    for violation in violations:
                        verbose = violation.violation_name
                        violation_name = ''
                        violation_scope = 'violations_measures'

                        if 'превышение скорости' in verbose:
                            if 'cреднее' in verbose or 'среднее' in verbose:
                                violation_name = 'avg_overspeed'
                            elif 'опасное' in verbose:
                                violation_name = 'critical_overspeed'
                        elif 'ремень' in verbose or 'ремня' in verbose:
                            violation_name = 'belt'
                        elif 'фар' in verbose:
                            violation_name = 'lights'
                        elif 'кму' in verbose or 'стрел' in verbose:
                            violation_name = 'jib'
                        elif 'разгон' in verbose or 'ускорение' in verbose:
                            violation_scope = 'per_100km_count'
                            violation_name = 'accelerations'
                        elif 'торможение' in verbose:
                            violation_scope = 'per_100km_count'
                            violation_name = 'brakings'
                        elif 'поворот' in verbose:
                            violation_scope = 'per_100km_count'
                            violation_name = 'turns'

                        if not violation_name:
                            print('%s) %s: unknown violaton name %s' % (i, row.unit_name, verbose))
                            continue

                        scope = report_row[violation_scope][violation_name]

                        if violation_scope == 'per_100km_count':
                            scope['count'] += (violation.violation_count / row.mileage * 100)
                        else:
                            scope['count'] += violation.violation_count
                            scope['total_time_percentage'] += (
                                violation.duration / row.duration * 100
                            )
                            scope['time_sec'] += violation.duration

                        # суммируем штрафы
                        rating_violation_name = violation_name
                        if 'overspeed' in violation_name:
                            rating_violation_name = 'overspeed'

                        # извлечем настройки объектов и узнаем, нужно ли рассчитывать
                        # относительно пробега
                        settings = ecodriving.get(verbose)
                        devider = 1
                        if settings and settings.get('flags', 0) in (2, 3, 7, 10):
                            devider = max(1.0, row.mileage)
                        fine = violation.fine / devider
                        report_row['rating'][rating_violation_name]['fine'] += fine
                        report_row['rating_total']['avg']['fine'] += fine

                        if rating_violation_name in ('belt', 'lights', 'jib', 'brakings'):
                            report_row['rating_total']['critical_avg']['fine'] += fine

                    # расчет статистики (рейтинга)
                    for key in report_row['rating']:
                        scope = report_row['rating'][key]
                        scope['rating'] = self.calculate_rating(scope['fine'])
                    report_row['rating_total']['avg']['rating'] = self.calculate_rating(
                        report_row['rating_total']['avg']['fine']
                    )
                    report_row['rating_total']['critical_avg']['rating'] = self.calculate_rating(
                        report_row['rating_total']['critical_avg']['fine']
                    )

                    report_data.append(report_row)

            kwargs['report_data'] = report_data
        return kwargs

    def write_xls_data(self, worksheet, context):
        worksheet = super(VchmDrivingStyleView, self).write_xls_data(worksheet, context)

        self.styles.update({
            'border_right_0_style': xlwt.easyxf(
                'borders: bottom thin, left thin, right thin, top thin;'
                'align: vert centre, horiz right'
            ),
            'border_right_25_style': xlwt.easyxf(
                'borders: bottom thin, left thin, right thin, top thin;'
                'align: vert centre, horiz right'
            ),
            'border_right_50_style': xlwt.easyxf(
                'borders: bottom thin, left thin, right thin, top thin;'
                'align: vert centre, horiz right'
            ),
            'border_right_75_style': xlwt.easyxf(
                'borders: bottom thin, left thin, right thin, top thin;'
                'align: vert centre, horiz right'
            )
        })

        pattern = xlwt.Pattern()
        pattern.pattern = xlwt.Pattern.SOLID_PATTERN
        pattern.pattern_fore_colour = xlwt.Style.colour_map['light_green']
        self.styles['border_right_0_style'].pattern = pattern

        pattern = xlwt.Pattern()
        pattern.pattern = xlwt.Pattern.SOLID_PATTERN
        pattern.pattern_fore_colour = xlwt.Style.colour_map['red']
        self.styles['border_right_25_style'].pattern = pattern

        pattern = xlwt.Pattern()
        pattern.pattern = xlwt.Pattern.SOLID_PATTERN
        pattern.pattern_fore_colour = xlwt.Style.colour_map['gold']
        self.styles['border_right_50_style'].pattern = pattern

        pattern = xlwt.Pattern()
        pattern.pattern = xlwt.Pattern.SOLID_PATTERN
        pattern.pattern_fore_colour = xlwt.Style.colour_map['light_yellow']
        self.styles['border_right_75_style'].pattern = pattern

        worksheet.set_portrait(False)
        worksheet.col(0).width = 2900
        worksheet.col(1).width = 5500
        worksheet.col(2).width = 2130
        worksheet.col(3).width = 4700
        worksheet.col(4).width = 4700
        worksheet.col(5).width = 4700
        worksheet.col(6).width = 4700
        worksheet.col(7).width = 4700
        worksheet.col(8).width = 4700
        worksheet.col(9).width = 2400
        worksheet.col(10).width = 2400
        worksheet.col(11).width = 2500
        worksheet.col(12).width = 2300
        worksheet.col(13).width = 2450
        worksheet.col(14).width = 2300
        worksheet.col(15).width = 3000
        worksheet.col(16).width = 2750
        worksheet.col(17).width = 2750
        worksheet.col(18).width = 2330
        worksheet.col(19).width = 3000
        worksheet.col(20).width = 3000

        headings = (
            'Гос №',
            'Водитель',
            'Пробег,\nкм',
            'Превышение\nдопустимой\nскорости',
            'Превышение\nкритической\nскорости',
            'Движение\nбез ремня\nбезопасности',
            'Движение\nбез фар',
            'Движение\nс поднятой КМУ\n(кузовом)',
            'Резкие\nтормож.,\nшт. на\n100 км',
            'Резкие\nускор-я,\nшт. на\n100 км',
            'Резкие\nповороты,\nшт. на\n100 км',
            'Собл.\nскор.\nреж.',
            'Ремень\nбезопас.',
            'Фары',
            'Торможения',
            'Ускорения',
            'Повороты',
            'КМУ\n*(кузов)',
            'Взвеш.\nоценка\nкачества\nвождения',
            'Оценка\nкритических\nпараметров'
        )

        # header
        worksheet.write_merge(
            1, 1, 0, 16, 'За период: %s - %s' % (
                date_format(context['cleaned_data']['dt_from'], 'd.m.Y'),
                date_format(context['cleaned_data']['dt_to'], 'd.m.Y')
            )
        )

        x = 2
        for y, heading in enumerate(headings):
            worksheet.write(
                x, y, heading, style=self.styles['border_center_style']
            )

        worksheet.row(2).height = 900

        for row in context['report_data']:
            x += 1
            worksheet.write(
                x, 0, row['unit_number'],
                style=self.styles['border_left_style']
            )
            worksheet.write(
                x, 1, row['driver_fio'],
                style=self.styles['border_left_style']
            )
            worksheet.write(
                x, 2, row['total_mileage'],
                style=self.styles['border_right_style']
            )
            worksheet.write(
                x, 3, self.render_measure(row, 'avg_overspeed'),
                style=self.styles['border_left_style']
            )
            worksheet.write(
                x, 4, self.render_measure(row, 'critical_overspeed'),
                style=self.styles['border_left_style']
            )
            worksheet.write(
                x, 5, self.render_measure(row, 'belt'),
                style=self.styles['border_left_style']
            )
            worksheet.write(
                x, 6, self.render_measure(row, 'lights'),
                style=self.styles['border_left_style']
            )
            worksheet.write(
                x, 7, self.render_measure(row, 'jib'),
                style=self.styles['border_left_style']
            )
            worksheet.write(
                x, 8, floatcomma(row['per_100km_count']['brakings']['count'], -2),
                style=self.styles['border_right_style']
            )
            worksheet.write(
                x, 9, floatcomma(row['per_100km_count']['accelerations']['count'], -2),
                style=self.styles['border_right_style']
            )
            worksheet.write(
                x, 10, floatcomma(row['per_100km_count']['turns']['count'], -2),
                style=self.styles['border_right_style']
            )
            worksheet.write(
                x, 11, self.render_rating(row['rating']['overspeed']),
                style=self.render_background(row['rating']['overspeed'])
            )
            worksheet.write(
                x, 12, self.render_rating(row['rating']['belt']),
                style=self.render_background(row['rating']['belt'])
            )
            worksheet.write(
                x, 13, self.render_rating(row['rating']['lights']),
                style=self.render_background(row['rating']['lights'])
            )
            worksheet.write(
                x, 14, self.render_rating(row['rating']['brakings']),
                style=self.render_background(row['rating']['brakings'])
            )
            worksheet.write(
                x, 15, self.render_rating(row['rating']['accelerations']),
                style=self.render_background(row['rating']['accelerations'])
            )
            worksheet.write(
                x, 16, self.render_rating(row['rating']['turns']),
                style=self.render_background(row['rating']['turns'])
            )
            worksheet.write(
                x, 17, self.render_rating(row['rating']['jib']),
                style=self.render_background(row['rating']['jib'])
            )
            worksheet.write(
                x, 18, self.render_rating(row['rating_total']['avg']),
                style=self.render_background(row['rating_total']['avg'])
            )
            worksheet.write(
                x, 19, self.render_rating(row['rating_total']['critical_avg']),
                style=self.render_background(row['rating_total']['critical_avg'])
            )
        return worksheet

    @staticmethod
    def render_rating(scope):
        return floatcomma(scope['rating'], -2)
