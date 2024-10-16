import os
from pathlib import Path

from django.conf import settings
from django.core.management.base import BaseCommand, CommandError
from django.utils import translation

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

        method_name = "generate_documentation_md"
        if not (doc_gen_method := getattr(importer, method_name, None)):
            raise CommandError(
                "Importer {} does not support documentation generation".format(
                    importer.name
                )
            )

        # Ensure translated fields are populated correctly.
        with translation.override(settings.LANGUAGES[0][0]):
            doc_str = doc_gen_method()

        if output_path := options["output_file"]:
            Path(output_path).write_text(doc_str)
        else:
            print(doc_str)  # noqa: T201
