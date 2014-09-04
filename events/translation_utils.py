from modeltranslation.translator import translator

def expand_model_fields(model, field_names):
    model_class = type(model)
    trans_field_mapping = translator.get_options_for_model(model_class).fields

    def expand_field(field_name):
        translated_versions = trans_field_mapping.get(
            field_name,
            [model._meta.get_field(field_name)]
        )
        return (f for f in translated_versions)

    return [expanded.name
            for unexpanded in field_names
            for expanded in expand_field(unexpanded)]
