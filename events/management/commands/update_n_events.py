from django.core.management import BaseCommand, CommandError

from events.models import Keyword, Place
from events.utils import recache_n_events, recache_n_events_in_locations


class Command(BaseCommand):
    help = "Update keyword and place event numbers"

    def add_arguments(self, parser):
        parser.add_argument("model", nargs="?", default=False)
        parser.add_argument(
            "--all",
            default=False,
            action="store_true",
            dest="update_all",
            help="Recalculate everything from scratch",
        )

    def handle_keywords(self, update_all=False):
        if update_all:
            keywords = Keyword.objects.all()
        else:
            keywords = Keyword.objects.filter(n_events_changed=True)
        recache_n_events((k.id for k in keywords), all=update_all)
        print(  # noqa: T201
            "Updated %s keyword event numbers." % ("all" if update_all else "changed")
        )
        print(f"A total of {str(keywords.count())} keywords updated.")  # noqa: T201

    def handle_places(self, update_all=False):
        if update_all:
            places = Place.objects.all()
        else:
            places = Place.objects.filter(n_events_changed=True)
        recache_n_events_in_locations((k.id for k in places), all=update_all)
        print("Updated %s place event numbers." % ("all" if update_all else "changed"))  # noqa: T201
        print(f"A total of {str(places.count())} places updated.")  # noqa: T201

    def handle(self, model=None, update_all=False, **kwargs):
        if model and model not in ("keyword", "place"):
            raise CommandError(
                f"Model {model} not found. Valid models are 'keyword' and 'place'."
            )
        if not model or model == "keyword":
            self.handle_keywords(update_all=update_all)
        if not model or model == "place":
            self.handle_places(update_all=update_all)
