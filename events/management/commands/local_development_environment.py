from django.core.management.base import BaseCommand, CommandError
from django.core.management import call_command
from django.conf import settings


class Command(BaseCommand):
    def handle(self, *args, **options):
        if settings.DEBUG is not True:
            raise CommandError('This command can be run only when DEBUG is True')

        # Apply database migrations
        call_command('migrate')

        # Syncronize languages for translations in database
        call_command('sync_translation_fields', '--noinput')

        # Start django server
        call_command('runserver', '0.0.0.0:8000')
