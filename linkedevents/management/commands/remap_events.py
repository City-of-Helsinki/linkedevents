import json
import logging
from typing import List

from django.core.management.base import BaseCommand
from django.db import transaction

from events.models import Event, Place

logger = logging.getLogger(__name__)


class DryRun(Exception):
    pass


class Command(BaseCommand):
    help = (
        "Remap events from old place id's to new place id's based on "
        "provided mapping file. The mapping file is a json containing a "
        'list of lists. For example [["tprek:3235", "tprek:71757"]] '
        "would remap from ID tprek:3235 to tprek:71757"
    )

    def add_arguments(self, parser):
        parser.add_argument(
            "map_file_path",
            type=str,
            help="Path to map file",
        )
        parser.add_argument(
            "--apply",
            action="store_true",
            help="Apply changes",
        )

    def handle(self, map_file_path, **options):
        apply = options["apply"]
        with open(map_file_path, "r") as f:
            remap = json.load(f)
        self.process_remap(remap, apply)

    @transaction.atomic
    def process_remap(self, remap: List[List[int]], apply=False):
        for old_id, new_id in remap:
            try:
                new_place = Place.objects.get(pk=new_id)
            except Place.DoesNotExist:
                logger.error(f"New place {old_id} does not exist")
                raise

            rows = Event.objects.filter(location_id=old_id).update(location=new_place)
            logger.info(
                f"{old_id} -> {new_id}: {rows} events updated ({new_place.name})"
            )
        if not apply:
            raise DryRun
