import hashlib

hash_length = 128


def _pseudonymize(text, secret):
    """Pseudonymize a `text` using `secret`."""
    result = []
    # hexdigest returns 128 character long string so call in multiple times for a long text
    for start in range(0, len(text), hash_length):
        block = text[start : start + hash_length]
        # Create a hash object using SHA-512 algorithm
        hash_object = hashlib.sha512()
        # Update the hash object with a secret
        hash_object.update(secret.encode("utf-8"))
        # Update the hash object with a message
        hash_object.update(block.encode("utf-8"))

        result.append(hash_object.hexdigest())

    return "".join(result)


def string(value, secret, size=None):
    """Pseudonymize as string."""
    if not value:
        return value
    if size is None:
        size = len(value)

    result = _pseudonymize(value, secret)

    return result[0:size]


def integer(value, secret, size=None):
    if not value and value != 0:
        return value
    if size is None:
        size = len(str(value))

    value = string(str(value), secret, size)
    result = ""

    for char in value:
        try:
            result += str(int(char))
        except ValueError:
            result += str(ord(char))[-1]

    return int(result[:size])


def text(value, secret, size=None):
    """Pseudonymize text. Contains letter, numbers and spaces."""
    if not value:
        return value

    return string(value, secret, size).replace(".", " ")


def name(value, secret, size=None):
    """A name is a text which has only one capital letter as the first one."""
    if not value:
        return value

    return text(value, secret, size).capitalize()


def street(value, secret):
    """A street is a name (maybe containing spaces) followed by a number."""
    if not value:
        return value

    source_name, sep, source_number = value.rpartition(" ")
    if not source_name:
        source_name = source_number
        source_number = ""

    return sep.join([name(source_name, secret), str(integer(source_number, secret))])


def email(value, secret):
    """Return something what could be an e-mail address."""
    if not value:
        return value

    local, at, domain = value.partition("@")

    return "{}{}{}.fi".format(
        string(local, secret, len(local)).lower(),
        at,
        string(domain, secret, len(domain) - 3).lower(),
    )


def phone(value, secret, size=None):
    if not value:
        return value

    return ("0%s" % integer(value.replace(" ", ""), secret, size))[:-1]


def day(value, secret, size=None):
    if not value:
        return value

    day = integer(value, secret)
    if day > 28:
        day = int(day / 4)

    return max(day, 1)


def month(value, secret, size=None):
    if not value:
        return value

    month = integer(value, secret)
    if month > 12:
        month = int(month / 8)

    return max(month, 1)


def year(value, secret):
    if not value:
        return value

    year = integer(value, secret)
    if year < 1900:
        year = year + 1900

    return year


def datestring(value, secret, format="YYYY-MM-DD"):
    """Date represended as a string.

    Parts of the date which are 0 are kept zero. (e. g. if the day is '00'
    it is not pseudonymized)

    """
    if not value:
        return value

    for part, length, func in (("D", 2, day), ("M", 2, month), ("Y", 4, year)):
        assert format.count(part) == length
        start_pos = format.find(part)
        end_pos = start_pos + length
        val = value[start_pos:end_pos]

        if val != "0" * length:
            replacement = str(func("".join(val), secret)).zfill(length)
            value = f"{value[:start_pos]}{replacement}{value[end_pos:]}"

    return value
