def move_list_element_to_front(arr, element):
    """Передвигает элемент списка в начало"""
    arr.insert(0, arr.pop(arr.index(element)))


def move_list_element_to_end(arr, element):
    """Передвигает элемент списка в конец"""
    arr.insert(len(arr), arr.pop(arr.index(element)))
