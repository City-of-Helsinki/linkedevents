import argparse
import json

from django.core.management.base import BaseCommand
from django.db import transaction

from events.models import Event, Place


class DryRun(Exception):  # noqa: N818
    pass


class Command(BaseCommand):
    help = (
        "Remap events from old place id's to new place id's based on "
        "provided mapping file. The mapping file is a json containing a "
        'mapping of old place ids to new place ids. For example\n"'
        'python manage.py remap_events - <<< \'{"tprek:3235": "tprek:71757"}\''
        "would remap from all events with location_id of tprek:3235 "
        "into a new location_id tprek:71757"
    )

    def add_arguments(self, parser):
        parser.add_argument(
            "file",
            type=argparse.FileType("r"),
            help="A json mapping file to process (path or stdin)",
        )

        parser.add_argument(
            "--apply",
            action="store_true",
            help="Apply changes",
        )

    def handle(self, file, **options):
        apply = options["apply"]
        remap = json.load(file)

        try:
            with transaction.atomic():
                self.process_remap(remap)
                if not apply:
                    raise DryRun
        except DryRun:
            self.stdout.write(
                self.style.WARNING(
                    "Dry run, no changes applied. Use --apply to apply changes."
                )
            )
        except ValueError as ex:
            self.stderr.write(f"Failed to apply: {str(ex)}")
        else:
            self.stdout.write(self.style.SUCCESS("Done"))

    def process_remap(self, remap: dict[str, str]):
        for old_id, new_id in remap.items():
            try:
                new_place = Place.objects.get(pk=new_id)
            except Place.DoesNotExist:
                error_msg = f"New place {new_id} does not exist"
                raise ValueError(error_msg)

            rows = Event.objects.filter(location_id=old_id).update(location=new_place)
            self.stdout.write(
                self.style.SUCCESS(
                    f"{old_id} -> {new_id}: {rows} events updated ({new_place.name})"
                )
            )
