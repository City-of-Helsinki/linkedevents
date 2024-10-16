import logging

from django.conf import settings
from django.core.management import call_command
from django.db import transaction
from django.utils.module_loading import import_string
from django_orghierarchy.models import Organization

from events.models import DataSource, Place

from .base import Importer, register_importer
from .sync import ModelSyncher

logger = logging.getLogger(__name__)

GK25_SRID = 3879
CHUNK_SIZE = 10000


@register_importer
class OsoiteImporter(Importer):
    name = "osoite"
    supported_languages = ["fi", "sv"]

    def setup(self):
        ds_args = dict(id="osoite")
        defaults = dict(name="Pääkaupunkiseudun osoiteluettelo")
        self.data_source, _ = DataSource.objects.get_or_create(
            defaults=defaults, **ds_args
        )

        ds_args = dict(id="ahjo")
        defaults = dict(name="Ahjo")
        ahjo_ds, _ = DataSource.objects.get_or_create(defaults=defaults, **ds_args)

        org_args = dict(origin_id="u541000", data_source=ahjo_ds)
        defaults = dict(name="Kaupunkiympäristön toimiala")
        self.organization, _ = Organization.objects.get_or_create(
            defaults=defaults, **org_args
        )
        if self.options.get("remap", None):
            # This will prevent deletion checking, marking all deleted places as deleted
            # again and remapping them accordingly! Otherwise, places already deleted
            # will not be remapped by the syncher.
            self.check_deleted = lambda x: False
            self.mark_deleted = self.delete_and_replace

    def get_street_address(self, address, language):
        # returns the address sans municipality in the desired language, or
        # Finnish as fallback
        address.street.set_current_language(language)
        street = address.street.name
        s = "%s %s" % (street, address.number)
        if address.number_end:
            s += "-%s" % address.number_end
        if address.letter:
            s += "%s" % address.letter
        return s

    def get_whole_address(self, address, language):
        # returns the address plus municipality in the desired language
        address.street.municipality.set_current_language(language)
        municipality = address.street.municipality.name
        return self.get_street_address(address, language) + ", " + municipality

    def pk_get(self, resource_name, res_id=None):
        # support all munigeo resources, not just addresses
        klass = import_string("munigeo.models." + resource_name)
        if res_id is not None:
            return klass.objects.get(origin_id=res_id)
        return klass.objects.all()

    def delete_and_replace(self, obj):
        obj.deleted = True
        obj.save(update_fields=["deleted"])
        # we won't stand idly by and watch kymp delete used addresses willy-nilly
        # without raising a ruckus!
        if obj.events.count() > 0:
            # sadly, addresses are identified by, well, address alone. Therefore we have no other data that  # noqa: E501
            # could be used to find out if there is a replacement location.
            logger.warning(
                "Osoiteluettelo deleted address %s (%s) with events. This means that the street in "  # noqa: E501
                "question has probably changed address numbers, as they do. Please check all "  # noqa: E501
                "addresses on the street for events and save any new address numbers in the "  # noqa: E501
                "replaced_by field. If several addresses have changed on the street, you may have to "  # noqa: E501
                "manually move the events instead. Until then, events will stay mapped to the old "  # noqa: E501
                "addresses." % (obj.id, str(obj))
            )
        return True

    def mark_deleted(self, obj):
        if obj.deleted:
            return False
        return self.delete_and_replace(obj)

    def check_deleted(self, obj):
        return obj.deleted

    @transaction.atomic
    def _import_address(self, syncher, address_obj):
        # addresses have no static ids, just format the address cleanly
        origin_id = (
            str(address_obj)
            .replace(" - ", "-")
            .replace(",", "")
            .replace(" ", "_")
            .replace(".", "_")
            .lower()
        )
        obj = syncher.get(origin_id)
        obj_id = "osoite:" + origin_id
        if not obj:
            obj = Place(data_source=self.data_source, origin_id=origin_id)
            obj._changed = True
            obj._created = True
            obj.id = obj_id
        else:
            assert obj.id == obj_id
            obj._created = False
        obj._changed_fields = []

        # we must construct the names and street addresses from the address object
        info = {}
        for lang in self.supported_languages:
            info["name_" + lang] = self.get_whole_address(address_obj, lang)
            info["street_address_" + lang] = self.get_street_address(address_obj, lang)
            address_obj.street.municipality.set_current_language(lang)
            info["municipality_" + lang] = address_obj.street.municipality.name

        self._save_translated_field(obj, "name", info, "name")
        self._save_translated_field(obj, "street_address", info, "street_address")
        self._save_translated_field(obj, "address_locality", info, "municipality")

        position = address_obj.location

        if position and obj.position:
            # If the distance is less than 10cm, assume the location
            # hasn't changed.
            assert obj.position.srid == settings.PROJECTION_SRID
            if position.distance(obj.position) < 0.10:
                position = obj.position
        if position != obj.position:
            obj._changed = True
            obj._changed_fields.append("position")
            obj.position = position

        if obj.publisher_id != self.organization.id:
            obj.publisher = self.organization
            obj._changed_fields.append("publisher")
            obj._changed = True

        if obj.deleted:
            obj.deleted = False
            # address has been reinstated, hip hip hooray!
            # there's no way we can find any events from other addresses that should now be in this address  # noqa: E501
            # so we cannot do address replace here (the way we do with tprek units)
            obj._changed_fields.append("deleted")
            obj._changed = True

        if obj._changed:
            if obj._created:
                verb = "created"
            else:
                verb = "changed (fields: %s)" % ", ".join(obj._changed_fields)
            logger.info("%s %s" % (obj, verb))
            obj.save()

        syncher.mark(obj)

    def import_places(self):
        # munigeo saves addresses in local db, we just create Places from them.
        # note that the addresses only change daily and the import is
        # time-consuming, so we should not run this hourly

        # addresses require the municipalities to be present in the db
        call_command("geo_import", "finland", municipalities=True)
        call_command("geo_import", "helsinki", addresses=True)

        queryset = Place.objects.filter(data_source=self.data_source)
        if self.options.get("single", None):
            obj_id = self.options["single"]
            obj_list = [self.pk_get("Address", obj_id)]
            queryset = queryset.filter(id=obj_id)
        else:
            logger.info("Loading addresses...")
            obj_list = self.pk_get("Address")
            logger.info(f"{obj_list.count()} addresses loaded")
            obj_list = obj_list.iterator(chunk_size=CHUNK_SIZE)
        syncher = ModelSyncher(
            queryset,
            lambda obj: obj.origin_id,
            delete_func=self.mark_deleted,
            check_deleted_func=self.check_deleted,
        )
        for idx, obj in enumerate(obj_list):
            if idx and (idx % 1000) == 0:
                logger.info(f"{idx} addresses processed")
            self._import_address(syncher, obj)

        syncher.finish(self.options.get("remap", False))
