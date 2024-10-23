from django.core.exceptions import ValidationError
from django.core.management.base import BaseCommand
from django.db import transaction

from events.importer import yso
from events.models import Keyword


class DryRun(Exception):
    pass


class Command(BaseCommand):
    help = "Check or apply replacements of deprecated keywords."

    def add_arguments(self, parser):
        parser.add_argument(
            "--apply",
            action="store_true",
            help="Apply replacements",
        )

    def handle(self, **options):
        apply = options["apply"]
        replacements = self.get_replacements()
        try:
            with transaction.atomic():
                # Apply only replacements that actually exist in the DB
                # This is done atomically to avoid accidentally
                # bulk-updating an invalid relation
                ok_replacements = []
                invalid_keyword_ids = []

                replacement_ids = set(
                    keyword.replaced_by_id for keyword in replacements
                )
                db_replacements = Keyword.objects.filter(
                    id__in=replacement_ids
                ).values_list("id", flat=True)

                for keyword in replacements:
                    if keyword.replaced_by_id in db_replacements:
                        ok_replacements.append(keyword)
                    else:
                        invalid_keyword_ids.append(keyword.id)

                if invalid_keyword_ids:
                    self.log_problems(
                        f"{len(invalid_keyword_ids)} replacement keywords do not exist in DB:",  # noqa: E501
                        invalid_keyword_ids,
                    )

                if not ok_replacements:
                    self.stdout.write(
                        self.style.SUCCESS("No keywords need or can be updated.")
                    )

                elif apply:
                    Keyword.objects.bulk_update(ok_replacements, ["replaced_by_id"])
                    self.stdout.write(
                        self.style.SUCCESS(f"Replaced {len(ok_replacements)} keywords")
                    )

                else:
                    self.stdout.write(
                        self.style.SUCCESS(
                            f"WOULD replace {len(ok_replacements)} keywords"
                        )
                    )
                    self.stdout.write(
                        self.style.WARNING(
                            "Dry run, no changes applied. Use --apply to apply changes."
                        )
                    )
                    raise DryRun()
        except DryRun:
            pass

    def log_problems(self, message, keyword_ids):
        self.stdout.write(self.style.WARNING(message))
        for keyword_id in keyword_ids:
            self.stdout.write(self.style.WARNING(f"* {keyword_id}"))
        self.stdout.write(self.style.WARNING("---"))

    def get_replacements(self):
        importer = yso.YsoImporter({})
        importer.setup()
        self.stdout.write("Loading graph into memory, this can take a while...")
        graph = importer.load_graph_into_memory(yso.URL)
        deprecated_keywords_without_replacement = Keyword.objects.filter(
            data_source=importer.data_source, deprecated=True, replaced_by__isnull=True
        )

        self.stdout.write(
            f"Found {len(deprecated_keywords_without_replacement)} deprecated keywords without replacements"  # noqa: E501
        )

        if len(deprecated_keywords_without_replacement) == 0:
            return []

        replacements = []
        missing_replacements_ids = []
        invalid_yso_id_replacements_ids = []
        self.stdout.write("Finding replacements...")
        for keyword in deprecated_keywords_without_replacement:
            subject = yso.get_subject(keyword.id)
            replacement = yso.get_replacement(graph, subject)
            if replacement:
                try:
                    keyword.replaced_by_id = yso.get_yso_id(replacement)
                except ValidationError:
                    invalid_yso_id_replacements_ids.append(keyword.id)
                else:
                    replacements.append(keyword)
            else:
                missing_replacements_ids.append(keyword.id)

        if missing_replacements_ids:
            self.log_problems(
                f"Missing replacements for {len(missing_replacements_ids)} keywords:",
                missing_replacements_ids,
            )

        if invalid_yso_id_replacements_ids:
            self.log_problems(
                f"Invalid replacement yso id for {len(invalid_yso_id_replacements_ids)} keywords:",  # noqa: E501
                invalid_yso_id_replacements_ids,
            )
        return replacements
