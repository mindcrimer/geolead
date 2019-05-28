def get_siblings(qs, obj_id):
    """Извлекает предыдущий и следующий объект"""
    prev_obj, prev_obj_candidate, next_obj, next_is_next = None, None, None, False

    for obj in qs.iterator():
        if next_is_next:
            next_obj = obj
            break

        if obj.pk == obj_id:
            next_is_next = True
            prev_obj = prev_obj_candidate

        prev_obj_candidate = obj

    return prev_obj, next_obj
