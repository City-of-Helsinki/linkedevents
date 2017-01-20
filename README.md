# Linked events

[![Build status](https://travis-ci.org/City-of-Helsinki/linkedevents.svg)](https://travis-ci.org/City-of-Helsinki/linkedevents)
[![Requirements](https://requires.io/github/City-of-Helsinki/linkedevents/requirements.svg?branch=master)](https://requires.io/github/City-of-Helsinki/linkedevents/requirements/?branch=master)
[![Stories in Ready](https://badge.waffle.io/City-of-Helsinki/linkedevents.svg?label=ready&title=Ready)](http://waffle.io/City-of-Helsinki/linkedevents)

Linked Events provides categorized data on events and places. The project was originally developed for the City of Helsinki.

[The Linked Events API for the Helsinki capital region](http://api.hel.fi/linkedevents/) contains data from the Helsinki City Tourist & Convention Bureau, the City of Helsinki Cultural Office and the Helmet metropolitan area public libraries.


Installation
------------

Prepare virtualenv

```bash
virtualenv -p /usr/bin/python3 ~/.virtualenvs/
workon linkedevents
```
Install required Python packages

```bash
(sudo) pip install -r requirements.txt
```

Create the database

```
sudo -u postgres createuser -R -S linkedevents
# Following is for US locale, we are not certain whether Linkedevents
# behaves differently depending on DB collation & ctype
#sudo -u postgres createdb -Olinkedevents linkedevents
# This is is for Finnish locale
sudo -u postgres createdb -Olinkedevents -Ttemplate0 -lfi_FI.UTF-8 linkedevents
sudo -u postgres psql linkedevents -c "CREATE EXTENSION postgis;"
sudo -u postgres psql linkedevents -c "CREATE EXTENSION hstore;"
# This fills the database with a basic skeleton
python manage.py migrate
```

You probably want to import some data for testing (these are events around Helsinki)
```
# Import places from Helsinki service registry (used by events from following sources)
python manage.py event_import tprek --places
# Import events from Visit Helsinki
python manage.py event_import matko --events
# Import events from Helsinki metropolitan region libraries
python manage.py event_import helmet --events
# Rebuild search index (for /search endpoint)
python manage.py rebuild_index

```

Finally, you may install city-specific HTML page templates for the browsable API by
```bash
python manage.py install_templates helevents
```
This will install the `helevents/templates/rest_framework/api.html` template,
which contains Helsinki event data summary and license. Customize the template
for your favorite city by creating `your_favorite_city/templates/rest_framework/api.html`.
[Customizing the browsable API](http://www.django-rest-framework.org/topics/browsable-api/#customizing)

Running tests
------------
Tests must be run using an user who can create (and drop) databases and write the directories
your linkedevents installation resides in.
```
py.test events
```

Requirements
------------

Linked Events uses two files for requirements. The workflow is as follows.

`requirements.txt` is not edited manually, but is generated
with `pip-compile`.

`requirements.txt` always contains fully tested, pinned versions
of the requirements. `requirements.in` contains the primary, unpinned
requirements of the project without their dependencies.

In production, deployments should always use `requirements.txt`
and the versions pinned therein. In development, new virtualenvs
and development environments should also be initialised using
`requirements.txt`. `pip-sync` will synchronize the active
virtualenv to match exactly the packages in `requirements.txt`.

In development and testing, to update to the latest versions
of requirements, use the command `pip-compile`. You can
use [requires.io](https://requires.io) to monitor the
pinned versions for updates.

To remove a dependency, remove it from `requirements.in`,
run `pip-compile` and then `pip-sync`. If everything works
as expected, commit the changes.


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
