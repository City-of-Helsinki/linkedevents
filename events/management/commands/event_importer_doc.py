import os

from django.conf import settings
from django.core.management.base import BaseCommand, CommandError
from django.utils.translation import activate

from events.importer.base import get_importers


class Command(BaseCommand):
    help = "Generate event importer documentation"

    def __init__(self):
        super().__init__()
        self.importers = get_importers()
        self.imp_list = ", ".join(sorted(self.importers.keys()))
        self.missing_args_message = (
            "Enter the name of the event importer module. Valid importers: {}".format(
                self.imp_list
            )
        )

    def add_arguments(self, parser):
        parser.add_argument("module")
        parser.add_argument(
            "--output-file",
            action="store",
            dest="output_file",
            help="Write output to a file, not to STDOUT.",
        )

    def handle(self, *args, **options):
        module = options["module"]
        if module not in self.importers:
            raise CommandError(
                "Importer %s not found. Valid importers: %s" % (module, self.imp_list)
            )
        imp_class = self.importers[module]

        if hasattr(settings, "PROJECT_ROOT"):
            root_dir = settings.PROJECT_ROOT
        else:
            root_dir = settings.BASE_DIR
        importer = imp_class(
            {
                "data_path": os.path.join(root_dir, "data"),
                "verbosity": int(options["verbosity"]),
                "generate_docs": True,
            }
        )

        # Activate the default language
        # to make sure translated fields are populated correctly.
        activate(settings.LANGUAGES[0][0])

        name = "generate_documentation_md"
        method = getattr(importer, name, None)
        if not method:
            raise CommandError(
                "Importer {} does not support documentation generation".format(
                    importer.name
                )
            )

        method(options["output_file"])
