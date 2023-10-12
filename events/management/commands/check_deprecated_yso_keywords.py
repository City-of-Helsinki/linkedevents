from django.core.management.base import BaseCommand, CommandError
from django.db import transaction

from events.importer import yso
from events.models import Keyword


class DryRun(Exception):
    pass


class Command(BaseCommand):
    help = "Check replacements of deprecated keywords."

    def add_arguments(self, parser):
        parser.add_argument(
            "--apply",
            action="store_true",
            help="Apply changes",
        )

    def handle(self, **options):
        apply = options["apply"]
        importer = yso.YsoImporter({})
        importer.setup()
        self.stdout.write("Loading graph into memory, this can take a while..")
        graph = importer.load_graph_into_memory(yso.URL)
        deprecated_keywords_without_replacement = Keyword.objects.filter(
            data_source=importer.data_source, deprecated=True, replaced_by__isnull=True
        )

        self.stdout.write(
            f"Found {len(deprecated_keywords_without_replacement)} deprecated keywords without replacements"
        )
        if len(deprecated_keywords_without_replacement) == 0:
            self.stdout.write(self.style.SUCCESS("ALl good, nothing to do!"))
            return

        replacements = []
        missing_replacements = []
        self.stdout.write("Finding replacements..")
        for keyword in deprecated_keywords_without_replacement:
            subject = yso.get_subject(keyword.id)
            replacement = yso.get_replacement(graph, subject)
            if replacement:
                keyword.replaced_by_id = yso.get_yso_id(replacement)
                replacements.append(keyword)
            else:
                missing_replacements.append(keyword)

        if missing_replacements:
            self.stdout.write(
                self.style.WARNING(
                    f"Missing replacements for {len(missing_replacements)} keywords"
                )
            )
            for keyword in missing_replacements:
                self.stdout.write(self.style.WARNING(f"{keyword.id}"))
            self.stdout.write(self.style.WARNING("---"))

        try:
            with transaction.atomic():
                # Sanity check that no replacements are missing
                replacement_ids = set(
                    keyword.replaced_by_id for keyword in replacements
                )
                db_replacements = Keyword.objects.filter(id__in=replacement_ids).count()
                if len(replacements) != db_replacements:
                    raise CommandError(
                        f"Found {len(replacements)} replacements, but only "
                        f"{db_replacements} of them were found from the database"
                    )

                if apply:
                    Keyword.objects.bulk_update(replacements, ["replaced_by_id"])
                    self.stdout.write(
                        self.style.SUCCESS("Replaced {len(replacements)} keywords")
                    )

                else:
                    self.stdout.write(
                        self.style.WARNING(
                            "Dry run, no changes applied. Use --apply to apply changes."
                        )
                    )
                    raise DryRun()
        except DryRun:
            pass
