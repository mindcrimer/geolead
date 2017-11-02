# -*- coding: utf-8 -*-


def get_fuel_level(calibration_table, value):
    """
    Получает уровень топлива
    Таблица предварительна должна быть отсортирована по ключу "x"
    """
    row, next_row = None, None
    table_len_0 = len(calibration_table) - 1

    for i, row in enumerate(calibration_table):
        # берем подходящую строку
        if i < table_len_0:
            next_row = calibration_table[i + 1]

            if row['x'] <= value <= next_row['x']:
                break
        else:
            next_row = None

    # если вообще есть строки в таблице
    if row:
        # когда нет следующей строки, тащим формулу из последней строки
        if next_row is None:
            a, b = row['a'], row['b']

        else:
            ratio = (value - row['x']) / (next_row['x'] - row['x'])
            a = row['a'] + (ratio * (next_row['a'] - row['a']))
            b = row['b'] + (ratio * (next_row['b'] - row['b']))

        return value * a + b

    return .0
