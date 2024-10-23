from django.apps import apps
from django.conf import settings

# For the most part this is copypasted from
# https://github.com/6aika/issue-reporting/blob/master/issues/extensions.py
# original author @akx (Aarni Koskela)


class EventExtension(object):
    #: The identifier for the extension (as referred to in the `extensions` argument)
    identifier = None

    #: The `related_name` for this extension's Event extension model. This will be added to  # noqa: E501
    #: `select_related` queries done over the API.
    related_name = None

    #: Like `related_name`, but for `prefetch_related`.
    prefetch_name = None

    def filter_event_queryset(self, request, queryset, view):  # pragma: no cover
        """
        Filter a queryset of Events given a DRF Request and view.

        This allows extensions to hook into GET queries for requests.

        :param request: DRF request
        :type request: rest_framework.request.Request
        :param queryset: Queryset of events
        :type queryset: QuerySet[Event]
        :param view: The DRF view that was used for this request.
        :type view: rest_framework.views.APIView
        :return: The queryset -- even if it wasn't modified.
        :rtype: QuerySet[Event]
        """
        return queryset

    def get_extension_serializer(self):
        """
        Get the serializer that will be used for this extension.

        This serializer will be wired under field "extension_<extension id>" in Event API.

        :return: The serializer.
        :rtype: rest_framework.serializers.Serializer
        """  # noqa: E501

    def post_create_event(self, request, event, data):  # pragma: no cover
        """
        Hook for after an event is created through the API.

        The given event has been saved already, naturally.

        :param request: The request that caused this event to be created.
        :type request: rest_framework.request.Request
        :param event: The event that was created.
        :type event: events.models.Event
        :param data: The data dict that was used to create the Event
        :type data: dict
        """
        pass

    def post_update_event(self, request, event, data):  # pragma: no cover
        """
        Hook for after an event is updated through the API.

        The given event has been saved already, naturally.

        :param request: The request that caused this event to be updated.
        :type request: rest_framework.request.Request
        :param event: The event that was updated.
        :type event: events.models.Event
        :param data: The data dict that was used to update the Event
        :type data: dict
        """
        pass

    def validate_event_data(self, serializer, data):
        """
        Extension hook to validate event data.

        This is called by EventSerializer.validate().

        :param serializer: EventSerializer
        :type serializer: events.api.serializers.EventSerializer
        :param data: data dict
        :type data: dict
        :return: the data dict, possibly modified (or replaced wholesale?!)
        :rtype: dict
        """
        return data


def get_extensions():
    """
    :rtype: Iterable[class[EventExtension]]
    """
    for app_config in apps.get_app_configs():
        if hasattr(app_config, "event_extension"):
            yield app_config.event_extension


def get_extension_ids():
    return set(ex.identifier for ex in get_extensions())


def get_extensions_from_request(request):
    """
    Get extension instances that are requested by the given request

    :param request: rest_framework.requests.Request
    :rtype: list[events.extensions.EventExtension]
    """
    if hasattr(request, "_event_extensions"):  # Sneaky cache
        return request._event_extensions
    extension_ids = _get_extension_ids_from_param(
        request.query_params.get("extensions")
    )
    if not extension_ids and request.method in ("POST", "PUT", "PATCH"):
        try:
            extension_ids = _get_extension_ids_from_param(
                request.data.get("extensions")
            )
        except (AttributeError, KeyError):
            pass
    extension_ids |= set(getattr(settings, "AUTO_ENABLED_EXTENSIONS", []))

    extensions = set(ex() for ex in get_extensions() if ex.identifier in extension_ids)
    request._event_extensions = extensions
    return extensions


def _get_extension_ids_from_param(extensions_param):
    if extensions_param in ("true", "all"):
        extension_ids = get_extension_ids()
    elif extensions_param:
        extension_ids = set(extensions_param.split(","))
    else:
        extension_ids = set()
    return extension_ids


def apply_select_and_prefetch(queryset, extensions):
    for extension in extensions:
        assert isinstance(extension, EventExtension)
        if extension.related_name:
            queryset = queryset.select_related(extension.related_name)
        if extension.prefetch_name:
            queryset = queryset.prefetch_related(extension.prefetch_name)
    return queryset
