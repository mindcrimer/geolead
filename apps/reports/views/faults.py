# -*- coding: utf-8 -*-
import datetime

import ujson
from django.utils.timezone import utc

from base.exceptions import ReportException
from reports import forms
from reports.utils import get_period, local_to_utc_time, cleanup_and_request_report, \
    get_wialon_report_template_id, exec_report, get_report_rows, utc_to_local_time, \
    parse_wialon_report_datetime
from reports.views.base import BaseReportView, WIALON_NOT_LOGINED, WIALON_USER_NOT_FOUND, \
    REPORT_ROW_HEIGHT
from snippets.jinjaglobals import date as date_format
from ura.models import Job
from users.models import User
from wialon.api import get_units, get_unit_settings


class FaultsView(BaseReportView):
    """Отчет о состоянии оборудования ССМТ"""
    form_class = forms.FaultsForm
    template_name = 'reports/faults.html'
    report_name = 'Отчет о состоянии оборудования ССМТ'
    xls_heading_merge = 5

    def __init__(self, *args, **kwargs):
        super(FaultsView, self).__init__(*args, **kwargs)
        self.last_data = {}
        self.report_data = None
        self.sensors_report_data = {}
        self.stats = {
            'total': set(),
            'broken': set()
        }
        # ВСЕ должен быть первым!
        self.known_sensors = (
            'ВСЕ',
            'GPS антенна',
            'Ближний свет фар',
            'Ремень',
            'Зажигание',
            'Датчик уровня топлива',
            'Напряжение АКБ'
        )
        self.unit_sensors_cache = {}
        self.user = None

    def get_default_form(self):
        data = self.request.POST if self.request.method == 'POST' else {
            'dt': (datetime.datetime.now() - datetime.timedelta(days=1))
            .replace(hour=0, minute=0, second=0, tzinfo=utc),
            'job_extra_offset': 2
        }
        return self.form_class(data)

    @staticmethod
    def get_new_grouping():
        return {
            'unit': '',
            'place': '',
            'dt': '',
            'driver_name': '',
            'sum_broken_work_time': '',
            'fault': ''
        }

    def get_context_data(self, **kwargs):
        kwargs = super(FaultsView, self).get_context_data(**kwargs)
        form = kwargs['form']
        kwargs['today'] = datetime.date.today()

        if self.request.POST:
            self.report_data = []

            if form.is_valid():
                sess_id = self.request.session.get('sid')
                if not sess_id:
                    raise ReportException(WIALON_NOT_LOGINED)

                self.user = User.objects.filter(is_active=True) \
                    .filter(wialon_username=self.request.session.get('user')).first()

                if not self.user:
                    raise ReportException(WIALON_USER_NOT_FOUND)

                report_date = form.cleaned_data['dt']
                job_extra_offset = datetime.timedelta(
                    seconds=form.cleaned_data['job_extra_offset'] * 60 * 60
                )

                units_list = get_units(sess_id=sess_id)
                units_cache = {u['id']: u['name'] for u in units_list}

                dt_from_local = datetime.datetime.combine(report_date, datetime.time(0, 0, 0))
                dt_to_local = datetime.datetime.combine(report_date, datetime.time(23, 59, 59))
                dt_from_utc = local_to_utc_time(dt_from_local, self.user.wialon_tz)
                dt_to_utc = local_to_utc_time(dt_to_local, self.user.wialon_tz)

                sensors_template_id = get_wialon_report_template_id('sensors', self.user)
                last_data_template_id = get_wialon_report_template_id('last_data', self.user)

                ura_user = self.user.ura_user if self.user.ura_user_id else self.user
                jobs = Job.objects.filter(
                    user=ura_user, date_begin__lt=dt_to_utc, date_end__gt=dt_from_utc
                ).order_by('unit_title')

                if jobs:
                    dt_from, dt_to = get_period(
                        dt_from_local, dt_to_local, self.user.wialon_tz
                    )
                    cleanup_and_request_report(self.user, last_data_template_id, sess_id=sess_id)
                    r = exec_report(
                        self.user,
                        last_data_template_id,
                        dt_from, dt_to,
                        sess_id=sess_id
                    )

                    for table_index, table_info in enumerate(r['reportResult']['tables']):
                        rows = get_report_rows(
                            self.user,
                            table_index,
                            table_info['rows'],
                            level=1,
                            sess_id=sess_id
                        )

                        if table_info['name'] == 'unit_group_location':
                            self.last_data = {r['c'][0]: r['c'][1:] for r in rows}
                            break

                print('Всего ПЛ при анализе состояния оборудования: %s' % len(jobs))
                for i, job in enumerate(jobs):
                    try:
                        unit_name = units_cache.get(int(job.unit_id))
                    except (ValueError, AttributeError, TypeError):
                        unit_name = ''

                    if not unit_name:
                        print('ТС не найден! %s' % job.unit_id)
                        continue

                    print('%s) %s' % (i, unit_name))
                    self.stats['total'].add(unit_name)

                    job_local_date_begin = utc_to_local_time(
                        job.date_begin - job_extra_offset, self.user.wialon_tz
                    )
                    job_local_date_to = utc_to_local_time(
                        job.date_end + job_extra_offset, self.user.wialon_tz
                    )
                    dt_from, dt_to = get_period(
                        job_local_date_begin, job_local_date_to, self.user.wialon_tz
                    )
                    self.sensors_report_data = {}
                    cleanup_and_request_report(self.user, sensors_template_id, sess_id=sess_id)
                    r = exec_report(
                        self.user, sensors_template_id, dt_from, dt_to,
                        sess_id=sess_id, object_id=int(job.unit_id)
                    )

                    report_tables = {}
                    for table_index, table_info in enumerate(r['reportResult']['tables']):
                        label = table_info['label'].split('(')[0].strip()

                        if table_info['name'] != 'unit_sensors_tracing':
                            continue

                        report_tables[label] = {
                            'index': table_index,
                            'rows': table_info['rows']
                        }

                    if 'ВСЕ' not in report_tables:
                        self.add_report_row(
                            job,
                            unit_name,
                            'Нет данных от блока мониторинга',
                            sensor=None
                        )
                        continue

                    has_movings = False
                    for field in self.known_sensors:
                        if field not in report_tables and field != 'ВСЕ':
                            # проверим, возможно датчик и не настроен
                            unit_sensors = self.get_unit_sensors(int(job.unit_id), sess_id=sess_id)
                            if field.lower() in unit_sensors:
                                self.add_report_row(
                                    job,
                                    unit_name,
                                    'Нет данных по датчику "%s"' % field,
                                    sensor=field
                                )
                            continue

                        # перебираем сначала более маленькие выборки, с целью ускорения работы
                        attempts = (10, 100, min(report_tables[field]['rows'], 10000))
                        for attempt, rows_limit in enumerate(attempts):

                            # таблицу ВСЕ придется взять целиком, для оценки движения
                            if field == 'ВСЕ' and attempt != len(attempts) - 1:
                                continue

                            rows = get_report_rows(
                                self.user,
                                report_tables[field]['index'],
                                rows_limit,
                                level=1,
                                sess_id=sess_id
                            )

                            data = [r['c'] for r in rows]
                            if field == 'ВСЕ':
                                try:
                                    # есть ли какое-нибудьт изменение скорости?
                                    has_movings = len(set(map(lambda x: x[4], data))) > 1
                                except IndexError:
                                    pass

                            analyze_result, values = self.analyze_sensor_data(field, data)
                            if analyze_result in (None, True):
                                if analyze_result:
                                    # все отлично, данные меняются и они есть
                                    pass

                                elif analyze_result is None:
                                    # данных никаких нет!
                                    # Снова проверяем на наличие датчика в настройках
                                    # проверим, возможно датчик и не настроен
                                    unit_sensors = self.get_unit_sensors(
                                        int(job.unit_id), sess_id=sess_id
                                    )
                                    if field != 'ВСЕ' and field.lower() in unit_sensors:
                                        self.add_report_row(
                                            job,
                                            unit_name,
                                            'Нет данных по датчику "%s"' % field,
                                            sensor=field
                                        )

                                break

                            # если в последней попытке тоже не нашел различающиеся данные
                            elif not analyze_result and attempt == len(attempts) - 1:
                                try:
                                    value = float(list(values)[0])
                                except (ValueError, TypeError, IndexError, AttributeError):
                                    value = 0

                                if field in {
                                    'Ближний свет фар', 'Ремень', 'Зажигание', 'GPS антенна'
                                }:
                                    if value == 1.0:
                                        value = 'Вкл'
                                    elif value == 0.0:
                                        value = 'Выкл'

                                # всегда включенный GPS - норма
                                if field == 'GPS антенна' and value == 'Вкл':
                                    continue

                                # всегда выключенное зажигание или свет фар
                                # для стоящей техники - норма
                                elif not has_movings and field in {
                                    'Зажигание', 'Ближний свет фар'
                                } and value == 'Выкл':
                                    continue

                                # всегда один и тот же уровень топлива для стоящей техники - норма
                                elif not has_movings and field == 'Датчик уровня топлива':
                                    continue

                                # всегда выключенный ремень для стоящей техники - норма
                                elif not has_movings and field == 'Ремень' and value == 'Выкл':
                                    continue

                                else:
                                    self.add_report_row(
                                        job,
                                        unit_name,
                                        'Датчик "%s" отправляет одинаковое '
                                        'значение (%s) в течение смены' % (field, value),
                                        sensor=field
                                    )

        self.stats['total'] = len(self.stats['total'])
        self.stats['broken'] = len(self.stats['broken'])

        kwargs.update(
            stats=self.stats,
            report_data=self.report_data
        )

        return kwargs

    def get_unit_sensors(self, unit_id, sess_id=None):
        if unit_id not in self.unit_sensors_cache:
            unit_settings = get_unit_settings(unit_id, user=self.user, sess_id=sess_id)
            sensors = unit_settings['sens']

            for sensor in sensors.values():
                sensor['c'] = ujson.loads(sensor['c'])

            sensors = list(map(
                lambda x: x['n'].lower(),
                filter(lambda s: s['c']['appear_in_popup'], sensors.values())
            ))

            self.unit_sensors_cache[unit_id] = sensors
        return self.unit_sensors_cache[unit_id]

    @staticmethod
    def analyze_sensor_data(label, data):
        """Ищем корректность датчика"""
        if label == 'GPS антенна':  # смотрим данные геолокации (GPS)
            values = set(
                filter(None, map(
                    lambda x: ('%s,%s' % (x[3]['x'], x[3]['y'])) if (
                        x[3] and isinstance(x[3], dict) and 'x' in x[3] and 'y' in x[3]
                    ) else None,
                    data
                ))
            )

        elif label == 'ВСЕ':
            values = set()
        else:
            values = set(map(lambda x: x[3], data))

        if not values:
            return None, set()

        return len(values) > 1, values

    def add_report_row(self, job, unit_name, fault, sensor=None):
        report_row = self.get_new_grouping()
        self.stats['broken'].add(unit_name)
        print(fault)

        dt = place = None
        if sensor is None:
            dt, place = self.get_last_data(unit_name)

        report_row.update(
            unit=unit_name,
            fault=fault,
            place=place,
            dt=dt,
            driver_name=job.driver_fio
        )

        if dt:
            report_row['sum_broken_work_time'] = self.get_sum_broken_work_time(
                job.unit_id,
                local_to_utc_time(dt, self.user.wialon_tz), job.date_end
            )

        self.report_data.append(report_row)

    def get_last_data(self, unit_name):
        data = self.last_data.get(unit_name)
        if data and len(data) > 1:
            dt, place = data[0], data[2]

            if isinstance(dt, dict):
                dt = datetime.datetime.utcfromtimestamp(dt['v'])
                dt = utc_to_local_time(dt, self.user.wialon_tz)
            else:
                dt = parse_wialon_report_datetime(dt)

            if isinstance(place, dict) and 't' in place:
                place = place['t']

            return dt, place

        return None, None

    def get_sum_broken_work_time(self, unit_id, dt_from, dt_to):
        if not dt_from or not dt_to:
            return None

        sum_broken_work_time = 0
        ura_user = self.user.ura_user if self.user.ura_user_id else self.user
        jobs = Job.objects.filter(
            user=ura_user, unit_id=unit_id, date_begin__lt=dt_to, date_end__gt=dt_from
        )

        for job in jobs:
            intersects_period = max(dt_from, job.date_begin), min(dt_to, job.date_end)
            sum_broken_work_time += (intersects_period[1] - intersects_period[0]).total_seconds()

        if sum_broken_work_time:
            return round(sum_broken_work_time / 3600.0, 2)

    def write_xls_data(self, worksheet, context):
        worksheet = super(FaultsView, self).write_xls_data(worksheet, context)
        worksheet.set_portrait(False)
        worksheet.set_print_scaling(80)

        for col in range(4):
            worksheet.col(col).width = 6000
        worksheet.col(1).width = 10000
        worksheet.col(2).width = 4800
        worksheet.col(4).width = 4200
        worksheet.col(5).width = 10000

        # header
        worksheet.write_merge(
            1, 1, 0, 3, 'На дату: %s' % date_format(context['cleaned_data']['dt'], 'd.m.Y'),
        )

        worksheet.write_merge(
            2, 2, 0, 1, 'ФИО ответственного за устранение неполадок:',
            style=self.styles['left_center_style']
        )

        worksheet.write_merge(2, 2, 2, 5, '', style=self.styles['bottom_border_style'])

        worksheet.write_merge(
            3, 3, 0, 5,
            'Всего оборудованных транспортных объектов ССМТ: %s' % context['stats']['total'],
            style=self.styles['right_center_style']
        )

        worksheet.write_merge(
            4, 4, 0, 5, 'Из них*: исправных %s\nВозможно неисправных %s' % (
                context['stats']['total'] - context['stats']['broken'],
                context['stats']['broken'],
            ),
            style=self.styles['right_center_style']
        )

        # head
        worksheet.write_merge(5, 6, 0, 0, ' Гос№ ТС', style=self.styles['border_center_style'])
        worksheet.write_merge(
            5, 5, 1, 2, ' Последняя полученная информация',
            style=self.styles['border_center_style']
        )
        worksheet.write_merge(
            5, 6, 3, 3, ' ФИО водителя', style=self.styles['border_center_style']
        )
        worksheet.write_merge(
            5, 6, 4, 4, ' Суммарное\nнеисправное\nрабочее время, ч',
            style=self.styles['border_center_style']
        )
        worksheet.write_merge(
            5, 6, 5, 5, ' Наименование возможно\nнеисправного оборудования (ДУТ, ...)',
            style=self.styles['border_center_style']
        )
        worksheet.write(6, 1, ' Место/геозона', style=self.styles['border_center_style'])
        worksheet.write(6, 2, ' Время', style=self.styles['border_center_style'])

        for i in range(6):
            worksheet.write(7, i, str(i + 1), style=self.styles['border_center_style'])

        for i in range(1, 8):
            worksheet.row(i).height = REPORT_ROW_HEIGHT
        worksheet.row(5).height = REPORT_ROW_HEIGHT + 100
        worksheet.row(6).height = REPORT_ROW_HEIGHT + 100
        worksheet.row(4).height = REPORT_ROW_HEIGHT * 2

        # body
        i = 8
        for row in context['report_data']:
            worksheet.write(i, 0, row['unit'], style=self.styles['border_left_style'])
            worksheet.write(i, 1, row['place'], style=self.styles['border_left_style'])
            worksheet.write(
                i, 2, date_format(row['dt'], 'Y-m-d H:i:s'), style=self.styles['border_left_style']
            )
            worksheet.write(i, 3, row['driver_name'], style=self.styles['border_left_style'])
            worksheet.write(
                i, 4, row['sum_broken_work_time'], style=self.styles['border_right_style']
            )
            worksheet.write(i, 5, row['fault'], style=self.styles['border_left_style'])
            worksheet.row(i).height = 780
            worksheet.row(i).height_mismatch = True
            i += 1

        worksheet.write_merge(
            i, i, 0, 5,
            '''
*Состояния:
- исправное - передача данных с датчиков и блока (трекера) осуществляется без затруднений;
- неисправное - отсутствует передача данных с блока (трекера) или датчиков (веса, ДУТ, ...) 
в течение смены.
''',
            style=self.styles['left_center_style']
        )
        worksheet.row(i).height = 520 * 3

        return worksheet
