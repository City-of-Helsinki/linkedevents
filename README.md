# Linked events

REST JSON API

Installation
------------

Install required Python packages

```
(sudo) pip install -r requirements.txt
```

Create the database

```
sudo -u postgres createuser -L -R -S linkedevents
sudo -u postgres createdb -Olinkedevents linkedevents
sudo -u postgres psql linkedevents -c "CREATE EXTENSION postgis;"
```

Fetch and import the database dump
```
wget -O - http://api.hel.fi/linkedevents/static/linkedevents.dump.gz | gunzip -c > linkedevents.dump
sudo -u postgres psql linkedevents < linkedevents.dump
```

Requirements
------------

Linked Events uses two files for requirements. The workflow is as follows.

requirements.txt is not edited manually, but is generated
with 'pip freeze -lr plain-requirements.txt'.

requirements.txt always contains fully tested versions of
the requirements, including their dependencies as output
by pip freeze.

plain-requirements.txt contains the primary requirements
of the project, without version numbers and without their
dependencies.

In production, deployments should always use requirements.txt
and the versions pinned therein. In development, new virtualenvs
and development environments should also be initialised using
requirements.txt.

In development and testing, to check for new versions
of requirements, use the command 'pip-review' or requires.io.

To update ​*all*​ of the requirements to the latest versions
with a single command, use

   pip install -U -r plain-requirements.txt

After verifying that they work and optionally downgrading
some dependencies, run pip freeze.

To add a dependency, add it to plain-requirements.txt and
run 'pip install -r plain-requirements.txt'.

To remove a dependency, remove it from plain-requirements.txt
and run 'pip uninstall <NAME-OF-DEPENDENCY>'.

Important! After all changes, verify & test them, then run
'pip freeze -lr plain-requirements.txt >requirements.txt'.
Commit the changes.


Search
------

For Elasticsearch-based searching we're using the following configuration.
Place it in your `local_settings.py`:

```python
CUSTOM_MAPPINGS = {
    'autosuggest': {
        'search_analyzer': 'standard',
        'index_analyzer': 'edgengram_analyzer',
        'analyzer': None
    },
    'text': {
        'analyzer': 'default'
    }
}

HAYSTACK_CONNECTIONS = {
    'default': {
        'ENGINE': 'multilingual_haystack.backends.MultilingualSearchEngine',
    },
    'default-fi': {
        'ENGINE': 'multilingual_haystack.backends.LanguageSearchEngine',
        'BASE_ENGINE': 'events.custom_elasticsearch_search_backend.CustomEsSearchEngine',
        'URL': 'http://localhost:9200/',
        'INDEX_NAME': 'linkedevents-fi',
        'MAPPINGS': CUSTOM_MAPPINGS,
        'SETTINGS': {
            "analysis": {
                "analyzer": {
                    "default": {
                        "tokenizer": "finnish",
                        "filter": ["lowercase", "voikko_filter"]
                    }
                },
                "filter": {
                    "voikko_filter": {
                        "type": "voikko",
                    }
                }
            }
        }
    },
    'default-sv': {
        'ENGINE': 'multilingual_haystack.backends.LanguageSearchEngine',
        'BASE_ENGINE': 'events.custom_elasticsearch_search_backend.CustomEsSearchEngine',
        'URL': 'http://localhost:9200/',
        'INDEX_NAME': 'linkedevents-sv',
        'MAPPINGS': CUSTOM_MAPPINGS
    },
    'default-en': {
        'ENGINE': 'multilingual_haystack.backends.LanguageSearchEngine',
        'BASE_ENGINE': 'events.custom_elasticsearch_search_backend.CustomEsSearchEngine',
        'URL': 'http://localhost:9200/',
        'INDEX_NAME': 'linkedevents-en',
        'MAPPINGS': CUSTOM_MAPPINGS
    },
}
```
