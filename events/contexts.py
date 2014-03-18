linked_events_schema_url = "http://example.com/le/"

EVENT_CONTEXT = {
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
    "linkedEvents": linked_events_schema_url
}