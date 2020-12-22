# Linked Events

[![Build status](https://travis-ci.org/City-of-Helsinki/linkedevents.svg)](https://travis-ci.org/City-of-Helsinki/linkedevents)
[![codecov](https://codecov.io/gh/City-of-Helsinki/linkedevents/branch/master/graph/badge.svg)](https://codecov.io/gh/City-of-Helsinki/linkedevents)
[![Requirements](https://requires.io/github/City-of-Helsinki/linkedevents/requirements.svg?branch=master)](https://requires.io/github/City-of-Helsinki/linkedevents/requirements/?branch=master)
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

Target audience of this README.md are developers who may or maynot have a lot of Python
experience and would like to get things running as quickly as possible.
Therefore, instructions written in this README.md should be written accordingly.

## Contributing

The best way to contribute is to open a new PR for discussion. We strive to be able to support various cities with various use cases, so suggestions and new features (as long as they fit in with existing functionality) are welcome.

## Syncing changes from Helsinki's Linked Events

### Syncing all latest changes

If you haven't already set Helsinki's Linked Events repository as a remote, you can do so by running (for more
information, see https://docs.github.com/en/free-pro-team@latest/github/collaborating-with-issues-and-pull-requests/configuring-a-remote-for-a-fork):

```
git remote add upstream https://github.com/City-of-Helsinki/linkedevents.git
```

To sync the changes via a feature branch and a pull request, run:

```
# Fetch the latest changes from Helsinki's Linked Events
git fetch upstream

# Ensure that your Espoo Events fork master branch is up-to-date
git pull origin master

# Create new feature branch for the changes in Helsinki's Linked Events
git checkout -b feat/sync-with-linkedevents master

# Merge the changes from Helsinki's Linked Events to the feature branch. Note that there may be conflicts that you need
# to resolve before you can commit the changes. If there are any other changes that you need to do related to the synced
# changes, it might be better to do them in their own commits instead of in the merge commit. This way, it might be
# clearer what the other changes are.
# NOTE! Remember to run any git rebase commands for the feature branch with caution after you've merged the upstream
# changes since rebasing can in certain situations mess the merged commits. For instance, dont' use
# "git rebase -i origin/master". Instead, you can use "git rebase -i HEAD~2" where the integer is the number of commits
# from HEAD to the first commit after the merge commit.
git merge upstream/master

# Push the feature branch to GitHub and create a pull request. Also, remember to document clearly what changes might
# have been necessary to resolve any conflicts so that it's easier to distinguish how Espoo Events differs from
# Helsinki's Linked Events.
git push -u origin feat/sync-with-linkedevents
```

Another possibility is to merge the synced changes directly to the master branch (https://docs.github.com/en/free-pro-team@latest/github/collaborating-with-issues-and-pull-requests/syncing-a-fork):
```
git fetch upstream
git checkout master
git merge upstream/master
# This requires that GitHub's protection setting is disabled for the master branch
git push origin master
```

The benefit of the first approach is that the pull request groups together all of the synced changes so that it's easier
to see what's changed.

### Syncing a specific pull request

If you for some reason want to sync a specific pull request, e.g., because the pull request has been submitted to the
upstream but it hasn't been merged yet, you can run the following commands:

```
# Ensure that your Espoo Events fork master branch is up-to-date
git pull origin master

# Create new feature branch for the changes that you want to sync
git checkout -b feat/sync-linkedevents-pr master

# Fetch the specific pull request and create a new local branch for it
# Format: git fetch upstream refs/pull/{pr_id}/head:linkedevents-pr-{pr_id}, where "pr_id" is the id of the pull request
# and "linkedevents-pr-{pr_id}" is the name of the local branch to be created. For instance:
git fetch upstream refs/pull/438/head:linkedevents-pr-438

# Merge the PR changes from Helsinki's Linked Events to the feature branch. Note that there may be conflicts that you
# need to resolve before you can commit the changes. If there are any other changes that you need to do related to the
# synced changes, it might be better to do them in their own commits instead of in the merge commit. This way, it might
# be clearer what the other changes are.
# NOTE! Remember to run any git rebase commands for the feature branch with caution after you've merged the upstream
# changes since rebasing can in certain situations mess the merged commits. For instance, dont' use
# "git rebase -i origin/master". Instead, you can use "git rebase -i HEAD~2" where the integer is the number of commits
# from HEAD to the first commit after the merge commit.
git merge linkedevents-pr-438

# Push the feature branch to GitHub and create a pull request. Also, remember to document clearly what changes might
# have been necessary to resolve any conflicts so that it's easier to distinguish how Espoo Events differs from
# Helsinki's Linked Events.
git push -u origin feat/sync-linkedevents-pr
```

## How to setup your local development environment
If all you want is a barebone application to work with for your own city:

* Copy `config_dev.toml.example` to `config_dev.toml`
    * Change settings where needed

* Run `bin/git-hooks.sh` which will set the required Git Hooks that will handle commit message linting and git-secrets.
  Install the following tools for the git hooks to work correctly:
    * To prevent commiting AWS credentials, install [git-secrets](https://github.com/awslabs/git-secrets)
    * To prevent other secrets from slipping to GitHub, install [truffleHog](https://github.com/dxa4481/truffleHog).
      truffleHog supports checking secrets only in commits so that's why truffleHog is only run in the pre-push hook.
    * To validate the CircleCI config, install [circleci-cli](https://github.com/CircleCI-Public/circleci-cli)
    * To lint yaml files, install [yamllint](https://github.com/adrienverge/yamllint)

* Start django application and database server:
  ```
  docker-compose up
  ```

* Access application on [localhost:8000](http://localhost:8000)

* You are done 🔥

* Optional: Helsinki TPREK importer should not need elasticsearch, but at the time of writing it doesn't work without
    * One solution for dev would be to make a local `docker-compose.override.yml` and spin one from there

If you wish to use locations, addresses and events data from the Helsinki capital region:

* Read [linked-events-importers.md](./linked-events-importers.md#linked-events-importers-and-commands) and decide the importers or commands you would like to use.

* You can then serve the [UI for Linked Events API](https://github.com/City-of-Helsinki/linkedevents-ui) for example by setting authentication keys to `local_settings.py`

* UI app is specific to Helsinki at the moment and requires general Finnish ontology as well as additional Helsinki specific audiences
and keywords to be present. However, UI code should be easily adaptable to your own city if you have an OAuth2 authentication server present

A few words about authentication
----------------------------
User creation and userinfo fetching is done on the same endpoint: [http://localhost:8000/v1/user/<username>](http://localhost:8000/v1/user/<username>)

Sending a GET request there, with a header `Authorizarion: JWT <encrypted_jwt_token>` will return a JSON payload with userinfo, creating the user if needed.

A way to test JWT tokens is to generate a token using [pyjwt](https://pyjwt.readthedocs.io/en/latest/) or similar:

```
$ pyjwt --alg=HS256 --key=secret encode \
  username=tauno \
  email=tauno.tammi@espoo.fi \
  first_name=Tauno \
  last_name=Tammi \
  department_name=null \
  display_name="Tauno Tammi" \
  iss=dummy \
  sub=458032f5-8d73-4370-b155-5330639a14d5 \
  aud=local-dev \
  iat=$(date +%s) \
  exp=$(date +%s -d "+10 days")
```
For MacOS, change the last line to `exp=$(date -v +10d +%s)`

Decrypted example JWT payload:
```
{
  "username": "tauno",
  "email": "tauno.tammi@espoo.fi",
  "first_name": "Tauno",
  "last_name": "Tammi",
  "department_name": null,
  "display_name": "Tauno Tammi",
  "iss": "dummy",
  "sub": "458032f5-8d73-4370-b155-5330639a14d5",
  "aud": "local-dev",
  "iat": 1579858924,
  "exp": 1580722924
}
```

Example JSON response
```
{
    "last_login": null,
    "username": "tauno",
    "email": "tauno.tammi@espoo.fi",
    "date_joined": "2020-01-28T15:44:44.876236+02:00",
    "first_name": "Tauno",
    "last_name": "Tammi",
    "uuid": "458032f5-8d73-4370-b155-5330639a14d5",
    "department_name": null,
    "is_staff": false,
    "display_name": "Tauno Tammi",
    "admin_organizations": [],
    "organization_memberships": []
}
```
In this EspooEvents fork, any created user will have CRUD rights to events via Django permissions.

Development installation on physical or virtual machine
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

The commands below are documented in more detail in [linked-events-importers.md](./linked-events-importers.md#linked-events-importers-and-commands).

```bash
cd $INSTALL_BASE/linkedevents
# Import general Finnish ontology (used by Helsinki UI and Helsinki events)
python manage.py event_import yso --all
# Add keyword set to display in the UI event audience selection
python manage.py add_helsinki_audience
# Add keyword set to display in the UI main category selection
python manage.py add_helsinki_topics
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

## Versioning

Espoo Events Service adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html). The benefit of having
explicit versions instead of just relying on commit hashes is that Semantic Versioning provides a more human-friendly
version that also has a clear meaning. Semantic Versioning makes it possible to infer things that wouldn't be possible
from commit hashes. For instance, it's possible to see whether the version contains just small fixes, features, or even
breaking changes. Another benefit is that explicit versioning enables the use of a changelog. This in turn helps
developers to more easily see what's changed between different versions of the project instead of having to browse
through the commit history which can be tedious. Finally, it's also easier to refer to a specific version using a
human-friendly version rather than a commit hash.

It's important to note that software strictly adhering to Semantic Versioning must declare a public API. Thus, Semantic
Versioning might not be applicable to all software (e.g., see [this](https://www.jering.tech/articles/semantic-versioning-in-practice#what-software-can-semver-version)
and [this](https://softwareengineering.stackexchange.com/a/255201) post). Espoo Events Service isn't a library so it
might not be directly evident why versioning is even needed. However, Espoo Events Service is a service with a REST API
used by the City of Espoo. In addition, Espoo Events Service can also be considered an open source product that can be
used by other parties. Thus, versioning can be helpful to communicate, e.g., breaking changes in the REST API or the
product's features. In other words, for Espoo Events Service, the following can, for instance, be considered to
constitute the public API:

- The REST API provided by Espoo Events Service
- Configuration used by developers for setting up the local development environment
- Documentation (see, e.g., [SemVerDoc](https://semverdoc.org/semverdoc.html))
- Product features

The upstream repository `linkedevents` doesn't seem to use versioning or tags very actively. There are, however, some
version tags and in order to avoid conflicts and to more easily distinguish Espoo Events version tags from Linked Events
version tags, the version tags of Espoo Events have been prefixed with `espoo-`. In this case, e.g., `espoo-v1.2.3` is
the version tag name and the corresponding semantic version is `1.2.3`. Since Linked Events isn't actively using
versioning, the versioning scheme of Espoo Events doesn't deliberately have any relation to the versions in the
`linkedevents` repository. This means that the versions between Espoo Events and Linked Events aren't comparable.

It's also important to note that since we're using continuous delivery, every merge to the `master` branch is a
potential release candidate. This means that every commit in `master` should have an explicit version associated with
it.

The version should be incremented just before a PR is merged to `master`. To create a new version, the creator of the PR
should follow these steps:

- Make sure that you've listed your changes in the [changelog](CHANGELOG.md). A good practice is to list your changes
  during development under the `Unreleased` title. That way, you can easily move the list under the correct version when
  it's time to increment the version.
- Based on Semantic Versioning, decide what's the correct version number for the new version and add the new version to
  the [changelog](CHANGELOG.md) and also update the version in the [VERSION](VERSION) file.

Ask for another developer to review your PR. Once the PR has been merged to `master`, the CI pipeline should
automatically tag the merge commit in the `master` branch with the new version.

## Changelog

This project uses a changelog to keep track of all notable changes between versions. See [CHANGELOG](CHANGELOG.md) for
more details.
