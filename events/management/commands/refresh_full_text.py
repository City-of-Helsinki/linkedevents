import os
import re

from django.conf import settings
from django.core.management import BaseCommand
from django.db import connection
from django.db.models import Exists, OuterRef, Q

from events.models import Event, EventFullText, Place


def sql_filename(filename):
    return os.path.join(os.path.dirname(__file__), f"sql/refresh_full_text/{filename}")


def field_regex(field):
    return re.compile(
        rf"(?P<head>setweight\([^)]*?{field}.*?')(?P<weight>[ABCD])(?P<tail>')",
        re.DOTALL,
    )


class Command(BaseCommand):
    help = "Refresh the full text materialized view. Use switches to adjust behaviour"

    def add_arguments(self, parser):
        parser.add_argument(
            "--create",
            action="store_true",
            help="(Re)create the materialized view instead of refresh",
        )

        parser.add_argument(
            "--drop",
            action="store_true",
            help="Drop the materialized view instead of refresh",
        )

        parser.add_argument(
            "--create-no-transaction",
            action="store_true",
            help="Same as --create but without a transaction. Primary use case is for testing.",  # noqa: E501
        )

        parser.add_argument("--force", action="store_true", help="Force refresh")

    def apply_overrides(self, sql):
        for field, weight_override in settings.FULL_TEXT_WEIGHT_OVERRIDES.items():
            replaced_sql = re.sub(
                field_regex(field), rf"\g<head>{weight_override}\g<tail>", sql
            )
            if replaced_sql == sql:
                self.stdout.write(
                    self.style.WARNING(f"Failed to apply weight override for {field}!")
                )
            else:
                self.stdout.write(
                    f"Applied weight override for field {field} to {weight_override}"
                )
            sql = replaced_sql
        return sql

    def handle(self, *args, **options):
        if options["drop"]:
            # Print stdout success info
            self.stdout.write("Dropping events_eventfulltext materialized view")
            with connection.cursor() as cursor:
                cursor.execute("DROP MATERIALIZED VIEW IF EXISTS events_eventfulltext")

        elif options["create"] or options["create_no_transaction"]:
            self.stdout.write(
                "Creating events_eventfulltext materialized view (this may take some seconds)"  # noqa: E501
            )

            with open(sql_filename("create_materialized_view.sql"), "r") as file:
                sql = file.read()

            sql = self.apply_overrides(sql)
            if not options["create_no_transaction"]:
                sql = f"BEGIN;\n {sql} \nCOMMIT;\n"

            with connection.cursor() as cursor:
                cursor.execute(sql)

        else:
            if not options["force"]:
                self.stdout.write("Checking if refresh is needed...")

                def check_refresh_needed():
                    # Check for new/modified events
                    yield Event.objects.filter(
                        ~Exists(
                            EventFullText.objects.filter(
                                event_id=OuterRef("id"),
                                event_last_modified_time=OuterRef("last_modified_time"),
                            )
                        )
                    ).count()

                    # Check for new/modified places
                    yield Event.objects.filter(
                        ~Exists(
                            EventFullText.objects.filter(
                                Q(place__isnull=True, event__location__isnull=True)
                                | Q(
                                    place_id=OuterRef("location_id"),
                                    place_last_modified_time=OuterRef(
                                        "location__last_modified_time"
                                    ),
                                ),
                                event_id=OuterRef("id"),
                            )
                        )
                    ).count()

                    # Check for deleted events
                    yield EventFullText.objects.filter(
                        ~Exists(Event.objects.filter(id=OuterRef("event_id"))),
                        event__isnull=False,
                    ).count()

                    # Check for deleted places
                    yield EventFullText.objects.filter(
                        ~Exists(Place.objects.filter(id=OuterRef("place_id"))),
                        place__isnull=False,
                    ).count()

                if not any(check_refresh_needed()):
                    self.stdout.write(self.style.SUCCESS("Refresh not needed!"))
                    return

            self.stdout.write(
                "Refreshing events_eventfulltext materialized view (this may take some seconds)"  # noqa: E501
            )
            with connection.cursor() as cursor:
                cursor.execute(
                    "REFRESH MATERIALIZED VIEW CONCURRENTLY events_eventfulltext"
                )
        self.stdout.write(self.style.SUCCESS("Done!"))
