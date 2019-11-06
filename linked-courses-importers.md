# Linked Courses importers and commands

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

We might categorize it with "education", "Portuguese", and "fun" *concepts*.

These *concepts* come from YSO.

### What depends on it?
Linked Courses application has *events*. Events must be described by *concepts*.
Therefore, all events depend on YSO.

### How to use it?
  ```bash
  python manage.py event_import yso --keywords --all
  ```

Imports all keywords in YSO into the database, without maintaining the existing hierarchy between the concepts.

## tprek - Location registry **(Required)**

### What is it?

*tprek*, short for *Toimipisterekisteri*, is a location registry service giving access to addresses in Helsinki through a REST API.

Basic example would be the address of a Kung Fu course in a certain sport facility.

### What depends on it?
Linked Courses application has *events*. Events must have addresses.

By default, all event addresses are from *tprek* location registry.

Therefore, all events depend on *tprek* addresses to be present.

### How to use it?
  ```bash
  python manage.py event_import tprek --places
  ```

Imports all addresses in *tprek* location registry into the database.

## helmet - Helsinki Metropolitan Area Libraries

### What is it?

*helmet* is an importer for Helsinki Metropolitan Area Libraries.

Basic example would be a book reading course organized by Helsinki city center library for young adults, which you can import with this importer.

### What depends on it?
If you want to populate the database with courses organized by Helmet, you need *helmet* importer.

### How to use it?
  ```bash
  python manage.py event_import helmet --courses
  ```

Imports all courses organized by Helmet into the database.

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

Imports all municipalities in Finland.

  ```bash
  python manage.py geo_import helsinki --divisions
  ```

Imports all divisions in Helsinki. This allows more specific filtering for Helsinki city based on
`district` names, `sub_district` names, and `neighborhood` names.
