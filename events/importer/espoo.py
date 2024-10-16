import logging
import time
import urllib
from copy import deepcopy
from typing import Annotated, Any, Callable, Optional, Type, TypeVar, Union
from urllib.parse import urljoin, urlparse

import requests
from django.conf import settings
from django.db import transaction
from django.db.models import Model
from django.utils import timezone
from django_orghierarchy.models import Organization
from requests.adapters import HTTPAdapter
from requests.exceptions import RetryError
from rest_framework.fields import empty
from urllib3 import Retry

from events.models import DataSource, Event, Image, Keyword, Language, Place
from events.translation import EventTranslationOptions

from ..serializers import generate_id
from ..utils import clean_text_fields
from .base import Importer, register_importer
from .sync import ModelSyncher

logger = logging.getLogger(__name__)

M = TypeVar("M", bound=Model)

EVENT_START = timezone.now() - timezone.timedelta(
    days=settings.ESPOO_API_EVENT_START_DAYS_BACK
)


PreMapper = Annotated[
    Callable[[str, Any, dict], dict[str, Any]],
    """
    Pre field actions are functions that receive arguments:
    - field_name: str (field that is currently being mapped)
    - field_data: Any (field data from the origin object)
    - data: dict (target object data)
    and return a new dict of fields to be used for the creation of the target object
    """,
]


PostMapper = Annotated[
    Callable[[str, Any, dict, M, dict[str, str]], dict[str, Any]],
    """
    Post field actions are functions that receive arguments:
    - field_name: str (field that is currently being mapped)
    - field_data: Any (field data from the origin object)
    - data: dict (target object data)
    - instance: instance of the model being mapped
    - instance_map: a map of origin object ids to target (local) object ids
    and return a new dict of fields to be used for the update of the target object
    """,
]


class EspooImporterError(Exception):
    pass


def parse_jsonld_id(data: dict) -> str:
    if (ld_reference := data.get("@id")) and (origin_id := ld_reference.split("/")[-2]):
        return origin_id
    raise EspooImporterError("Could not parse jsonld id")


def _build_url(path):
    base_url = settings.ESPOO_API_URL
    if base_url[-1] != "/":
        base_url += "/"

    return urllib.parse.urljoin(base_url, urllib.parse.quote(path))


def _get_data(url: str, params: Optional[dict] = None) -> dict:
    session = requests.Session()
    retries = Retry(
        total=settings.ESPOO_MAX_RETRIES,
        status_forcelist=[429, 500, 502, 503, 504],
    )
    parsed_url = urlparse(url)
    session.mount(f"{parsed_url.scheme}://", HTTPAdapter(max_retries=retries))
    try:
        response = session.get(url, timeout=settings.ESPOO_TIMEOUT, params=params)
    except RetryError:
        raise EspooImporterError(f"Exceeded max retries for {url}")
    if response.status_code != 200:
        raise EspooImporterError(f"Received bad status: {response.status_code}")
    return response.json()


def _list_data(url: str, params: Optional[dict] = None) -> list[dict]:
    results = []
    request_params = params
    for _ in range(settings.ESPOO_MAX_PAGES):
        response_data = _get_data(url, request_params)
        results += response_data["data"]
        url = response_data["meta"]["next"]
        if url is None:
            return results

        # Params are included in the response next url
        request_params = None
        time.sleep(settings.ESPOO_WAIT_BETWEEN)

    raise EspooImporterError("Exceeded ESPOO_MAX_PAGES")


def _get_origin_objs(detail_url: str, origin_obj_ids: list) -> list:
    return [_get_data(urljoin(detail_url, f"./{obj_id}/")) for obj_id in origin_obj_ids]


def _build_pre_map(mapping: dict[str, str]) -> PreMapper:
    """
    Build a pre field mapper that maps the origin object field value to a value from a mapping.

    :param mapping: a map of origin object values to target object values

    :return: a pre field mapper function
    """  # noqa: E501

    def pre_map(
        field_name, field_data: Optional[Union[str, dict]], data: dict
    ) -> dict[str, Any]:
        """
        Map a single field from origin object to target object

        :param field_name: name of the field in the target object, e.g. "name"
        :param field_data: data from the field in the origin object, e.g. origin_obj["name"]
        :param data: target object data

        :return: updated target object data with the field mapped
        """  # noqa: E501
        if field_data is None:
            return {**data}
        # If the field is a dict, we map the id field to the target field
        elif isinstance(field_data, dict):
            if "id" not in field_data and "@id" not in field_data:
                raise EspooImporterError(f"Unable to parse id from data: {field_data}")

            if "id" in field_data:
                return {**data, field_name: mapping[field_data["id"]]}
            else:
                return {**data, field_name: mapping[parse_jsonld_id(field_data)]}

        # If the field is a string, we map the string to the target field
        return {**data, field_name: mapping[field_data]}

    return pre_map


def _build_pre_map_to_id(mapping: dict[str, str]) -> PreMapper:
    """
    Build a pre field mapper that maps the origin object field value to a target object id.

    :param mapping: a map of origin object ids to target (local) object ids
    """  # noqa: E501
    pre_mapper = _build_pre_map(mapping)

    def pre_map_to_id(
        field_name: str, field_data: Optional[Union[str, dict]], data: dict
    ) -> dict[str, Any]:
        return pre_mapper(f"{field_name}_id", field_data, data)

    return pre_map_to_id


def _pre_map_value_to_id(
    field_name: str, field_data: Optional[Union[str, dict]], data: dict
) -> dict[str, Any]:
    """
    Direct map a value to the relevant id (foreign key)
    """
    return {**data, f"{field_name}_id": field_data}


def _pre_map_translation(
    field_name: str, field_data: Optional[dict], data: dict
) -> dict:
    """
    Translation field mapper
    """
    if field_data is None:
        return data

    language_codes = [lang[0] for lang in settings.LANGUAGES]

    return {
        **data,
        **{
            f"{field_name}_{lang}": value
            for lang, value in field_data.items()
            if lang in language_codes
        },
    }


def _post_map_to_self_id(
    field_name: str,
    field_data: Optional[Union[str, dict]],
    data: dict,
    instance: M,
    instance_map: dict[str, str],
):
    mapper = _build_pre_map_to_id(instance_map)
    return mapper(field_name, field_data, data)


def _build_post_map_m2m_obj(mapping: dict[str, str], id_getter=None) -> PostMapper:
    """
    Post mapper for ManyToMany fields
    """
    id_getter = id_getter or (lambda d: d["id"])

    def post_map_m2m_obj(
        field_name: str,
        field_data: list[dict],
        data: dict,
        instance: M,
        instance_map: dict[str, str],
    ) -> dict[str, Any]:
        field = getattr(instance, field_name)
        field.set([mapping[id_getter(d)] for d in field_data])
        return {**data}

    return post_map_m2m_obj


def _post_recreate_m2o(
    field_name: str,
    field_data: list[dict],
    data: dict,
    instance: M,
    instance_map: dict[str, str],
):
    """
    For relations that the API does not provide an ID for, such as
    Event.offers.

    Delete old ones and recreate. Since this function is rather
    destructive, there's an extra safeguard allowed_fields to make
    the usage of this function more obvious.
    """
    allowed_fields = ("offers", "external_links")
    if field_name not in allowed_fields:
        raise EspooImporterError(
            f"Field {field_name} is not allowed for _post_recreate_m2m"
        )

    field = getattr(instance, field_name)
    field.all().delete()
    for relation_data in field_data:
        field.create(**relation_data)
    return {**data}


def _post_recreate_external_links(
    field_name: str,
    field_data: list[dict],
    data: dict,
    instance: M,
    instance_map: dict[str, str],
):
    """
    Extension of _post_recreate_m2o for Event.external_links
    which also require a reference to language object.

    Does not create new Language objects, those that don't exist
    are skipped.
    """
    language_map = {
        language.id: language for language in Language.objects.all().only("id")
    }
    language_field_data = []
    for relation_data in field_data:
        relation_data = {**relation_data}
        if relation_data["language"] in language_map:
            relation_data["language"] = language_map[relation_data["language"]]
            language_field_data.append(relation_data)
    return _post_recreate_m2o(
        field_name, language_field_data, data, instance, instance_map
    )


def _import_origin_obj(
    obj_data,
    model: Type[M],
    data_source,
    copy_fields,
    pre_field_mappers,
    auto_pk=False,
    origin_id_field="id",
    instance_id_field="origin_id",
) -> M:
    obj_data = deepcopy(obj_data)
    origin_id = obj_data.pop(origin_id_field)
    obj_data.pop("data_source")

    data = {k: v for k, v in obj_data.items() if k in copy_fields}
    for field_name, mapper in pre_field_mappers.items():
        data = mapper(field_name, obj_data.get(field_name), data)
    data = clean_text_fields(data, ["description"], strip=True)

    qs = model.objects.filter(data_source=data_source, **{instance_id_field: origin_id})
    qs_count = qs.count()
    if qs_count == 0:
        kwargs = {
            instance_id_field: origin_id,
            "data_source": data_source,
        }
        if not auto_pk:
            kwargs["id"] = generate_id(data_source)

        instance = model.objects.create(
            **kwargs,
            **data,
        )
    elif qs_count == 1:
        qs.update(**data)
        instance = qs[0]
    else:
        raise EspooImporterError(
            f"Data integrity is broken "
            f"({instance_id_field}={origin_id}, data_source={data_source.pk})"
        )
    return instance


def _import_origin_objs(
    model: Type[M],
    data_source: DataSource,
    common_objs: list[M],
    origin_objs: list[dict],
    copy_fields: Optional[list[str]] = None,
    pre_field_mappers: Optional[dict[str, PreMapper]] = None,
    post_field_mappers: Optional[dict[str, PostMapper]] = None,
    auto_pk=False,
    instance_id_field: Optional[str] = "origin_id",
    origin_id_field: Optional[str] = "id",
) -> tuple[dict[str, str], ModelSyncher]:
    """
    Import data from origin_objs into model instances using mapping
    defined by copy_fields, pre_field_mappers and post_field_mappers.

    id, origin_id and data_source are set/mapped automatically.

    common_objs: list of common model instances that are used only for mapping
    copy_fields: list of field names to be copied as is from origin to target
    pre_field_mappers: fields that are mapped before saving the model instance (source -> target)
    post_field_mappers: fields that are mapped after saving all the model instances (source -> target)
    auto_id: set True for models that use AutoField pk
    syncher_key:
    """  # noqa: E501
    logger.info(f"Importing related Espoo {model.__name__}s")

    def origin_id(instance):
        return getattr(instance, instance_id_field)

    queryset = model.objects.filter(data_source=data_source)

    if model == Event:
        queryset = queryset.filter(start_time__gte=EVENT_START)

    syncher = ModelSyncher(
        queryset,
        origin_id,
    )

    copy_fields = copy_fields or []
    pre_field_mappers = pre_field_mappers or {}
    post_field_mappers = post_field_mappers or {}

    instances = []
    instance_data_map = {}
    for obj_data in origin_objs:
        instance = _import_origin_obj(
            obj_data,
            model,
            data_source,
            copy_fields,
            pre_field_mappers,
            auto_pk=auto_pk,
            instance_id_field=instance_id_field,
            origin_id_field=origin_id_field,
        )

        instances.append(instance)
        instance_data_map[instance] = obj_data
        syncher.mark(instance)

    instance_mapping = {
        **{obj.id: obj.id for obj in common_objs},
        **{origin_id(instance): instance.id for instance in instances},
    }

    for instance in instances:
        post_data = {}
        for field_name, mapper in post_field_mappers.items():
            obj_data = instance_data_map[instance]
            post_data = mapper(
                field_name, obj_data[field_name], post_data, instance, instance_mapping
            )

        if post_data:
            type(instance).objects.filter(pk=instance.pk).update(**post_data)

    return instance_mapping, syncher


def _split_common_objs(
    model: Type[M],
    data_source: DataSource,
    origin_objs: list[dict],
) -> tuple[list[M], list[dict]]:
    """
    Generic method for discovering origin objects that can be matched
    to existing models in other data sources. For example tprek entries
    should generally be identical between Helsinki LE and Espoo LE.
    """
    origin_obj_ids = set(obj["id"] for obj in origin_objs)
    common_objs = list(
        model.objects.filter(id__in=origin_obj_ids)
        .exclude(data_source=data_source)
        .only("id")
    )
    common_obj_ids = [obj.id for obj in common_objs]
    origin_objs = [obj for obj in origin_objs if obj["id"] not in common_obj_ids]
    return common_objs, origin_objs


def _add_id_to_set(container: set, obj, key):
    """
    Utility function for adding ids to a set
    """
    if value := obj.get(key, empty):
        if value == empty:
            raise EspooImporterError(f"Missing {key}")
        if not isinstance(value, list):
            value = [value]
        container.update(value)


def _add_id_to_dict(container: dict, obj, key):
    """
    Utility function for adding ids to a dict
    """
    if value := obj.get(key, empty):
        if value == empty:
            raise EspooImporterError(f"Missing {key}")
        if not isinstance(value, list):
            value = [value]
        for row in value:
            container[row["id"]] = row


def purge_orphans(events_data: list[dict], skip_log=False) -> list[dict]:
    """
    This function can (and should) be called to recursively get rid of
    broken super event references. Each iteration produces a map of known
    events and then checks if there are any events that reference missing events.

    Multiple iterations are required since each call gets rid of one "generation"
    """
    ids = [event_data["id"] for event_data in events_data]
    keep = []
    drop = set()
    for event_data in events_data:
        if (super_event := event_data["super_event"]) and (
            super_event_id := parse_jsonld_id(super_event)
        ) not in ids:
            drop.add(super_event_id)
            continue
        keep.append(event_data)

    if drop:
        if not skip_log:
            logger.info(
                f"Events referenced as super events are missing from the data: {', '.join(sorted(drop))}"  # noqa: E501
            )
        return purge_orphans(keep, skip_log=True)

    return keep


@register_importer
class EspooImporter(Importer):
    """
    Espoo Linkedevents importer

    Almost generic importer that can import events from a compatible
    Linkedevents instance. It also imports referenced relations, such as
    Organizations, Keywords and Places.

    The importer detects referenced objects that are shared across instances,
    for example tprek places, and maps the references against existing instances
    if such are found.

    All imported objects are placed under the same data source. The origin
    id is mapped to origin_id and a new local id is generated.

    Objects in the importer datasource that are no longer referenced by the
    origin API will get removed using ModelSyncher.
    """

    name = "espoo"
    data_source_name = "espoo_le"

    supported_languages = ["fi", "sv", "en"]
    keyword_cache = {}
    location_cache = {}

    def setup(self):
        ds_args = dict(id=self.data_source_name)
        ds_defaults = dict(name="Espoo Linkedevents")
        self.data_source, _ = DataSource.objects.get_or_create(
            defaults=ds_defaults, **ds_args
        )

        org_data_source, _ = DataSource.objects.get_or_create(
            id="espoo", defaults={"name": "Espoo"}
        )

        espoo_kaupunki, _ = Organization.objects.get_or_create(
            id="espoo:kaupunki",
            defaults={
                "name": "Espoon kaupunki",
                "data_source": org_data_source,
                "origin_id": "espoo_kaupunki",
            },
        )
        for org_id, org_name in settings.ESPOO_API_PUBLISHERS:
            Organization.objects.get_or_create(
                id=org_id,
                defaults={
                    "data_source": org_data_source,
                    "name": org_name,
                    "parent": espoo_kaupunki,
                    "origin_id": org_id,
                },
            )

        # No default organization
        self.organization = None

    @transaction.atomic
    def import_events(self):
        logger.info("Importing Espoo events")

        # Grab all origin organizations
        orgs_data = _list_data(_build_url("v1/organization/"))

        # Grab all relevant events from origin
        # Using include=keywords,audience,location and restrict events starting from
        # configured days (defaulting to 180) back to reduce the number of needed
        # requests.
        events_data = _list_data(
            _build_url("v1/event/"),
            params={
                "start": EVENT_START.isoformat(),
                "include": "keywords,audience,location",
                **settings.ESPOO_API_EVENT_QUERY_PARAMS,
            },
        )

        events_data = purge_orphans(events_data)

        # Relations that need to be imported separately
        origin_places = {}
        origin_keywords = {}
        origin_audiences = {}
        origin_org_ids = set()
        origin_images = {}

        # Collect remote relations from events
        for event_data in events_data:
            _add_id_to_set(origin_org_ids, event_data, "publisher")
            _add_id_to_dict(origin_audiences, event_data, "audience")
            _add_id_to_dict(origin_places, event_data, "location")
            _add_id_to_dict(origin_keywords, event_data, "keywords")
            _add_id_to_dict(origin_images, event_data, "images")

        # Collect publisher organizations from places and keywords
        logger.info("Discovering organizations from relations")
        for place_data in origin_places.values():
            _add_id_to_set(origin_org_ids, place_data, "publisher")

        for keyword_data in origin_keywords.values():
            _add_id_to_set(origin_org_ids, keyword_data, "publisher")

        for audience_data in origin_audiences.values():
            _add_id_to_set(origin_org_ids, audience_data, "publisher")

        for image_data in origin_images.values():
            _add_id_to_set(origin_org_ids, image_data, "publisher")

        old_event_ids = Event.objects.filter(
            data_source=self.data_source, start_time__lt=EVENT_START
        ).values_list("id", flat=True)

        # Import organizations
        logger.info("Importing organizations")
        org_objs = [org for org in orgs_data if org["id"] in origin_org_ids]
        common_objs, org_objs = _split_common_objs(
            Organization, self.data_source, org_objs
        )
        org_map, org_syncher = _import_origin_objs(
            Organization,
            self.data_source,
            common_objs,
            org_objs,
            copy_fields=["name"],
        )

        # Mark Organizations which are referenced in older Espoo events to avoid
        # deletion.
        for org in Organization.objects.filter(
            data_source=self.data_source, published_events__in=old_event_ids
        ).iterator():
            org_syncher.mark(org)

        # Import places
        common_places, origin_places = _split_common_objs(
            Place, self.data_source, list(origin_places.values())
        )
        place_map, place_syncher = _import_origin_objs(
            Place,
            self.data_source,
            common_places,
            origin_places,
            pre_field_mappers={
                "name": _pre_map_translation,
                "publisher": _build_pre_map_to_id(org_map),
            },
        )

        # Mark Places which are referenced in older Espoo events to avoid deletion.
        for place in Place.objects.filter(
            data_source=self.data_source, events__in=old_event_ids
        ).iterator():
            place_syncher.mark(place)

        # Import keywords
        common_keywords, origin_keywords = _split_common_objs(
            Keyword,
            self.data_source,
            list(origin_keywords.values()) + list(origin_audiences.values()),
        )
        keyword_map, keyword_syncher = _import_origin_objs(
            Keyword,
            self.data_source,
            common_keywords,
            origin_keywords,
            pre_field_mappers={
                "name": _pre_map_translation,
                "publisher": _build_pre_map_to_id(org_map),
            },
        )

        # Mark Keywords which are referenced in older Espoo events to avoid deletion.
        for kw in Keyword.objects.filter(
            data_source=self.data_source, events__in=old_event_ids
        ).iterator():
            place_syncher.mark(kw)

        image_map, image_syncher = _import_origin_objs(
            Image,
            self.data_source,
            [],
            list(origin_images.values()),
            copy_fields=[
                "created_time",
                "last_modified_time",
                "name",
                "url",
                "cropping",
                "photographer_name",
                "alt_text",
                "data_source",
            ],
            pre_field_mappers={"license": _pre_map_value_to_id},
            auto_pk=True,
            instance_id_field="url",
            origin_id_field="url",
        )

        # And finally import events
        _, event_syncher = _import_origin_objs(
            Event,
            self.data_source,
            [],
            events_data,
            copy_fields=[
                "created_time",
                "date_published",
                "deleted",
                "end_time",
                "last_modified_time",
                "start_time",
                "super_event_type",
            ],
            pre_field_mappers={
                **{
                    translation_field_name: _pre_map_translation
                    for translation_field_name in EventTranslationOptions.fields
                },
                "event_status": _build_pre_map({v: k for k, v in Event.STATUSES}),
                "location": _build_pre_map_to_id(place_map),
                "publisher": _build_pre_map_to_id(org_map),
            },
            post_field_mappers={
                "audience": _build_post_map_m2m_obj(keyword_map),
                "keywords": _build_post_map_m2m_obj(keyword_map),
                "images": _build_post_map_m2m_obj(
                    image_map, id_getter=lambda d: d["url"]
                ),
                "offers": _post_recreate_m2o,
                "external_links": _post_recreate_external_links,
                "super_event": _post_map_to_self_id,
            },
        )

        force = self.options["force"]
        event_syncher.finish(force=force)
        place_syncher.finish(force=force)
        keyword_syncher.finish(force=force)
        image_syncher.finish(force=force)
        org_syncher.finish(force=force)

        logger.info("{} events processed".format(len(events_data)))
