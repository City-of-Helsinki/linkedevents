# Linked Courses importers and commands

Please keep this file up to date and document the new importers or update current ones if necessary.

This documentation is written to help you decide what to use if you'd like to setup your own application instance of Linked Courses.

#

<!-- vim-markdown-toc GFM -->

* [YSO - General Finnish ontology **(Required)**](#yso---general-finnish-ontology-required)
  * [What is it?](#what-is-it)
  * [What depends on it?](#what-depends-on-it)
  * [How to use it?](#how-to-use-it)
* [tprek - Location registry **(Required)**](#tprek---location-registry-required)
  * [What is it?](#what-is-it-1)
  * [What depends on it?](#what-depends-on-it-1)
  * [How to use it?](#how-to-use-it-1)
* [helmet - Helsinki Metropolitan Area Libraries](#helmet---helsinki-metropolitan-area-libraries)
  * [What is it?](#what-is-it-2)
  * [What depends on it?](#what-depends-on-it-2)
  * [How to use it?](#how-to-use-it-2)
* [install_templates](#install_templates)
  * [What is it?](#what-is-it-3)
  * [What depends on it?](#what-depends-on-it-3)
  * [How to use it?](#how-to-use-it-3)
* [geo_import](#geo_import)
  * [What is it?](#what-is-it-4)
  * [What depends on it?](#what-depends-on-it-4)
  * [How to use it?](#how-to-use-it-4)
* [kulke](#kulke)
  * [What is it?](#what-is-it-5)
  * [What depends on it?](#what-depends-on-it-5)
  * [How to use it?](#how-to-use-it-5)
* [enkora](#enkora)
  * [What is it?](#what-is-it-7)
  * [What depends on it?](#what-depends-on-it-7)
  * [How to use it?](#how-to-use-it-7)

<!-- vim-markdown-toc -->

## YSO - General Finnish ontology **(Required)**

### What is it?
First, some terminology is in order. Starting with *ontology*:

> In computer science and information science, an ontology encompasses a representation,
> formal naming and definition of the categories, properties and relations between the
> concepts, data and entities that substantiate one, many or all domains of discourse.
>
> From [Wikipedia of Ontology (information science)](https://en.wikipedia.org/wiki/Ontology_(information_science))

YSO, short for *Yleinen suomalainen ontologia*, is basically a +30,000 collection of **concepts** in Finnish culture, translated in 3 languages.

> General Finnish Ontology YSO is a trilingual ontology consisting mainly of general concepts.
> YSO has been founded on the basis of concepts in Finnish cultural sphere.
>
> From https://finto.fi/yso/en/. You can browse the concepts there if you wish

Basic example would be, let's say a Portuguese language teacher coming to Helsinki to teach Portuguese to children.

We might categorize it with "chldren", "education", "Portuguese", and "fun" *concepts*.

These *concepts* come from YSO.

### What depends on it?
Linked Courses application has *events*. Events must be described by *concepts*.
Therefore, all events depend on YSO.

### How to use it?
  ```bash
  python manage.py event_import yso --keywords --all
  ```

Imports all keywords in YSO into the database, without maintaining the existing hierarchy between the concepts.

This is scheduled to run `daily` on the instance as data doesn't change that often.

## tprek - Location registry **(Required)**

### What is it?

*tprek*, short for [*Toimipisterekisteri*](https://hri.fi/data/fi/dataset/paakaupunkiseudun-palvelukartan-rest-rajapinta), is a location registry service giving access to locations in Helsinki through a REST API.

Basic example would be the location of a Kung Fu course in a certain sport facility.

### What depends on it?
Linked Courses application has *events*. Events must have locations.

By default, all event locations are from *tprek* location registry.

Therefore, all events depend on *tprek* locations to be present.

### How to use it?
  ```bash
  python manage.py event_import tprek --places
  ```

Imports all locations, which usually have addresses, coordinates and other metadata, from *tprek* location registry into the database.

This is scheduled to run `hourly` on the instance as data changes often.

## helmet - Helsinki Metropolitan Area Libraries

### What is it?

*helmet* is an importer for Helsinki Metropolitan Area Libraries *Courses* from https://helmet.fi..

Basic example would be a book reading course organized by Helsinki city center library for young adults, which you can import with this importer.

### What depends on it?
If you want to populate the database with courses organized by Helmet, you need *helmet* importer.

### How to use it?
  ```bash
  python manage.py event_import helmet --courses
  ```

**NOTE**: `--courses` flag functionality is not present at the moment but will be implemented.

Imports all courses organized by Helmet into the database.

This is scheduled to run `hourly` on the instance as data changes often.

## install_templates

### What is it?

*install_templates* is a django management command for giving the browsable API which comes from django-rest-framework
a Helsinki brand look and feel and also instructions for the API user.

Basic example would be the live version of [Linked Courses API for Helsinki city](https://api.hel.fi/linkedcourses/v1/event/)
which is blue and also includes instructions on how to query the API when you'd like to apply certain filters to the `/event` endpoint.

### What depends on it?
If you're having an application for Helsinki city and you'd like the browsable API to have Helsinki brand
look and feel and also instructions for API user, you need this django management command.

### How to use it?
  ```bash
  python manage.py install_templates helevents
  ```

Installs Helsinki city templates for the browsable API.

## geo_import

### What is it?

*geo_import* is an importer which creates *divisions* data structure for each *place* object in database.

For example, a simplified *place* object from Sello library can be like so:
```json
{
  ...
  "id": "tprek:15417",
  "position": {
      "type": "Point",
      "coordinates": [
          24.80992,
          60.21748
      ]
  },
  "name": {
      "fi": "Sellon kirjasto",
      "sv": "Sellobiblioteket",
      "en": "Sellon kirjasto"
  },
  ...
},
```

And by running this importer, you'd add `divisions` to the object above:
```json
{
  ...
  "id": "tprek:15417",
  "divisions": [
      {
          "type": "muni",
          "ocd_id": "ocd-division/country:fi/kunta:espoo",
          "municipality": null,
          "name": {
              "fi": "Espoo",
              "sv": "Esbo"
          }
      }
  ],
  "position": {
      "type": "Point",
      "coordinates": [
          24.80992,
          60.21748
      ]
  },
  "name": {
      "fi": "Sellon kirjasto",
      "sv": "Sellobiblioteket",
      "en": "Sellon kirjasto"
  },
  ...
},
```

This allows the API user to query the `/place` endpoint by adding division of Espoo as an example:

  ```
  /place/?division=Espoo
  ```

Or directly querying the `/event` endpoint by filtering division of Espoo as an example:

  ```
  /event/?division=Espoo
  ```

### What depends on it?
If you'd like to add support for division based filtering of events or places in your application, then you need this importer.

### How to use it?
  ```bash
  python manage.py geo_import finland --municipalities
  ```

Imports all municipalities in Finland from https://kartat.kapsi.fi/.

  ```bash
  python manage.py geo_import helsinki --divisions
  ```

Imports all divisions in Helsinki from the [Helsinki district division datasets](https://hri.fi/data/dataset/helsingin-piirijako). This allows more specific filtering for Helsinki city based on
`district` names, `sub_district` names, and `neighborhood` names.

## kulke

### What is it?

*kulke*, short for *Kulttuurikeskukset*, is an importer which imports *courses* from City of Helsinki cultural centers (http://annantalo.fi, http://vuotalo.fi, http://malmitalo.fi etc.).

**NOTE**: To get access to data from City of Helsinki cultural centers, you need to have access to City of Helsinki internal network.
Specifics of how to get this access for City of Helsinki developers will be documented here later.

### What depends on it?
If you'd like to have courses organized by City of Helsinki cultural centers in your Linked Courses application instance, you need this importer.

### How to use it?
  ```bash
  python manage.py event_import kulke --courses
  ```

Imports all courses organized by City of Helsinki cultural centers into the database.

This is scheduled to run `hourly` on the instance as data changes often.

## enkora

### What is it?

*Enkora* is an importer which imports *courses* from [Enkora](https://enkora.fi/fi/referenssit/helsingin-liikuntavirasto/)
ERP used by Sports and Leisure.

Please note, Enkora is not a public system and any access to it requires credentials.
Enkora acts as a data provider for other systems, like LinkedEvents with information on activities and courses.

### What depends on it?
Activities from Enkora are published on number of websites and applications by City of Helsinki.

This importer is merely a bridge to transmit and transform activity data to LinkedEvents.

### How to use it?
Dependencies:
* Credentials into Enkora API
* YSO keywords imported to SQL
* TPrek places imported to SQL

Import Enkora courses with a single command:
  ```bash
  python manage.py event_import enkora --courses
  ```

Running this imports all active courses from ERP into the database.

### Mapping
* Enkora location is mapped to TPrek place
* Enkora keyword is mapped to audience keywords
* Enkora description is mapped to keywords and audience keywords

A MarkDown-document how mapping works can be auto-generated.