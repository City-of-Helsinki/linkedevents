# Linked Events
[![codecov](https://codecov.io/gh/City-of-Helsinki/linkedevents/branch/master/graph/badge.svg)](https://codecov.io/gh/City-of-Helsinki/linkedevents)
[![Gitter](https://img.shields.io/gitter/room/City-of-Helsinki/heldev.svg?maxAge=2592000)](https://gitter.im/City-of-Helsinki/heldev)

![High-level diagram of Linked Events](./assets/Linked_Events.jpg?raw=true)


#### TL;DR => Linked Events is a REST API which allows you to set up an _**event**_* publication hub.

\*_**event**_  here means a happening where people get together and do something.


Linked Events is event information:

  * *Aggregator* => using Python importers which have the logic to import events information from different data sources
  * *Creator* => by offering PUT/POST `/event` API endpoint with granular user permissions and a hierarchical organization structure supporting different publishing rights for different organizations
  * *Publisher* => by offering API endpoints from which interested parties can retrieve information about events

Linked Events was originally developed for City of Helsinki organization and
you can see the Linked Events API in action for [Helsinki capital region here](https://api.hel.fi/linkedevents/v1/).
It contains data from all Helsinki City Departments as well as data from Helsinki Marketing and the Helmet metropolitan area public libraries. Viewing the API should give a reasonable view for the kind of information Linked Events is targeted for.

Target audience of this README.md are developers who may or may not have a lot of Python
experience and would like to get things running as quickly as possible.
Therefore, instructions written in this README.md should be written accordingly.


## Contributing

The best way to contribute is to open a new PR for discussion. We strive to be able to support various cities with various use cases, so suggestions and new features (as long as they fit in with existing functionality) are welcome.


## How to setup your local development environment
If all you want is a barebone application to work with for your own city:

* Copy `./docker/django/.env.example` to `./docker/django/.env` and change the variable values to your liking.
* Start django application and database server:
  ```
  docker-compose up
  ```

* Access application on [localhost:8000](http://localhost:8000)

* You are done 🔥

If you wish to use locations, addresses and events data from the Helsinki capital region:

* Read [linked-events-importers.md](./linked-events-importers.md#linked-events-importers-and-commands) and decide the importers or commands you would like to use.

* You can then serve the [UI for Linked Events API](https://github.com/City-of-Helsinki/linkedevents-ui) for example by setting authentication keys to `local_settings.py`

* UI app is specific to Helsinki at the moment and requires general Finnish ontology as well as additional Helsinki specific audiences
and keywords to be present. However, UI code should be easily adaptable to your own city if you have an OAuth2 authentication server present


## Development installation on physical or virtual machine

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

Install Voikko by following [these](https://voikko.puimula.org/python.html) instructions.
Recommendation is to use "morpho" Finnish language dictionary.

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
# This creates language objects with correct translations
python manage.py create_languages
```

If you wish to install Linkedevents without any Helsinki specific data (an empty database), and instead customize everything for your own city, you have a working install right now.

The last steps are needed if you wish to use location, address or event data from the Helsinki metropolitan region, or if you wish to run the Helsinki UI (https://linkedevents.hel.fi) from https://github.com/City-of-Helsinki/linkedevents-ui. Currently, the UI is specific to Helsinki and requires the general Finnish ontology as well as additional Helsinki specific audiences and keywords to be present, though its code should be easily adaptable to your own city if you have an OAuth2 authentication server present.

The commands below are documented in more detail in [linked-events-importers.md](./linked-events-importers.md#linked-events-importers-and-commands).

```bash
cd $INSTALL_BASE/linkedevents
# Import general Finnish ontology (used by Helsinki UI and Helsinki events)
python manage.py event_import yso --all
# Add keyword set to display in the UI event audience selection
python manage.py add_helsinki_audience
# Add keyword set to display in the UI main category selection
python manage.py add_helsinki_topics
# Add kasko related keywords
python manage.py add_kasko_keywords
# Import places from Helsinki metropolitan region service registry (used by events from following sources)
python manage.py event_import tprek --places
# Import places from Helsinki metropolitan region address registry (used as fallback locations)
python manage.py event_import osoite --places
# Import events from Helsinki metropolitan region libraries
python manage.py event_import helmet --events
# Import events from Espoo
python manage.py event_import espoo --events
# Import City of Helsinki hierarchical organization for UI user rights management
python manage.py import_organizations https://dev.hel.fi/paatokset/v1/organization/?limit=1000 -c openahjo -s OpenAhjoAPI:ahjo
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


## Development in macOS (linux/arm64)
* Note: Processor architecture on Apple-silicon machines is ARM64, not AMD64.
  If you have one of these extra tinkering is needed.
  On Intel-silicon machines, this is not necessary.
* Note 2: As AMD64 is emulated on top of ARM64 Linux, this isn't fast.
1. Pre-build linux/AMD64-versions
   1. PostgreSQL-container:
       ```bash
       podman build --platform=linux/amd64 \
         -f docker/postgres/Dockerfile  \
         .
       ```
   1. Django-container:
       ```bash
       podman build --platform=linux/amd64 \
         -f docker/postgres/Dockerfile  \
         .
       ```
2. Now `podman-compose` will find pre-built alternate architecture container images and will run ok:
    ```bash
    podman-compose up
    ```
3. Done, test @ http://127.0.0.1:8000/

### GIS
* Problem on macOS:
    ```text
    django.contrib.gis.geos.error.GEOSException: Error encountered checking Geometry returned from GEOS C function "GEOSGeom_createCollection_r".
    ```
  * See: https://github.com/django/django/pull/15214
* Fix:
  * Edit `.zshrc` / `.bashrc` / `.bash_profile` and add the following lines:
    ```text
    # macOS:
    export GDAL_LIBRARY_PATH=/opt/homebrew/lib/libgdal.dylib
    export GEOS_LIBRARY_PATH=/opt/homebrew/lib/libgeos_c.dylib
    ```

### Troubleshooting
* Problem:
  _Error: no container with name or ID "linkedevents-backend" found: no such container_
  * Solution:
    You missed the part with: Copy `./docker/django/.env.example` to `./docker/django/.env`

* Problem:
  TCP-ports not available in host
  * Solution:
    If port forwarding from VM is flaky, native ports are visible.
    Django should be visible in http://127.0.0.1:8080/

## Production notes

Development installation above will give you quite a serviceable production installation for lightish usage. You can serve out the application using your favorite WSGI-capable application server. The WSGI-entrypoint for Linked Events is ```linkedevents.wsgi``` or in file ```linkedevents/wsgi.py```. Former is used by gunicorn, latter by uwsgi. The callable is ```application```.

You will also need to serve out ```static``` and ```media``` folders at ```/static``` and ```/media``` in your URL space.


## Running tests

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
CREATE EXTENSION IF NOT EXISTS pg_trgm;
EOF

```

Afterwards you can run the tests:
```bash
cd $INSTALL_BASE/linkedevents
py.test events
```

Note that search tests will fail unless you configure [search](#search)


## Sending email
The project uses [django-mailer](https://github.com/pinax/django-mailer) for queuing and sending email. When a normal Django email function like `send_mail` is called, the email will be stored into a queue that exists in the database for later sending.

`django-mailer` comes with a number of management commands for interacting with the email queue. Out of those, the `send_mail` command is for us perhaps the most notable one as it is responsible for the actual sending of the queued messages.

To send messages locally, you can run the `send_mail` command:
`./manage.py send_mail`

For more information about `django-mailer` and the management commands, you can refer to the [usage documentation](https://github.com/pinax/django-mailer/blob/master/docs/usage.rst).


## Requirements

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


## Code format

This project uses [Ruff](https://docs.astral.sh/ruff/) for code formatting and quality checking.

Basic `ruff` commands:

* lint: `ruff check`
* apply safe lint fixes: `ruff check --fix`
* check formatting: `ruff format --check`
* format: `ruff format`

[`pre-commit`](https://pre-commit.com/) can be used to install and
run all the formatting tools as git hooks automatically before a
commit.


## Git blame ignore refs

Project includes a `.git-blame-ignore-revs` file for ignoring certain commits from `git blame`.
This can be useful for ignoring e.g. formatting commits, so that it is more clear from `git blame`
where the actual code change came from. Configure your git to use it for this project with the
following command:

```shell
git config blame.ignoreRevsFile .git-blame-ignore-revs
```


## Commit message format

New commit messages must adhere to the [Conventional Commits](https://www.conventionalcommits.org/)
specification, and line length is limited to 72 characters.

When [`pre-commit`](https://pre-commit.com/) is in use, [`commitlint`](https://github.com/conventional-changelog/commitlint)
checks new commit messages for the correct format.


## Search

Linkedevents uses Elasticsearch for generating results on the /search-endpoint. If you wish to use that functionality, proceed like so:

1. Install elasticsearch

    We've only tested using the rather ancient 1.7 version. If you are using Ubuntu 16.04, 1.7 will be available in the official repository.
    This limitation was originally due to django-haystack not supporting versions above 1.
    As of writing this the django-haystack version in use does support versions 1, 2, 5 and 7.

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

    Set the `ELASTICSEARCH_URL` environment variable (or variable in `config_dev.env`, if you are running in development mode) to your elasticsearch instance. The default value is `http://localhost:9200/`.

    Haystack configuration for all Linkedevents languages happens automatically if `ELASTICSEARCH_URL` is set, but you may customize it manually using `local_settings.py` if you know Haystack and wish to do so.

4. Rebuild the search indexes

   `python manage.py rebuild_index`

   You should now have a working /search endpoint, give or take a few.


## Event extensions

It is possible to extend event data and API without touching `events` application by implementing separate extension applications. These extensions will be wired under field `extension_<extension idenfier>` in event API. If not auto enabled (see 6. below), extensions can be enabled per request using query param `extensions` with comma separated identifiers as values, or `all` for enabling all the extensions.

To implement an extension:

1) Create a new Django application, preferably named `extension_<unique identifier for the extension>`.

2) If you need to add new data for events, implement that using model(s) in the extension application.

3) Inherit `events.extensions.EventExtension` and implement needed attributes and methods. See [extensions.py](events/extensions.py) for details.

4) Add `event_extension: <your EventExtension subclass>` attribute to the extension applications's `AppConfig`.

5) Make the extension available by adding the extension application to `INSTALLED_APPS`.

6) If you want to force the extension to be enabled on every request, add the extension's identifier to `AUTO_ENABLED_EXTENSIONS` in Django settings.

For an example extension implementation, see [course extension](extension_course).


## Swagger documentation

Swagger documentation is available at the endpoint `/docs/swagger-ui/`. The schema is generated using [drf-spectacular](https://github.com/tfranzel/drf-spectacular).

Development/local servers use a dynamic schema that is generated on-the-fly, and production servers use a pregenerated static YAML file.

To create or update a static YAML file for testing purposes, etc., you may run the following management command:

```shell
./manage.py spectacular --file <file_name> --lang en --validate --fail-on-warn --api-version v1
```
To make your local Linked Events instance use the static file, the environment variable `SWAGGER_USE_STATIC_SCHEMA` should be set to `true`.
