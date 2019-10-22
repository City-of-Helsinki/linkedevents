# Linked events

[![Build status](https://travis-ci.org/City-of-Helsinki/linkedevents.svg)](https://travis-ci.org/City-of-Helsinki/linkedevents)
[![codecov](https://codecov.io/gh/City-of-Helsinki/linkedevents/branch/master/graph/badge.svg)](https://codecov.io/gh/City-of-Helsinki/linkedevents)
[![Requirements](https://requires.io/github/City-of-Helsinki/linkedevents/requirements.svg?branch=master)](https://requires.io/github/City-of-Helsinki/linkedevents/requirements/?branch=master)
[![Gitter](https://img.shields.io/gitter/room/City-of-Helsinki/heldev.svg?maxAge=2592000)](https://gitter.im/City-of-Helsinki/heldev)

Linked Events provides categorized data on events and places. The project was originally developed for the City of Helsinki.

[The Linked Events API for the Helsinki capital region](http://api.hel.fi/linkedevents/) contains data from the Helsinki City Tourist & Convention Bureau, the City of Helsinki Cultural Office and the Helmet metropolitan area public libraries.

*Linked Events has been updated to Django 1.11. To upgrade to Linked Events release v2.0, please upgrade to release v1.3 first.*

Set up project with Docker
--------------------------

1. Create `local_settings.py` from the template:
    * `cp local_settings.py.template local_settings.py`

2. Run `docker-compose up`

3. Run migrations:
    * `docker exec linkedevents-backend python manage.py migrate`

4. Syncronize languages for translations in DB:
    * `docker exec -it linkedevents-backend python manage.py sync_translation_fields`
    * Answer `y` (for 'yes') to all prompt questions

If you wish to install Linkedevents without any Helsinki specific data (an empty database), and instead customize everything for your own city, you may jump to step 11.

Steps 5-10 are needed if you wish to use location, address or event data from the Helsinki metropolitan region, or if you wish to run the Helsinki UI (https://linkedevents.hel.fi) from https://github.com/City-of-Helsinki/linkedevents-ui. Currently, the UI is specific to Helsinki and requires the general Finnish ontology as well as additional Helsinki specific audiences and keywords to be present, though its code should be easily adaptable to your own city if you have an OAuth2 authentication server present.

5. (Optionally) import general Finnish ontology (used by Helsinki UI and Helsinki events):
    * `docker exec -it linkedevents-backend python manage.py event_import yso --all`
6. (Optionally) add helsinki specific audiences and keywords:
    ```bash
    # Add keyword set to display in the UI event audience selection
    docker exec -it linkedevents-backend python manage.py add_helsinki_audience
    # Add keyword set to display in the UI main category selection
    docker exec -it linkedevents-backend python manage.py add_helfi_topics
    ```
7. (Optionally) import places and events for testing:
    ```bash
    # Import places from Helsinki metropolitan region service registry (used by events from following sources)
    docker exec -it linkedevents-backend python manage.py event_import tprek --places
    # Import places from Helsinki metropolitan region address registry (used as fallback locations)
    docker exec -it linkedevents-backend python manage.py event_import osoite --places
    # Import events from Helsinki metropolitan region libraries
    docker exec -it linkedevents-backend python manage.py event_import helmet --events
    # Import events from Espoo
    docker exec -it linkedevents-backend python manage.py event_import espoo --events
8. (Optionally) import City of Helsinki internal organization for UI user rights management:
    * `docker exec -it linkedevents-backend python manage.py import_organizations https://api.hel.fi/paatos/v1/organization/ -s helsinki:ahjo`
9. (Optionally) install API frontend templates:
    * `docker exec -it linkedevents-backend python manage.py install_templates helevents`
10. (Optionally) import Finland municipalities and Helsinki administrative divisions, if you want to use district based API filtering of events:
    ```bash
    # Import municipalities in Finland
    docker exec -it linkedevents-backend python manage.py geo_import finland --municipalities
    # Import districts in Helsinki
    docker exec -it linkedevents-backend python manage.py geo_import helsinki --divisions
    ```

Finish the install:

11. (Optionally) install Elasticsearch reading the [instructions below](#search). This is an optional feature. If you do not wish to install Elasticsearch, all the endpoints apart from `/v1/search` will function normally, and the `/v1/search` endpoint does a dumb exact text match for development purposes.

12. Start your Django server:
    * `docker exec -it linkedevents-backend python manage.py runserver 0:8000`

Now your project is live at [localhost:8000](http://localhost:8000)

For UI, set authentication keys to local_settings.

Installation for development
----------------------------
These instructions assume an $INSTALL_BASE, like so:
```bash
INSTALL_BASE=$HOME/linkedevents
```
If you've already cloned this repository, just move repository root into $INSTALL_BASE/linkedevents. Otherwise just clone the repository, like so:
```bash
git clone https://github.com/City-of-Helsinki/linkedevents.git $INSTALL_BASE/linkedevents
```
Prepare Python 3.x virtualenv using your favorite tools and activate it. Plain virtualenv is like so:
```bash
virtualenv -p python3 $INSTALL_BASE/venv
source $INSTALL_BASE/venv/bin/activate
```
Install required Python packages into the virtualenv
```bash
cd $INSTALL_BASE/linkedevents
pip install -r requirements.txt
```
Create the database, like so: (we have only tested on PostgreSQL)
```bash
cd $INSTALL_BASE/linkedevents
sudo -u postgres createuser -R -S linkedevents
# Following is for US locale, we are not certain whether Linkedevents
# behaves differently depending on DB collation & ctype
#sudo -u postgres createdb -Olinkedevents linkedevents
# This is is for Finnish locale
sudo -u postgres createdb -Olinkedevents -Ttemplate0 -lfi_FI.UTF-8 linkedevents
# Create extensions in the database
sudo -u postgres psql linkedevents -c "CREATE EXTENSION postgis;"
sudo -u postgres psql linkedevents -c "CREATE EXTENSION hstore;"
# This fills the database with a basic skeleton
python manage.py migrate
# This adds language fields based on settings.LANGUAGES (which may be missing in external dependencies)
python manage.py sync_translation_fields
```

If you wish to install Linkedevents without any Helsinki specific data (an empty database), and instead customize everything for your own city, you have a working install right now.

The last steps are needed if you wish to use location, address or event data from the Helsinki metropolitan region, or if you wish to run the Helsinki UI (https://linkedevents.hel.fi) from https://github.com/City-of-Helsinki/linkedevents-ui. Currently, the UI is specific to Helsinki and requires the general Finnish ontology as well as additional Helsinki specific audiences and keywords to be present, though its code should be easily adaptable to your own city if you have an OAuth2 authentication server present.

```bash
cd $INSTALL_BASE/linkedevents
# Import general Finnish ontology (used by Helsinki UI and Helsinki events)
python manage.py event_import yso --all
# Add keyword set to display in the UI event audience selection
python manage.py add_helsinki_audience
# Add keyword set to display in the UI main category selection
python manage.py add_helfi_topics
# Import places from Helsinki metropolitan region service registry (used by events from following sources)
python manage.py event_import tprek --places
# Import places from Helsinki metropolitan region address registry (used as fallback locations)
python manage.py event_import osoite --places
# Import events from Helsinki metropolitan region libraries
python manage.py event_import helmet --events
# Import events from Espoo
python manage.py event_import espoo --events
# Import City of Helsinki hierarchical organization for UI user rights management
python manage.py import_organizations https://api.hel.fi/paatos/v1/organization/ -s helsinki:ahjo
# Import municipalities in Finland
python manage.py geo_import finland --municipalities
# Import districts in Helsinki
python manage.py geo_import helsinki --divisions
# install API frontend templates:
python manage.py install_templates helevents
```

The last command installs the `helevents/templates/rest_framework/api.html` template,
which contains Helsinki event data summary and license. You may customize the template
for your favorite city by creating `your_favorite_city/templates/rest_framework/api.html`.
For further erudition, take a look at the DRF documentation on [customizing the browsable API](http://www.django-rest-framework.org/topics/browsable-api/#customizing)

After this, everything but search endpoint (/search) is working. See [search](#search)

Production notes
----------------

Development installation above will give you quite a serviceable production installation for lightish usage. You can serve out the application using your favorite WSGI-capable application server. The WSGI-entrypoint for Linked Events is ```linkedevents.wsgi``` or in file ```linkedevents/wsgi.py```. Former is used by gunicorn, latter by uwsgi. The callable is ```application```.

You will also need to serve out ```static``` and ```media``` folders at ```/static``` and ```/media``` in your URL space.

Running tests
------------
Tests must be run using an user who can create (and drop) databases and write the directories
your linkedevents installation resides in. Also the template database must include Postgis and
HSTORE-extensions. If you are developing, you probably want to give those
permissions to the database user configured in your development instance. Like so:

```bash
# Change this if you have different DB user
DATABASE_USER=linkedevents
# Most likely you have a postgres system user that can log into postgres as DB postgres user
sudo -u postgres psql << EOF
ALTER USER "$DATABASE_USER" CREATEDB;
\c template1
CREATE EXTENSION IF NOT EXISTS postgis;
CREATE EXTENSION IF NOT EXISTS hstore;
EOF

```

Afterwards you can run the tests:
```bash
cd $INSTALL_BASE/linkedevents
py.test events
```

Note that search tests will fail unless you configure [search](#search)

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
Linkedevents uses Elasticsearch for generating results on the /search-endpoint. If you wish to use that functionality, proceed like so:

1. Install elasticsearch

    We've only tested using the rather ancient 1.7 version. Version 5.x will certainly not work as the `django-haystack`-library does not support it. If you are using Ubuntu 16.04, 1.7 will be available in the official repository.

2. (For Finnish support) Install elasticsearch-analyzer-voikko, libvoikko and needed dictionaries

    `/usr/share/elasticsearch/bin/plugin -i fi.evident.elasticsearch/elasticsearch-analysis-voikko/0.4.0`
    This specific command is for Debian derivatives. The path to `plugin` command might be different on yours. Note that version 0.4.0 is the one compatible with Elasticsearch 1.7

    Installing libvoikko:
    `apt-get install libvoikko1`

    Installing the dictionaries (v5 dictionaries are needed for libvoikko version included in Ubuntu 16.04):

    ```
    wget -P $INSTALL_BASE http://www.puimula.org/htp/testing/voikko-snapshot-v5/dict-morpho.zip
    unzip $INSTALL_BASE/dict-morpho.zip -d /etc/voikko
    ```

3. Configure the thing

    Set the `ELASTICSEARCH_URL` environment variable (or variable in `config_dev.toml`, if you are running in development mode) to your elasticsearch instance. The default value is `http://localhost:9200/`.

    Haystack configuration for all Linkedevents languages happens automatically if `ELASTICSEARCH_URL` is set, but you may customize it manually using `local_settings.py` if you know Haystack and wish to do so.

4. Rebuild the search indexes

   `python manage.py rebuild_index`

   You should now have a working /search endpoint, give or take a few.

Event extensions
----------------

It is possible to extend event data and API without touching `events` application by implementing separate extension applications. These extensions will be wired under field `extension_<extension idenfier>` in event API. If not auto enabled (see 6. below), extensions can be enabled per request using query param `extensions` with comma separated identifiers as values, or `all` for enabling all the extensions.

To implement an extension:

1) Create a new Django application, preferably named `extension_<unique identifier for the extension>`.

2) If you need to add new data for events, implement that using model(s) in the extension application.

3) Inherit `events.extensions.EventExtension` and implement needed attributes and methods. See [extensions.py](events/extensions.py) for details.

4) Add `event_extension: <your EventExtension subclass>` attribute to the extension applications's `AppConfig`.

5) Make the extension available by adding the extension application to `INSTALLED_APPS`.

6) If you want to force the extension to be enabled on every request, add the extension's identifier to `AUTO_ENABLED_EXTENSIONS` in Django settings.

For an example extension implementation, see [course extension](extension_course).
