import os
from optparse import make_option
from django.conf import settings
from django.core.management.base import BaseCommand, CommandError
from django.utils.translation import activate, get_language

from events.exporter.base import get_exporters


class Command(BaseCommand):
    help = "Export event data"

    exporter_types = ['events']

    def __init__(self):
        super().__init__()
        self.exporters = get_exporters()
        self.exp_list = ', '.join(sorted(self.exporters.keys()))
        self.missing_args_message = "Enter the name of the event exporter module. Valid exporters: %s" % self.exp_list

    def add_arguments(self, parser):
        parser.add_argument('module')
        parser.add_argument('--new', action='store_true', dest='new',
                            help='Export entities added after last export date')
        parser.add_argument('--delete', action='store_true', dest='delete',
                            help='Delete exported items from target system')
        for exp in self.exporter_types:
            parser.add_argument('--%s' % exp, dest=exp, action='store_true', help='export %s' % exp)

    def handle(self, *args, **options):
        module = options['module']
        if not module in self.exporters:
            raise CommandError("Exporter %s not found. Valid exporters: %s" % (module, self.exp_list))
        exp_class = self.exporters[module]

        if hasattr(settings, 'PROJECT_ROOT'):
            root_dir = settings.PROJECT_ROOT
        else:
            root_dir = settings.BASE_DIR
        exporter = exp_class()

        # Activate the default language for the duration of the export
        # to make sure translated fields are populated correctly.
        old_lang = get_language()
        activate(settings.LANGUAGES[0][0])

        for exp_type in self.exporter_types:
            name = "export_%s" % exp_type
            method = getattr(exporter, name, None)
            if options[exp_type]:
                if not method:
                    raise CommandError(
                        "Exporter %s does not support exporter %s"
                        % (name, exp_type))
            else:
                if not options['new'] and not options['delete']:
                    continue

            if method:
                method(is_delete=(True if options['delete'] else False))

        activate(old_lang)
