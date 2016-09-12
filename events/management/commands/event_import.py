import os
from optparse import make_option
from django.conf import settings
from django.core.management.base import BaseCommand, CommandError
from django.utils.translation import activate, get_language

from events.importer.base import get_importers


class Command(BaseCommand):
    help = "Import event data"

    importer_types = ['places', 'events', 'keywords']

    def __init__(self):
        super().__init__()
        self.importers = get_importers()
        self.imp_list = ', '.join(sorted(self.importers.keys()))
        self.missing_args_message = "Enter the name of the event importer module. Valid importers: %s" % self.imp_list

    def add_arguments(self, parser):
        parser.add_argument('module')
        parser.add_argument('--all', action='store_true', dest='all', help='Import all entities')
        parser.add_argument('--cached', action='store_true', dest='cached', help='Cache requests (if possible)')
        parser.add_argument('--single', action='store', dest='single', help='Import only single entity')

        for imp in self.importer_types:
            parser.add_argument('--%s' % imp, dest=imp, action='store_true', help='import %s' % imp)

    def handle(self, *args, **options):
        module = options['module']
        if not module in self.importers:
            raise CommandError("Importer %s not found. Valid importers: %s" % (module, self.imp_list))
        imp_class = self.importers[module]

        if hasattr(settings, 'PROJECT_ROOT'):
            root_dir = settings.PROJECT_ROOT
        else:
            root_dir = settings.BASE_DIR
        importer = imp_class({'data_path': os.path.join(root_dir, 'data'),
                              'verbosity': int(options['verbosity']),
                              'cached': options['cached'],
                              'single': options['single']})

        # Activate the default language for the duration of the import
        # to make sure translated fields are populated correctly.
        old_lang = get_language()
        activate(settings.LANGUAGES[0][0])

        for imp_type in self.importer_types:
            name = "import_%s" % imp_type
            method = getattr(importer, name, None)
            if options[imp_type]:
                if not method:
                    raise CommandError("Importer %s does not support importing %s" % (name, imp_type))
            else:
                if not options['all']:
                    continue

            if method:
                method()

        activate(old_lang)
