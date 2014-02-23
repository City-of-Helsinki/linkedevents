from .sync import ModelSyncher
from .base import Importer, register_importer

@register_importer
class KulkeImporter(Importer):
    name = "kulke"

    def import_events(self):
        print("Importing Kulke events")
        pass

    def import_locations(self):
        print("Importing Kulke locations")
        pass
