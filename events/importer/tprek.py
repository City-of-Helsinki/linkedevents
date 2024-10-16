import logging

import requests
import requests_cache
from django.conf import settings
from django.contrib.gis.geos import Point
from django.db import transaction
from django_orghierarchy.models import Organization

from events.importer.utils import replace_location
from events.models import DataSource, Place

from .base import Importer, register_importer
from .sync import ModelSyncher

logger = logging.getLogger(__name__)

URL_BASE = "https://www.hel.fi/palvelukarttaws/rest/v4/"
GK25_SRID = 3879


@register_importer
class TprekImporter(Importer):
    name = "tprek"
    supported_languages = ["fi", "sv", "en"]

    def setup(self):
        ds_args = dict(id="tprek")
        defaults = dict(name="Toimipisterekisteri")
        self.data_source, _ = DataSource.objects.get_or_create(
            defaults=defaults, **ds_args
        )

        ds_args = dict(id="ahjo")
        defaults = dict(name="Ahjo")
        ahjo_ds, _ = DataSource.objects.get_or_create(defaults=defaults, **ds_args)

        org_args = dict(origin_id="u021800", data_source=ahjo_ds)
        defaults = dict(name="Viestintäosasto")
        self.organization, _ = Organization.objects.get_or_create(
            defaults=defaults, **org_args
        )
        if self.options.get("remap", None):
            # This will prevent deletion checking, marking all deleted places as deleted
            # again and remapping them accordingly! Otherwise, places already deleted
            # will not be remapped by the syncher.
            self.check_deleted = lambda x: False

    def pk_get(self, resource_name, res_id=None):
        url = "%s%s/" % (URL_BASE, resource_name)
        if res_id is not None:
            url = "%s%s/" % (url, res_id)
        logger.info("Fetching URL %s" % url)
        resp = requests.get(url, timeout=self.default_timeout)
        assert resp.status_code == 200
        return resp.json()

    def delete_and_replace(self, obj):
        obj.deleted = True
        obj.save(update_fields=["deleted"])
        # we won't stand idly by and watch tprek delete needed units willy-nilly
        # without raising a ruckus!
        if obj.events.count() > 0:
            # try to replace by tprek
            replaced = replace_location(replace=obj, by_source="tprek")
            if not replaced:
                logger.warning(
                    "Tprek deleted location %s (%s) with events."
                    "No unambiguous replacement was found. "
                    "Please look for a replacement location and save it in the replaced_by field. "  # noqa: E501
                    "Until then, events will stay mapped to the deleted location."
                    % (obj.id, str(obj))
                )
        return True

    def mark_deleted(self, obj):
        if obj.deleted:
            return False
        return self.delete_and_replace(obj)

    def check_deleted(self, obj):
        return obj.deleted

    @transaction.atomic
    def _import_unit(self, syncher, info):
        obj = syncher.get(str(info["id"]))
        obj_id = "tprek:%s" % str(info["id"])
        if not obj:
            obj = Place(data_source=self.data_source, origin_id=info["id"])
            obj._changed = True
            obj._created = True
            obj.id = obj_id
        else:
            assert obj.id == obj_id
            obj._created = False
        obj._changed_fields = []

        self._save_translated_field(obj, "name", info, "name")
        self._save_translated_field(obj, "description", info, "desc")
        self._save_translated_field(obj, "street_address", info, "street_address")
        self._save_translated_field(obj, "address_locality", info, "address_city")

        self._save_translated_field(obj, "info_url", info, "www", max_length=1000)

        self._save_field(obj, "telephone", info, "phone")

        field_map = {
            "address_zip": "postal_code",
            "address_postal_full": None,
            "email": "email",
        }
        for src_field, obj_field in field_map.items():
            if not obj_field:
                continue
            val = info.get(src_field, None)
            if getattr(obj, obj_field) != val:
                setattr(obj, obj_field, val)
                obj._changed_fields.append(obj_field)
                obj._changed = True

        n = info.get("latitude", 0)
        e = info.get("longitude", 0)
        position = None
        if n and e:
            p = Point(e, n, srid=settings.WGS84_SRID)  # GPS coordinate system
            if p.within(self.bounding_box):
                if self.target_srid != settings.WGS84_SRID:
                    p.transform(self.gps_to_target_ct)
                position = p
            else:
                logger.warning("Invalid coordinates (%f, %f) for %s" % (n, e, obj))

        picture_url = info.get("picture_url", "").strip()
        if picture_url:
            self.set_image(obj, {"url": picture_url})

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
            # location has been reinstated in tprek, hip hip hooray!
            replace_location(from_source="matko", by=obj)
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
        if self.options["cached"]:
            requests_cache.install_cache("tprek")

        queryset = Place.objects.filter(data_source=self.data_source)
        if self.options.get("single", None):
            obj_id = self.options["single"]
            obj_list = [self.pk_get("unit", obj_id)]
            queryset = queryset.filter(id=obj_id)
        else:
            logger.info("Loading units...")
            obj_list = self.pk_get("unit")
            logger.info("%s units loaded" % len(obj_list))
        syncher = ModelSyncher(
            queryset,
            lambda obj: obj.origin_id,
            delete_func=self.mark_deleted,
            check_deleted_func=self.check_deleted,
        )
        for idx, info in enumerate(obj_list):
            if idx and (idx % 1000) == 0:
                logger.info("%s units processed" % idx)
            self._import_unit(syncher, info)

        syncher.finish(self.options.get("remap", False))
