viewset_classes_by_model = {}

all_views = []


def register_view(klass, name, base_name=None):
    entry = {"class": klass, "name": name}
    if base_name is not None:
        entry["base_name"] = base_name
    all_views.append(entry)
    if (
        klass.serializer_class
        and hasattr(klass.serializer_class, "Meta")
        and hasattr(klass.serializer_class.Meta, "model")
    ):
        model = klass.serializer_class.Meta.model
        viewset_classes_by_model[model] = klass
