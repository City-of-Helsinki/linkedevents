from haystack.backends import elasticsearch_backend as es_backend
from haystack.query import SearchQuerySet
from .utils import update


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
        settings = connection_options.get('SETTINGS')
        if settings:
            default_settings = self.DEFAULT_SETTINGS['settings']
            update(default_settings, settings)

    def build_schema(self, fields):
        content_field_name, mappings = (
            super(CustomEsSearchBackend, self).build_schema(fields)
        )
        if not self.custom_mappings:
            return (content_field_name, mappings)

        for index_fieldname, mapping in self.custom_mappings.items():
            target = mappings.setdefault(index_fieldname, {})
            for key, value in mapping.items():
                if value is None and key in target:
                    del target[key]
                else:
                    target[key] = value
        return (content_field_name, mappings)

    def build_search_kwargs(self, query_string, decay_functions=None, **kwargs):
        kwargs = super(CustomEsSearchBackend, self).build_search_kwargs(
            query_string, **kwargs)
        if not decay_functions:
            return kwargs

        original_query = kwargs['query']
        function_score_query = {
            'function_score': {
                'functions': decay_functions,
                'query': original_query,
                'score_mode': 'multiply'
            }
        }
        kwargs['query'] = function_score_query
        return kwargs


class CustomEsSearchQuery(es_backend.ElasticsearchSearchQuery):
    def __init__(self, **kwargs):
        super(CustomEsSearchQuery, self).__init__(**kwargs)
        self.decay_functions = []

    def build_params(self, *args, **kwargs):
        search_kwargs = super(CustomEsSearchQuery, self).build_params(*args, **kwargs)
        if self.decay_functions:
            search_kwargs['decay_functions'] = self.decay_functions
        return search_kwargs

    def add_decay_function(self, function_dict):
        self.decay_functions.append(function_dict)

    def _clone(self, **kwargs):
        clone = super(CustomEsSearchQuery, self)._clone(**kwargs)
        clone.decay_functions = self.decay_functions[:]
        return clone


class CustomEsSearchQuerySet(SearchQuerySet):
    """
    usage example:
    SearchQuerySet().filter(text='konsertti').decay({'gauss': {'end_time' : {'origin': '2014-05-07', 'scale' : '10d' }}}
    """

    def decay(self, function_dict):
        clone = self._clone()
        clone.query.add_decay_function(function_dict)
        return clone


class CustomEsSearchEngine(es_backend.ElasticsearchSearchEngine):
    backend = CustomEsSearchBackend
    query = CustomEsSearchQuery
