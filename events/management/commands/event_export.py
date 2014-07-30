import os
from optparse import make_option
from django.conf import settings
from django.core.management.base import BaseCommand, CommandError
from django.utils.translation import activate, get_language

from events.exporter.base import get_exporters


class Command(BaseCommand):
    args = '<module>'
    help = "Export event data"
    option_list = list(BaseCommand.option_list + (
        make_option('--new', action='store_true', dest='new',
                    help='Export entities added after last export date'),
        make_option('--delete', action='store_true', dest='delete',
                    help='Delete exported items from target system'),
    ))

    exporter_types = ['events']

    def __init__(self):
        super(Command, self).__init__()
        for imp in self.exporter_types:
            opt = make_option('--%s' % imp, dest=imp, action='store_true',
                              help='export %s' % imp)
            self.option_list.append(opt)

    def handle(self, *args, **options):
        importers = get_exporters()
        imp_list = ', '.join(sorted(importers.keys()))
        if len(args) != 1:
            raise CommandError(
                "Enter the name of the event exporter module. "
                "Valid exporters: %s" % imp_list)
        if not args[0] in importers:
            raise CommandError("Exporter %s not found. Valid exporters: %s"
                               % (args[0], imp_list))
        imp_class = importers[args[0]]

        if hasattr(settings, 'PROJECT_ROOT'):
            root_dir = settings.PROJECT_ROOT
        else:
            root_dir = settings.BASE_DIR
        exporter = imp_class()

        # Activate the default language for the duration of the import
        # to make sure translated fields are populated correctly.
        old_lang = get_language()
        activate(settings.LANGUAGES[0][0])

        for imp_type in self.exporter_types:
            name = "export_%s" % imp_type
            method = getattr(exporter, name, None)
            if options[imp_type]:
                if not method:
                    raise CommandError(
                        "Exporter %s does not support exporter %s"
                        % (name, imp_type))
            else:
                if not options['new'] and not options['delete']:
                    continue

            if method:
                method(is_delete=(True if options['delete'] else False))

        activate(old_lang)
