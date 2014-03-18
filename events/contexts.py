LINKED_EVENTS_SCHEMA_URL = "http://example.com/le/"


def create_context(klass):
    klass.jsonld_context = CONTEXTS[klass.__name__]
    # for name, obj in klass.__dict__.iteritems():
        # TODO: dynamically craft context based on fields

CONTEXTS = {
    "Event": {
        "@vocab": "http://schema.org/",
        "id": {
            "@id": "linkedEvents:id",
            "@type": "Integer"
        },
        "name": {
            "@id": "name",
            "@container": "@language"
        },
        "description": {
            "@id": "description",
            "@container": "@language"
        },
        "originId": {
            "@id": "linkedEvents:originId",
            "@type": "Text"
        },
        "targetGroup": {
            "@id": "linkedEvents:targetGroup",
            "@type": "Text"
        },
        "slug": {
            "@id": "linkedEvents:slug",
            "@type": "Text"
        },
        "customFields": {
            "@id": "linkedEvents:customFields",
            "@container": "@index"
        },
        "eventStatus": {
            "@type": "EventStatusType"
        },
        "linkedEvents": LINKED_EVENTS_SCHEMA_URL
    }
}