from django.core.management.base import BaseCommand, CommandError
from django.core.management import call_command
from django.conf import settings


class Command(BaseCommand):
    help = 'Setup all data needed for boostrapping a Helsinki specific installation'

    def handle(self, *args, **options):
        if settings.DEBUG is not True:
            raise CommandError('This command can be run only when DEBUG is True')

        # Import general Finnish ontology (used by Helsinki UI and Helsinki events)
        call_command('event_import', 'yso', '--all')

        # Add keyword set to display in the UI event audience selection
        call_command('add_helsinki_audience')

        # Add keyword set to display in the UI main category selection
        call_command('add_helfi_topics')

        # Import places from Helsinki metropolitan region service registry (used by events from following sources)
        call_command('event_import', 'tprek', '--places')

        # Import places from Helsinki metropolitan region address registry (used as fallback locations)
        call_command('event_import', 'osoite', '--places')

        # Import events from Helsinki metropolitan region libraries
        call_command('event_import', 'helmet', '--events')

        # Import events from Espoo
        call_command('event_import', 'espoo', '--events')

        # Import City of Helsinki internal organization for UI user rights management
        call_command('import_organizations', 'https://api.hel.fi/paatos/v1/organization/', '-s', 'helsinki:ahjo')

        # Install API frontend templates
        call_command('install_templates', 'helevents')

        # Import municipalities in Finland (if you want to use district based API filtering of events)
        call_command('geo_import', 'finland', '--municipalities')

        # Import districts in Helsinki (if you want to use district based API filtering of events)
        call_command('geo_import', 'helsinki', '--divisions')

        self.stdout.write(self.style.SUCCESS('Helsinki setup completed successfully'))
