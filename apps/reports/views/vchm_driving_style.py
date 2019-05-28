from collections import namedtuple, defaultdict
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
from users.models import User, UserTotalReportUser
from wialon.api import get_units, get_drive_rank_settings
from wialon.auth import get_wialon_session_key
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
        self.driver_id_cache = {}
        self.mileage_cache = {}
        self.duration_cache = {}
        self.is_total = False

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

    def new_grouping(self, row=None, unit=None):
        return {
            'driver_id': self.driver_id_cache.get(int(unit['id']), None) if unit else None,
            'unit_name': row.unit_name if row else '',
            'unit_number': (unit['number'] if unit['number'] else unit['name']) if unit else '',
            'total_mileage': row.mileage if row else .0,
            'total_duration': row.duration if row else .0,
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
                    'count': .0,
                    'total_count': 0
                },
                'accelerations': {
                    'count': .0,
                    'total_count': 0
                },
                'turns': {
                    'count': .0,
                    'total_count': 0
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

    def parse_report_row(self, row, user, total=False):
        return ReportRow(
            row[0],  # unit_name
            row[1].lower().strip(),  # violation
            int(row[2]) if row[2] else 1,  # violation_count
            self.duration_cache.get(row[0], 0)
            if total else parse_timedelta(row[3]).total_seconds(),  # duration
            parse_float(row[4], default=.0),  # fine
            parse_float(row[5], default=.0),  # rating
            local_to_utc_time(
                parse_wialon_report_datetime(
                    row[6]['t'] if isinstance(row[6], dict) else row[6]
                ), user.timezone
            ),  # from_dt
            local_to_utc_time(
                parse_wialon_report_datetime(
                    row[7]['t'] if isinstance(row[7], dict) else row[7]
                ), user.timezone
            ),  # to_dt
            self.mileage_cache.get(row[0], .0)
            if total else parse_float(row[9], default=.0)  # mileage_corrected
        )

    def get_context_data(self, **kwargs):
        kwargs = super(VchmDrivingStyleView, self).get_context_data(**kwargs)
        self.is_total = bool(self.request.POST.get('total_report'))
        total_report_data = []
        form = kwargs['form']

        sess_id = self.request.session.get('sid')
        if not sess_id:
            raise ReportException(WIALON_NOT_LOGINED)

        try:
            units_list = get_units(sess_id, extra_fields=True)
        except WialonException as e:
            raise ReportException(str(e))

        kwargs['units'] = units_list

        if not self.request.POST:
            return kwargs

        units_dict = {u['name']: u for u in units_list}
        if form.is_valid():
            if self.is_total:
                user = User.objects.filter(
                    is_active=True,
                    username=self.request.session.get('user')
                ).first()

                if not user:
                    raise ReportException(WIALON_USER_NOT_FOUND)

                report_users = UserTotalReportUser.objects\
                    .published()\
                    .order_by('ordering')\
                    .filter(executor_user=user)\
                    .select_related('report_user', 'report_user__ura_user')

                users = set(user.report_user for user in report_users)

            else:
                user = User.objects.filter(
                    is_active=True,
                    wialon_username=self.request.session.get('user')
                ).first()

                if not user:
                    raise ReportException(WIALON_USER_NOT_FOUND)

                users = {user}

            dt_from = local_to_utc_time(datetime.datetime.combine(
                form.cleaned_data['dt_from'],
                datetime.time(0, 0, 0)
            ), user.timezone)
            dt_to = local_to_utc_time(datetime.datetime.combine(
                form.cleaned_data['dt_to'],
                datetime.time(23, 59, 59)
            ), user.timezone)

            for user in users:
                report_data = []
                print('Evaluating report for user %s' % user)
                ura_user = user.ura_user if user.ura_user_id else user
                print('URA user is %s' % ura_user)

                if self.request.POST.get('total_report'):
                    sess_id = get_wialon_session_key(user)
                    if not sess_id:
                        raise ReportException(WIALON_NOT_LOGINED)

                    try:
                        units_list = get_units(sess_id, extra_fields=True)
                    except WialonException as e:
                        raise ReportException(str(e))

                    kwargs['units'] = units_list
                    units_dict = {u['name']: u for u in units_list}

                jobs = Job.objects\
                    .filter(user=ura_user, date_begin__lt=dt_to, date_end__gt=dt_from)

                if form.cleaned_data.get('unit'):
                    jobs = jobs.filter(unit_id=str(form.cleaned_data['unit']))

                self.driver_cache = {
                    j.driver_id: j.driver_fio
                    for j in jobs
                    if j.driver_fio.lower() != 'нет в.а.'
                }

                self.driver_id_cache = {
                    int(j.unit_id): j.driver_id
                    for j in jobs
                    if j.driver_fio.lower() != 'нет в.а.'
                }

                template_id = get_wialon_report_template_id('driving_style', user, sess_id)

                mobile_vehicle_types = set()
                if user.wialon_mobile_vehicle_types:
                    mobile_vehicle_types = set(
                        x.strip() for x in user.wialon_mobile_vehicle_types.lower().split(',')
                    )

                cleanup_and_request_report(user, template_id, sess_id)
                report_kwargs = {}
                if form.cleaned_data.get('unit'):
                    report_kwargs['object_id'] = form.cleaned_data['unit']

                print('Executing report...')
                r = exec_report(
                    user,
                    template_id,
                    sess_id,
                    int(time.mktime(dt_from.timetuple())),
                    int(time.mktime(dt_to.timetuple())),
                    **report_kwargs
                )

                wialon_report_rows = {}
                for table_index, table_info in enumerate(r['reportResult']['tables']):
                    wialon_report_rows[table_info['name']] = get_report_rows(
                        sess_id,
                        table_index,
                        table_info['rows'],
                        level=2 if table_info['name'] == 'unit_group_ecodriving' else 1
                    )

                self.mileage_cache = {
                    row['c'][0]: parse_float(row['c'][1], default=.0)
                    for row in wialon_report_rows.get('unit_group_trips', [])
                }
                self.duration_cache = {
                    row['c'][0]: parse_timedelta(row['c'][2]).total_seconds()
                    for row in wialon_report_rows.get('unit_group_trips', [])
                }

                i = 0
                for row in wialon_report_rows.get('unit_group_ecodriving', []):
                    i += 1
                    violations = [
                        self.parse_report_row(x['c'], user, total=False)
                        for x in row['r']
                    ]
                    row = self.parse_report_row(row['c'], user, total=True)
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
                    ecodriving = get_drive_rank_settings(unit['id'], sess_id)
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
                            print(
                                '%s) %s: unknown violaton name %s' % (
                                    i, row.unit_name, verbose
                                )
                            )
                            continue

                        scope = report_row[violation_scope][violation_name]

                        if violation_scope == 'per_100km_count':
                            scope['count'] += violation.violation_count / row.mileage * 100
                            scope['total_count'] += violation.violation_count
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

                # группируем строки по нарушителям и сортируем, самых нарушающих наверх
                groups = defaultdict(lambda: {
                    'rows': [],
                    'driver_id': '',
                    'driver_fio': '',
                    'company_name': ''
                })

                # сначала отсортируем без группировки,
                # чтобы внутри групп была правильная сортировка
                report_data = sorted(
                    report_data,
                    key=lambda x: x['rating_total']['critical_avg']['rating']
                )

                for row in report_data:
                    group = groups[row['driver_id']]
                    group['driver_id'] = row['driver_id']
                    group['driver_fio'] = self.driver_cache.get(row['driver_id'], DRIVER_NO_NAME)
                    group['company_name'] = user.company_name or user.wialon_resource_name or ''
                    if not group['driver_fio'] \
                            or group['driver_fio'].strip().lower() != 'неизвестный':
                        group['stats'] = self.new_grouping()
                    group['rows'].append(row)

                # собираем суммарную статистику по каждому водителю
                report_data = list(groups.values())
                for group in report_data:
                    if 'stats' not in group:
                        continue

                    for row in group['rows']:
                        group['stats']['total_mileage'] += row['total_mileage']
                        group['stats']['total_duration'] += row['total_duration']

                    for field in ('avg_overspeed', 'critical_overspeed', 'belt', 'lights', 'jib'):
                        for row in group['rows']:
                            group['stats']['violations_measures'][field]['count'] += \
                                row['violations_measures'][field]['count']

                            group['stats']['violations_measures'][field]['time_sec'] += \
                                row['violations_measures'][field]['time_sec']

                        group['stats']['violations_measures'][field]['total_time_percentage'] = \
                            group['stats']['violations_measures'][field]['time_sec'] \
                            / group['stats']['total_duration'] * 100.0

                    for field in ('brakings', 'accelerations', 'turns'):
                        for row in group['rows']:
                            group['stats']['per_100km_count'][field]['total_count'] += \
                                row['per_100km_count'][field]['total_count']

                        group['stats']['per_100km_count'][field]['count'] = \
                            group['stats']['per_100km_count'][field]['total_count'] \
                            / group['stats']['total_mileage'] * 100

                    for field in (
                        'overspeed', 'belt', 'lights', 'brakings', 'accelerations', 'turns', 'jib'
                    ):
                        for row in group['rows']:
                            fine = row['rating'][field]['fine']
                            group['stats']['rating'][field]['fine'] += fine
                            group['stats']['rating_total']['avg']['fine'] += fine

                            if field in ('belt', 'lights', 'jib', 'brakings'):
                                group['stats']['rating_total']['critical_avg']['fine'] += fine

                    # расчет статистики (рейтинга)
                    for key in group['stats']['rating']:
                        scope = group['stats']['rating'][key]
                        scope['rating'] = self.calculate_rating(scope['fine'])
                    group['stats']['rating_total']['avg']['rating'] = self.calculate_rating(
                        group['stats']['rating_total']['avg']['fine']
                    )
                    group['stats']['rating_total']['critical_avg']['rating'] = \
                        self.calculate_rating(
                            group['stats']['rating_total']['critical_avg']['fine']
                        )

                total_report_data.extend(report_data)

            # финально отсортируем всю группу
            total_report_data = sorted(
                total_report_data,
                key=lambda x: x['stats']['rating_total']['critical_avg']['rating']
            )

        kwargs['report_data'] = total_report_data
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
        widths = [
            5500, 2900, 2130, 4700, 4700, 4700, 4700, 4700, 4700, 2400, 2400, 2500, 2300, 2450,
            2300, 3000, 2750, 2750, 2330, 3000, 3000
        ]

        if self.is_total:
            widths.insert(0, 5500)

        for y, width in enumerate(widths):
            worksheet.col(y).width = width

        headings = [
            'Водитель',
            'Гос №',
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
        ]

        if self.is_total:
            headings.insert(0, 'Компания')

        # header
        worksheet.write_merge(
            1, 1, 0, 17 if self.is_total else 16, 'За период: %s - %s' % (
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

        def write_row(x, group, row):
            y = 0

            if self.is_total:
                worksheet.write(
                    x, y, group['company_name'],
                    style=self.styles['border_left_style']
                )
                y += 1

            worksheet.write(
                x, y, group['driver_fio'],
                style=self.styles['border_left_style']
            )
            y += 1
            worksheet.write(
                x, y, row['unit_number'],
                style=self.styles['border_left_style']
            )
            y += 1
            worksheet.write(
                x, y, row['total_mileage'],
                style=self.styles['border_right_style']
            )
            y += 1
            worksheet.write(
                x, y, self.render_measure(row, 'avg_overspeed'),
                style=self.styles['border_left_style']
            )
            y += 1
            worksheet.write(
                x, y, self.render_measure(row, 'critical_overspeed'),
                style=self.styles['border_left_style']
            )
            y += 1
            worksheet.write(
                x, y, self.render_measure(row, 'belt'),
                style=self.styles['border_left_style']
            )
            y += 1
            worksheet.write(
                x, y, self.render_measure(row, 'lights'),
                style=self.styles['border_left_style']
            )
            y += 1
            worksheet.write(
                x, y, self.render_measure(row, 'jib'),
                style=self.styles['border_left_style']
            )
            y += 1
            worksheet.write(
                x, y, floatcomma(row['per_100km_count']['brakings']['count'], -2),
                style=self.styles['border_right_style']
            )
            y += 1
            worksheet.write(
                x, y, floatcomma(row['per_100km_count']['accelerations']['count'], -2),
                style=self.styles['border_right_style']
            )
            y += 1
            worksheet.write(
                x, y, floatcomma(row['per_100km_count']['turns']['count'], -2),
                style=self.styles['border_right_style']
            )
            y += 1
            worksheet.write(
                x, y, self.render_rating(row['rating']['overspeed']),
                style=self.render_background(row['rating']['overspeed'])
            )
            y += 1
            worksheet.write(
                x, y, self.render_rating(row['rating']['belt']),
                style=self.render_background(row['rating']['belt'])
            )
            y += 1
            worksheet.write(
                x, y, self.render_rating(row['rating']['lights']),
                style=self.render_background(row['rating']['lights'])
            )
            y += 1
            worksheet.write(
                x, y, self.render_rating(row['rating']['brakings']),
                style=self.render_background(row['rating']['brakings'])
            )
            y += 1
            worksheet.write(
                x, y, self.render_rating(row['rating']['accelerations']),
                style=self.render_background(row['rating']['accelerations'])
            )
            y += 1
            worksheet.write(
                x, y, self.render_rating(row['rating']['turns']),
                style=self.render_background(row['rating']['turns'])
            )
            y += 1
            worksheet.write(
                x, y, self.render_rating(row['rating']['jib']),
                style=self.render_background(row['rating']['jib'])
            )
            y += 1
            worksheet.write(
                x, y, self.render_rating(row['rating_total']['avg']),
                style=self.render_background(row['rating_total']['avg'])
            )
            y += 1
            worksheet.write(
                x, y, self.render_rating(row['rating_total']['critical_avg']),
                style=self.render_background(row['rating_total']['critical_avg'])
            )
            y += 1

        for group in context['report_data']:
            for row in group['rows']:
                x += 1
                write_row(x, group, row)

            if len(group['rows']) > 1 and group.get('stats'):
                x += 1
                write_row(x, group, group['stats'])

        return worksheet

    @staticmethod
    def render_rating(scope):
        return floatcomma(scope['rating'], -2)
