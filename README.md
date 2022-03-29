# Linked Events

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

## Manual installation of Linked Events on physical or virtual machine:

Install following packages with your distros package manager
```bash
postgresql postgis nginx virtualenv python3-dev python3-pip build-essential libpq-dev
```

### Preparing your PostgreSQL:
	
Generate required locales
```bash
sudo locale-gen fi_FI.UTF-8
sudo systemctl restart postgresql
```		
Create a new role in postgresql
```bash
sudo -u postgres createuser -R -S linkedevents
```
Create a new database in postgresql
```bash
sudo -u postgres createdb -O linkedevents -T template0 -l fi_FI.UTF-8 linkedevents
```
Create extensions for the database
```bash
sudo -u postgres psql linkedevents -c "CREATE EXTENSION postgis;"
sudo -u postgres psql linkedevents -c "CREATE EXTENSION hstore;"
```
### Preparing your local repository:

Clone your repository
```bash
git clone https://github.com/City-of-Turku/linkedevents.git
```
Create a virtual environment for your python
```bash
virtualenv -p python3 venv
```
Activate your virtual environment
```bash
source venv/bin/activate
```
Install requirements.txt
```bash
pip install -r requirements.txt
```
Install requirements-dev.txt
```bash
pip install -r requirements-dev.txt
```
### Fill your database with included migrations:
	
Run basic migrations
```bash
python manage.py migrate
```
Additional changes to language fields according to settings.LANGUAGES
```bash
python manage.py sync_translation_fields
```
After this you have a very basic installation of Linked Events ready,
but it's recommended to run at least some of the supported importers if you
want to have all of the features working.

### Use importers to add installation specific data:

```bash
#YSO(General Finnish Ontology)-importer that adds all the concepts and their alt labels and hierarchies.
#A large part of Linked Events features are built on top of YSO, this importer should be used in all installations.
python manage.py event_import ontology

#TSL-wordlist(Turun sanalista)-importer adds a City-of-Turku specific wordlist that is used by some of the keyword set importers.
#Use this if you don't plan on using your own keyword sets based on YSO or your own wordlists.
python manage.py event_import tsl --all

  #Add a new keyword set to display in the UI general audience selection.
  #!Based on TSL-wordlist so import that first!
  python manage.py add_tku_audience

  #Add a new keyword set to display in the UI event category selections.
  #!Based on TSL-wordlist so import that first!
  python manage.py add_tku_topics_by_content

  #Add a new keyword set to display in the UI event category selections.
  #!Based on TSL-wordlist so import that first!
  python manage.py add_tku_topics_by_type
  
  #Add a new keyword set to display in the UI hobby category selections.
  #!Based on TSL-wordlist so import that first!
  python manage.py add_tku_hobbytopics

#Import places from Turku Servicemap API.
#It's recommended to use at least one of the place importers when developing Linked Events.
python manage.py event_import tpr --places

#Import Turku-region street addresses from api.turku.fi
#It's recommended to use at least one of the place importers when developing Linked Events.
python manage.py event_import osoite --places

#Import City of Turku hierarchical organization for UI user rights management
python manage.py event_import turku_organization

#Add default payment methods to display in the UI.
python manage.py event_import payment_method_defaults
				
#Import Turku specific images for Linked Events image bank.
#! Before importing, create media\images folder in the main project folder
python manage.py event_import turku_image_bank
		
#Import event data from the old Turku events calendar.
python manage.py event_import turku_old_events --events
```

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
