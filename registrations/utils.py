from django.conf import settings
from django.core.mail import EmailMultiAlternatives, get_connection


def code_validity_duration(seats):
    return settings.SEAT_RESERVATION_DURATION + seats


def send_mass_html_mail(
    datatuple,
    fail_silently=False,
    auth_user=None,
    auth_password=None,
    connection=None,
):
    """
    django.core.mail.send_mass_mail doesn't support sending html mails,

    This method duplicates send_mass_mail except requires html_message for each message
    and adds html alternative to each mail
    """
    connection = connection or get_connection(
        username=auth_user,
        password=auth_password,
        fail_silently=fail_silently,
    )
    messages = []
    for subject, message, html_message, from_email, recipient_list in datatuple:
        mail = EmailMultiAlternatives(
            subject, message, from_email, recipient_list, connection=connection
        )
        mail.attach_alternative(html_message, "text/html")
        messages.append(mail)

    return connection.send_messages(messages)
