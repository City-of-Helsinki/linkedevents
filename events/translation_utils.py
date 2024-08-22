import modeltranslation
from helsinki_gdpr.models import SerializableMixin
from modeltranslation.translator import translator


def expand_model_fields(model, field_names):
    model_class = type(model)
    try:
        trans_field_mapping = translator.get_options_for_model(model_class).all_fields
    except modeltranslation.translator.NotRegistered:
        return field_names

    def expand_field(field_name):
        translated_versions = trans_field_mapping.get(field_name)
        if translated_versions is not None:
            return (f.name for f in translated_versions)
        else:
            return [field_name]

    return [
        expanded for unexpanded in field_names for expanded in expand_field(unexpanded)
    ]


class TranslatableSerializableMixin(SerializableMixin):
    def _resolve_field(self, model, field_description):
        field_name = field_description.get("name")

        try:
            options = translator.get_options_for_model(self._meta.model)
        except modeltranslation.translator.NotRegistered:
            return super()._resolve_field(model, field_description)

        if field_name in options.get_field_names():
            fields = sorted([f.name for f in options.all_fields.get(field_name)])
            children = [
                {
                    "key": f"{translated_field}".upper(),
                    "value": getattr(model, f"{translated_field}", ""),
                }
                for translated_field in fields
                if getattr(model, f"{translated_field}", False)
            ]

            return {
                "key": field_name.upper(),
                "children": children,
            }

        return super()._resolve_field(model, field_description)

    class Meta:
        abstract = True
