from haystack import indexes

from .models import Event, Place, PublicationStatus


class EventIndex(indexes.SearchIndex, indexes.Indexable):
    text = indexes.CharField(document=True, use_template=True)
    autosuggest = indexes.EdgeNgramField(model_attr="name")
    start_time = indexes.DateTimeField(model_attr="start_time", null=True)
    end_time = indexes.DateTimeField(model_attr="end_time", null=True)

    def get_updated_field(self):
        return "last_modified_time"

    def get_model(self):
        return Event

    def index_queryset(self, using=None):
        return (
            super()
            .index_queryset(using)
            .filter(publication_status=PublicationStatus.PUBLIC, deleted=False)
        )

    def update_object(self, instance, using=None, **kwargs):
        # instantly remove deleted and non-public events
        if instance.deleted or instance.publication_status != PublicationStatus.PUBLIC:
            super().remove_object(instance, using, **kwargs)
        else:
            super().update_object(instance, using, **kwargs)


class PlaceIndex(indexes.SearchIndex, indexes.Indexable):
    text = indexes.CharField(document=True, use_template=True)
    autosuggest = indexes.EdgeNgramField(model_attr="name")

    def get_updated_field(self):
        return "last_modified_time"

    def get_model(self):
        return Place

    def index_queryset(self, using=None):
        return super().index_queryset(using).filter(deleted=False)

    def update_object(self, instance, using=None, **kwargs):
        # instantly remove deleted objects
        if instance.deleted:
            super().remove_object(instance, using, **kwargs)
        else:
            super().update_object(instance, using, **kwargs)
