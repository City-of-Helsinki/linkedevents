from django.core import mail


def assert_invitation_email_is_sent(email, event_name):
    assert mail.outbox[0].to[0] == email
    assert mail.outbox[0].subject.startswith("Oikeudet myönnetty osallistujalistaan")
    assert (
        f"Sähköpostiosoitteelle <strong>{email}</strong> on myönnetty oikeudet lukea "
        f"tapahtuman <strong>{event_name}</strong> osallistujalista."
        in str(mail.outbox[0].alternatives[0])
    )
