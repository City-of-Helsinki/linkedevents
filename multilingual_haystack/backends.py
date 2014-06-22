# based on http://anthony-tresontani.github.io/Django/2012/09/20/multilingual-search/
import re
from django.conf import settings
from django.utils import translation
from haystack import connections
from haystack.backends import BaseEngine, BaseSearchBackend, BaseSearchQuery
from haystack.constants import DEFAULT_ALIAS
from haystack.utils.loading import load_backend


def get_using(language, alias=DEFAULT_ALIAS):
    new_using = alias + "-" + language
    using = new_using if new_using in settings.HAYSTACK_CONNECTIONS else alias
    return using

class MultilingualSearchBackend(BaseSearchBackend):
    def update(self, index, iterable, commit=True):
        initial_language = translation.get_language()[:2]
        # retrieve unique backend name
        backends = []
        for language, _ in settings.LANGUAGES:
            using = '%s-%s' % (self.connection_alias, language)
            # Ensure each backend is called only once
            if using in backends:
                continue
            else:
                backends.append(using)
            translation.activate(language)
            backend = connections[using].get_backend()
            backend.parent_class.update(backend, index, iterable, commit)

        translation.activate(initial_language)
    def clear(self, **kwargs):
        return

class MultilingualSearchQuery(BaseSearchQuery):
    def __init__(self, using=DEFAULT_ALIAS):
        language = translation.get_language()[:2]
        using = get_using(language)
        super(MultilingualSearchQuery, self).__init__(using=using)

class LanguageSearchBackend(BaseSearchBackend):
    def update(self, *args, **kwargs):
        # Handle all updates through the main Multilingual object.
        return

class LanguageSearchQuery(BaseSearchQuery):
    def __init__(self, **kwargs):
        pass

class LanguageSearchEngine(BaseEngine):
    def __init__(self, **kwargs):
        conn_config = settings.HAYSTACK_CONNECTIONS[kwargs['using']]
        base_engine = load_backend(conn_config['BASE_ENGINE'])(**kwargs)

        backend_bases = (LanguageSearchBackend, base_engine.backend)
        backend_class = type('LanguageSearchBackend', backend_bases,
                             {'parent_class': base_engine.backend})
        self.backend = backend_class

        query_bases = (LanguageSearchQuery, base_engine.query)
        query_class = type('LanguageSearchQuery', query_bases,
                           {'parent_class': base_engine.query})
        self.query = query_class

        super(LanguageSearchEngine, self).__init__(**kwargs)


class MultilingualSearchEngine(BaseEngine):
    backend = MultilingualSearchBackend
    query = MultilingualSearchQuery
