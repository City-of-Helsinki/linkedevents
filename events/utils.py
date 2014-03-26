import re


def convert_to_camelcase(s):
    return ''.join(word.title() if i else word for i, word in enumerate(
        s.split('_')))


def convert_from_camelcase(s):
    return re.sub(r'(^|[a-z])([A-Z])',
                  lambda m: '_'.join([i.lower() for i in m.groups() if i]), s)


def get_value_from_tuple_list(list_of_tuples, search_key, value_index):
    """
    Find "value" from list of tuples by using the other value in tuple as a
    search key and other as a returned value
    :param list_of_tuples: tuples to be searched
    :param search_key: search key used to find right tuple
    :param value_index: Index telling which side of tuple is
                        returned and which is used as a key
    :return: Value from either side of tuple
    """
    for i, v in enumerate(list_of_tuples):
        if v[value_index ^ 1] == search_key:
            return v[value_index]
