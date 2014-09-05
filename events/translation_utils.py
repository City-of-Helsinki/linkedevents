import modeltranslation
from modeltranslation.translator import translator

def expand_model_fields(model, field_names):
    model_class = type(model)
    try:
        trans_field_mapping = translator.get_options_for_model(model_class).fields
    except modeltranslation.translator.NotRegistered:
        return field_names

    def expand_field(field_name):
        translated_versions = trans_field_mapping.get(field_name)
        if translated_versions is not None:
            return (f.name for f in translated_versions)
        else:
            return [field_name]

    return [expanded
            for unexpanded in field_names
            for expanded in expand_field(unexpanded)]
