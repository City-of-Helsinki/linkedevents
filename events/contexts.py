"""
Most of the types and properties used are found from schema.org
but customized properties and types should be defined in @context
to add semantic spice in JSONs.
"""
from events import utils

LINKED_EVENTS_SCHEMA_URL = "http://example.com/le/"


def create_context(klass):
    klass.jsonld_context = {
        "@vocab": "http://schema.org/",
        "linkedEvents": LINKED_EVENTS_SCHEMA_URL
    }
    for name in klass._meta.get_all_field_names():
        #name = utils.convert_to_camelcase(name)
        if klass.__name__ in CONTEXTS and name in CONTEXTS[klass.__name__]:
            klass.jsonld_context[name] = CONTEXTS[klass.__name__][name]
        elif name in CONTEXTS:
            klass.jsonld_context[name] = CONTEXTS[name]

CONTEXTS = {
    # General contexts
    "name": {
        "@container": "@language"
    },
    "url": {
        "@container": "@language"
    },
    "description": {
        "@container": "@language"
    },
    "street_address": {
        "@container": "@language"
    },
    "address_locality": {
        "@container": "@language"
    },
    "origin_id": {
        "@id": "linkedEvents:originId",
        "@type": "Text"
    },
    "target_group": {
        "@id": "linkedEvents:targetGroup",
        "@type": "Text"
    },
    "slug": {
        "@id": "linkedEvents:slug",
        "@type": "Text"
    },
    "custom_fields": {
        "@id": "linkedEvents:customFields",
        "@container": "@index"
    },
    "data_source": {
        "@id": "linkedEvents:dataSource",
        "@type": "Text"
    },
    # Place specific contexts
    "Place": {
        "location": {
            "@id": "linkedEvents:geo",
            "Point": "http://geovocab.org/geometry#Point",
            "coordinates": "_:n1",
            "type": "@type"
        },
    }

}
