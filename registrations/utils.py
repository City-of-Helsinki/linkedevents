from django.conf import settings


def code_validity_duration(seats):
    return settings.SEAT_RESERVATION_DURATION + seats
