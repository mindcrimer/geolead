import datetime
import traceback
from collections import OrderedDict

from django.db.models import Prefetch, Q

from base.exceptions import ReportException, APIProcessError
from reports import forms
from reports.utils import local_to_utc_time, cleanup_and_request_report, \
    get_wialon_report_template_id, exec_report, get_report_rows
from reports.views.base import BaseVchmReportView, WIALON_NOT_LOGINED, WIALON_USER_NOT_FOUND
from snippets.utils.email import send_trigger_email
from ura.models import StandardJobTemplate, StandardPoint, Job, JobPoint
from users.models import User
from wialon.api import get_units, get_routes
from wialon.exceptions import WialonException


class VchmIdleTimesView(BaseVchmReportView):
    """Отчет по простоям за смену"""
    form_class = forms.VchmIdleTimesForm
    template_name = 'reports/vchm_idle_times.html'
    report_name = 'Отчет по простоям за смену'
    xls_heading_merge = 11

    def __init__(self, *args, **kwargs):
        super(VchmIdleTimesView, self).__init__(*args, **kwargs)
        self.units_dict = {}

    def get_default_form(self):
        data = self.request.POST if self.request.method == 'POST' else {
            'dt_from': datetime.date.today() - datetime.timedelta(days=1),
            'dt_to': datetime.date.today() - datetime.timedelta(days=1),
            'default_total_time_standard': 3,
            'default_parking_time_standard': 3
        }
        return self.form_class(data)

    @staticmethod
    def get_new_grouping():
        return {
            'driver_fio': '',
            'car_number': '',
            'car_vin': '',
            'car_type': '',
            'route_name': '',
            'point_name': '',
            'parking_time': '',
            'off_motor_time': '',
            'idle_time': '',
            'gpm_time': '',
            'address': '',
            'overstatement': ''
        }

    def get_car_number(self, unit_id):
        return self.units_dict.get(int(unit_id), {}).get('number', '')

    def get_car_vin(self, unit_id):
        return self.units_dict.get(int(unit_id), {}).get('vin', '')

    def get_car_type(self, unit_id):
        return self.units_dict.get(int(unit_id), {}).get('vehicle_type', '')

    @staticmethod
    def get_geozones_report_template_id(user):
        report_template_id = get_wialon_report_template_id('geozones', user)
        if report_template_id is None:
            raise APIProcessError(
                'Не указан ID шаблона отчета по геозонам у текущего пользователя',
                code='geozones_report_not_found'
            )
        return report_template_id

    @staticmethod
    def prepare_geozones_visits(user, geozones_report_data, dt_from, dt_to):
        # удаляем лишнее
        geozones_report_data['unit_zones_visit'] = tuple(map(
            lambda x: x['c'], geozones_report_data['unit_zones_visit']
        ))

        # пробегаемся по интервалам геозон и сглаживаем их
        unit_zones_visit = []
        for i, row in enumerate(geozones_report_data['unit_zones_visit']):
            if isinstance(row[2], str):
                # если конец участка неизвестен, считаем, что конец участка - конец периода запроса
                row[2] = {'v': dt_to}

            geozone_name = row[0]['t'] if isinstance(row[0], dict) else row[0]
            try:
                row = {
                    'name': geozone_name.strip(),
                    'time_in': row[1]['v'],
                    'time_out': row[2]['v']
                }
            except (IndexError, KeyError, ValueError, AttributeError) as e:
                send_trigger_email(
                    'Нет необходимого атрибута v в результате', extra_data={
                        'Exception': str(e),
                        'Traceback': traceback.format_exc(),
                        'row': row,
                        'user': user
                    }
                )

            # проверим интервалы между отрезками
            try:
                previous_geozone = unit_zones_visit[-1]
                # если время входа в текущую не превышает 1 минуту выхода из предыдущей
                delta = row['time_in'] - previous_geozone['time_out']
                if delta < 60:
                    # если имена совпадают
                    if row['name'] == previous_geozone['name']:
                        # тогда прибавим к предыдущей геозоне
                        previous_geozone['time_out'] = row['time_out']
                        continue
                    else:
                        # или же просто предыдущей точке удлиняем время выхода (или усреднять?)
                        previous_geozone['time_out'] = row['time_in']

                    # если же объект вылетел из геозоны в другую менее чем на 1 минуту
                    # (то есть проехал в текущей геозоне менее 1 минуты) - списываем на помехи
                    if row['time_out'] - row['time_in'] < 60:
                        # и при этом в дальнейшем вернется в предыдущую:
                        try:
                            next_geozone = geozones_report_data['unit_zones_visit'][i + 1]
                            if next_geozone[0].strip() == previous_geozone['name']:
                                # то игнорируем текущую геозону, будто ее и не было,
                                # расширив по диапазону времени предыдущую
                                previous_geozone['time_out'] = row['time_out']
                                continue
                        except IndexError:
                            pass

            except IndexError:
                pass

            unit_zones_visit.append(row)

        if unit_zones_visit:
            # обработаем концевые участки: сигнал с объекта мог не успеть прийти в начале
            # и конце диапазона запроса, поэтому если сигнал не приходил в приемлимое время
            # (3 минуты), считаем, что объект там и находился
            delta = 60 * 3
            if unit_zones_visit[0]['time_in'] - dt_from < delta:
                unit_zones_visit[0]['time_in'] = dt_from

            if dt_to - unit_zones_visit[-1]['time_out'] < delta:
                unit_zones_visit[-1]['time_out'] = dt_to

        return unit_zones_visit

    def get_context_data(self, **kwargs):
        kwargs = super(VchmIdleTimesView, self).get_context_data(**kwargs)
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

        if self.request.POST:

            if form.is_valid():
                report_data = []
                geozones_report_data = {
                    'unit_chronology': [],
                    'unit_digital_sensors': [],
                    'unit_engine_hours': [],
                    'unit_zones_visit': []
                }

                user = User.objects.filter(is_active=True) \
                    .filter(wialon_username=self.request.session.get('user')).first()
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

                routes = {
                    x['id']: x for x in get_routes(sess_id=sess_id, user=user, with_points=True)
                }
                self.units_dict = OrderedDict((x['id'], x) for x in units_list)

                standard_job_templates = StandardJobTemplate.objects \
                    .filter(wialon_id__in=[str(x) for x in routes.keys()]) \
                    .prefetch_related(
                        Prefetch(
                            'points',
                            StandardPoint.objects.filter(
                                Q(total_time_standard__isnull=False) |
                                Q(parking_time_standard__isnull=False)
                            ),
                            'points_cache'
                        )
                    )

                standards = {
                    int(x.wialon_id): {
                        'space_overstatements_standard': x.space_overstatements_standard
                        if x.space_overstatements_standard is not None else None,
                        'points': {
                            p.title: {
                                'total_time_standard': p.total_time_standard
                                if p.total_time_standard is not None else None,
                                'parking_time_standard': p.parking_time_standard
                                if p.parking_time_standard is not None else None
                            } for p in x.points_cache
                        }
                    } for x in standard_job_templates
                    if x.space_overstatements_standard is not None or x.points_cache
                }

                ura_user = user.ura_user if user.ura_user_id else user
                jobs = Job.objects\
                    .filter(user=ura_user, date_begin__gte=dt_from, date_end__lte=dt_to)\
                    .order_by('date_begin', 'date_end')
                jobs_cache = {int(j.unit_id): j for j in jobs}

                normal_ratio = 1 + (form.cleaned_data['overstatement_param'] / 100.0)

                total_count = len(units_list)
                i = 0
                for unit in units_list:
                    i += 1
                    print('%s/%s: %s' % (i, total_count, unit['name']))
                    job = jobs_cache.get(unit['id'])
                    standard = None
                    if job:
                        standard = standards.get(int(job.route_id))

                    report_template_id = self.get_geozones_report_template_id(user)
                    cleanup_and_request_report(
                        user, report_template_id, item_id=unit['id'], sess_id=sess_id
                    )

                    try:
                        r = exec_report(
                            user,
                            report_template_id,
                            dt_from,
                            dt_to,
                            object_id=unit['id'],
                            sess_id=sess_id
                        )
                    except ReportException as e:
                        raise WialonException(
                            'Не удалось получить в Wialon отчет о поездках: %s' % e
                        )

                    for table_index, table_info in enumerate(r['reportResult']['tables']):
                        if table_info['name'] not in geozones_report_data:
                            continue

                        try:
                            geozones_report_data[table_info['name']] = get_report_rows(
                                user,
                                table_index,
                                table_info['rows'],
                                level=1,
                                sess_id=sess_id
                            )

                        except ReportException as e:
                            raise WialonException(
                                'Не удалось получить в Wialon отчет о поездках.'
                                'Исходная ошибка: %s' % e
                            )
                    unit_zones_visits = self.prepare_geozones_visits(
                        user, geozones_report_data, dt_from, dt_to
                    )

                    for point in unit_zones_visits:
                        point_standard = None
                        if standard:
                            point_standard = standard.get('points', {}).get(point['name'])

                        if not point_standard:
                            point_standard = {
                                'total_time_standard': form.cleaned_data.get(
                                    'default_total_time_standard', 3
                                ),
                                'parking_time_standard': form.cleaned_data.get(
                                    'default_parking_time_standard', 3
                                )
                            }
                        total_standart, parking_standard = point_standard['total_time_standard'],\
                            point_standard['parking_time_standard']

                        overstatement = .0
                        total_time = (point['time_out'] - point['time_in']).total_seconds() / 60.0
                        if total_standart is not None \
                                and total_time / total_standart > normal_ratio:
                            overstatement += total_time - total_standart

                        parking_time = point.parking_time / 60.0
                        if parking_standard is not None \
                                and parking_time / parking_standard > normal_ratio:
                            overstatement += parking_time - parking_standard

                        if overstatement > .0:
                            row = self.get_new_grouping()
                            row['driver_fio'] = job.driver_fio \
                                if job and job.driver_fio else 'Неизвестный'
                            row['car_number'] = self.get_car_number(unit['id'])
                            row['car_vin'] = self.get_car_vin(unit['id'])
                            row['car_type'] = self.get_car_type(unit['id'])
                            row['route_name'] = job.route_title \
                                if job and job.route_title else 'Неизвестный маршрут'
                            row['point_name'] = point['name'] \
                                if point['name'] and point['name'].lower() != 'space'\
                                else 'Неизвестная'

                            row['parking_time'] = .0
                            row['off_motor_time'] = .0
                            row['idle_time'] = .0
                            row['gpm_time'] = .0
                            row['address'] = ''

                            row['overstatement'] = round(overstatement / 60.0, 2) \
                                if overstatement > 1.0 else round(overstatement / 60.0, 4)

                            report_data.append(row)

            kwargs.update(
                report_data=report_data,
            )

        return kwargs

    def write_xls_data(self, worksheet, context):
        worksheet = super(VchmIdleTimesView, self).write_xls_data(worksheet, context)

        worksheet.col(0).width = 5000
        worksheet.col(1).width = 5000
        worksheet.col(2).width = 5000
        worksheet.col(3).width = 5000
        worksheet.col(4).width = 5000
        worksheet.col(5).width = 5000
        worksheet.col(6).width = 5000
        worksheet.col(7).width = 5000
        worksheet.col(8).width = 5000
        worksheet.col(9).width = 5000
        worksheet.col(10).width = 5000
        worksheet.col(11).width = 5000

        headings = (
            'Водитель',
            'Гос №',
            'VIN',
            'Тип ТС',
            'Название маршрута',
            'Название геозоны',
            'Время остановки, чч:мм',
            'Время с выключенным двигателем, чч:мм',
            'Время на холостом ходу (без работы), чч:мм',
            'Время работы ГПМ, чч:мм',
            'Место остановки (адрес или км трассы)',
            'Время простоя сверх норматива*, чч:мм'
        )

        x = 1
        for y, heading in enumerate(headings):
            worksheet.write(
                x, y, heading, style=self.styles['border_center_style']
            )

        worksheet.row(x).height = 900

        worksheet.write_merge(x, x, 0, 11, 'В процессе реализации')

        for row in context['report_data']:
            x += 1

        return worksheet
