from collections import OrderedDict

from django.utils.translation import ugettext_lazy as _

from snippets.models import BaseEnumerate


class IconEnum(BaseEnumerate):
    """Перечисление медицинских иконок"""
    ANTIBIOTIC = 'antibiotic'
    BACTERIA = 'bacteria'
    BRACES = 'braces'
    CARDIOGRAM = 'cardiogram'
    DENTAL_DRILL = 'dental-drill'
    DENTAL_PIN = 'dental-pin'
    ELECTRIC_TOOTHBRUSH = 'electric-toothbrush'
    IMPLANTS = 'implants'
    MEDICAL_RECORDS = 'medical-records'
    MIRROR = 'mirror'
    MOLAR = 'molar'
    MOLAR_1 = 'molar-1'
    MOLAR_2 = 'molar-2'
    MOLAR_CROWN = 'molar-crown'
    PERIODONTAL_SCALER = 'periodontal-scaler'
    PREMOLAR = 'premolar'
    RECORDS = 'records'
    RECORDS_1 = 'records-1'
    SEARCH = 'search'
    TEETH = 'teeth'
    TOOTH = 'tooth'
    TOOTH_1 = 'tooth-1'
    TWEEZERS = 'tweezers'
    VIRUS = 'virus'
    X_RAY = 'x-ray'

    values = OrderedDict((
        (ANTIBIOTIC, _('Антибиотик')),
        (BACTERIA, _('Бактерия')),
        (BRACES, _('Брекеты')),
        (DENTAL_DRILL, _('Бормашина')),
        (VIRUS, _('Вирус')),
        (MEDICAL_RECORDS, _('Врачебная запись')),
        (RECORDS, _('Диагностика 1')),
        (RECORDS_1, _('Диагностика 2')),
        (MIRROR, _('Зеркало')),
        (TEETH, _('Зуб, пломба')),
        (TOOTH, _('Зуб, блеск')),
        (TOOTH_1, _('Зуб в разрезе')),
        (DENTAL_PIN, _('Зубы и штифт')),
        (IMPLANTS, _('Имплант')),
        (CARDIOGRAM, _('Кардиограмма')),
        (MOLAR_CROWN, _('Коронка')),
        (MOLAR, _('Коренной, бормашина')),
        (MOLAR_1, _('Коренной, крупно')),
        (MOLAR_2, _('Корренной, мелко, с десной')),
        (PREMOLAR, _('Малый коренной')),
        (TWEEZERS, _('Пинцет')),
        (SEARCH, _('Поиск, лупа')),
        (X_RAY, _('Рентген')),
        (PERIODONTAL_SCALER, _('Скалер')),
        (ELECTRIC_TOOTHBRUSH, _('Электрическая зубная щетка')),
    ))


class TextAlignEnum(BaseEnumerate):
    LEFT = 'left'
    CENTER = 'center'
    RIGHT = 'right'
    JUSTIFY = 'justify'

    values = OrderedDict((
        (LEFT, _('По левому краю')),
        (CENTER, _('По центру')),
        (RIGHT, _('По правому краю')),
        (JUSTIFY, _('Растянуть по обоим краям'))
    ))
