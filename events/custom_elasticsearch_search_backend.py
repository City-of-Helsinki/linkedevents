from haystack.backends import elasticsearch_backend as es_backend

class CustomEsSearchBackend(es_backend.ElasticsearchSearchBackend):
    """ A slight modification of the default Haystack elasticsearch
    backend which allows custom mapping configurations for specified
    fields in the connection options.

    Configure with a MAPPING key in the connection settings
    dictionary, containing a dictionary of 
    field-name to mapping configurations.
    """
    def __init__(self, connection_alias, **connection_options):
        super(CustomEsSearchBackend, self).__init__(
            connection_alias, **connection_options
        )
        self.custom_mappings = connection_options.get('MAPPINGS')

    def build_schema(self, fields):
        content_field_name, mappings = (
            super(CustomEsSearchBackend, self).build_schema(fields)
        )
        if not self.custom_mappings:
            return (content_field_name, mappings)

        for index_fieldname, mapping in self.custom_mappings.items():
            target = mappings.get(index_fieldname, {})
            for key, value in mapping.items():
                if value is None and key in target:
                    del target[key]
                else:
                    target[key] = value
        return (content_field_name, mappings)

class CustomEsSearchEngine(es_backend.ElasticsearchSearchEngine):
    backend = CustomEsSearchBackend
