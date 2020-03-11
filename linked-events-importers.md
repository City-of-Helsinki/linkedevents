# Linked Events importers and commands

Please keep this file up to date and document the new importers or update current ones if necessary.

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
* [osoite - Address registry](#osoite---address-registry)
  * [What is it?](#what-is-it-2)
  * [What depends on it?](#what-depends-on-it-2)
  * [How to use it?](#how-to-use-it-2)
* [helmet - Helsinki Metropolitan Area Libraries](#helmet---helsinki-metropolitan-area-libraries)
  * [What is it?](#what-is-it-3)
  * [What depends on it?](#what-depends-on-it-3)
  * [How to use it?](#how-to-use-it-3)
* [espoo - Espoo city](#espoo---espoo-city)
  * [What is it?](#what-is-it-4)
  * [What depends on it?](#what-depends-on-it-4)
  * [How to use it?](#how-to-use-it-4)
* [add_helsinki_audience](#add_helsinki_audience)
  * [What is it?](#what-is-it-5)
  * [What depends on it?](#what-depends-on-it-5)
  * [How to use it?](#how-to-use-it-5)
* [add_helsinki_topics](#add_helsinki_topics)
  * [What is it?](#what-is-it-6)
  * [What depends on it?](#what-depends-on-it-6)
  * [How to use it?](#how-to-use-it-6)
* [import_organizations](#import_organizations)
  * [What is it?](#what-is-it-7)
  * [What depends on it?](#what-depends-on-it-7)
  * [How to use it?](#how-to-use-it-7)
* [install_templates](#install_templates)
  * [What is it?](#what-is-it-8)
  * [What depends on it?](#what-depends-on-it-8)
  * [How to use it?](#how-to-use-it-8)
* [geo_import](#geo_import)
  * [What is it?](#what-is-it-9)
  * [What depends on it?](#what-depends-on-it-9)
  * [How to use it?](#how-to-use-it-9)
* [kulke](#kulke)
  * [What is it?](#what-is-it-10)
  * [What depends on it?](#what-depends-on-it-10)
  * [How to use it?](#how-to-use-it-10)
* [lippupiste](#lippupiste)
  * [What is it?](#what-is-it-11)
  * [What depends on it?](#what-depends-on-it-11)
  * [How to use it?](#how-to-use-it-11)

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

Basic example would be, let's say a guitar player coming to Helsinki to perform in a concert and use sauna afterwards.

We might categorize it with "concert", "popular music", and "sauna" *concepts*.

These *concepts* come from YSO.

### What depends on it?
Linked Events application has *events*. Events must be described by *concepts*.
Therefore, all events depend on YSO.

[add_helsinki_audience](#what-depends-on-it-5) also depends on this importer.

### How to use it?
  ```bash
  python manage.py event_import yso --keywords --all
  ```

Imports all keywords in YSO into the database, without maintaining the existing hierarchy between the concepts.

This is scheduled to run `daily` on the instance as data doesn't change that often.

## tprek - Location registry **(Required)**

### What is it?

*tprek*, short for [*Toimipisterekisteri*](https://hri.fi/data/fi/dataset/paakaupunkiseudun-palvelukartan-rest-rajapinta), is a location registry service giving access to locations in Helsinki through a REST API.

Basic example would be the location of a concert in a certain theater hall.

### What depends on it?
Linked Events application has *events*. Events must have locations.

By default, all event locations are from *tprek* location registry.

Therefore, all events depend on *tprek* locations to be present.

### How to use it?
  ```bash
  python manage.py event_import tprek --places
  ```

Imports all locations, which usually have addresses, coordinates and other metadata, from *tprek* location registry into the database.

This is scheduled to run `hourly` on the instance as data changes often.

## osoite - Address registry

### What is it?

Let's get terminology in order.

`address` is a field in a `location` object. `location` can have other metadata.

[*Pääkaupunkiseudun osoiteluettelo*](https://hri.fi/data/dataset/seudullinen-osoiteluettelo) is an address registry which only contains *addresses*.
*osoite* is a Metropolitan *location* list importer, which creates a *location* object with only one field of *address* from the addresses imported from *Pääkaupunkiseudun osoiteluettelo*.

Basic example would be the location of a one-off random event in a private location.
Locations not meant to be used regularly are not usually added to *tprek*.

### What depends on it?
If you want to give the users of your application the ability to add events with locations which are not present in *tprek*, you need *osoite*.

In other words, *osoite* is fall-back for *tprek*.

### How to use it?
  ```bash
  python manage.py event_import osoite --places
  ```

Creates locations from *osoite* address registry into the database.

This is scheduled to run `daily` on the instance as origin database updates daily too.

## helmet - Helsinki Metropolitan Area Libraries

### What is it?

*helmet* is an importer for Helsinki Metropolitan Area Libraries *Events* from https://helmet.fi.

Basic example would be an event organized by Helsinki city center library for children, which you can import with this importer.

### What depends on it?
If you want to populate the database with events organized by Helmet, you need *helmet* importer.

### How to use it?
  ```bash
  python manage.py event_import helmet --events
  ```

Imports all events organized by Helmet into the database.

This is scheduled to run `hourly` on the instance as data changes often.

## espoo - Espoo city

### What is it?

*espoo* is an importer for Espoo city *Events* from https://espoo.fi.

Basic example would be an event organized by Espoo city for its residents, which you can import with this importer.

### What depends on it?
If you want to populate the database with events organized by Espoo city, you need *espoo* importer.

### How to use it?
  ```bash
  python manage.py event_import espoo --events
  ```

Imports all events organized by Espoo city into the database.

This is scheduled to run `hourly` on the instance as data changes often.

## add_helsinki_audience

### What is it?

*add_helsinki_audience* is a django management command for creating a set of *audience* keywords in the database which is then exposed through `/keyword_set` endpoint.

Basic example would be an event whose target audience are elderly immigrants.

"Elderly" and "Immigrant" are keywords that the event creator would pick from the choices in the *audience* keywords set created by this command.

### What depends on it?
Any YSO keyword can be used as *audience* in the backend. However, if you're running the [Linked Events UI](https://github.com/City-of-Helsinki/linkedevents-ui),
you need this command as the UI only allows the keywords set with this command to be used.

You are free to make your own UI that uses any YSO concept for the target *audience* and you can skip this command.

Keywords in this set are all from YSO except the ones defined in `NEW_SOTE_KEYWORDS_DATA` in [add_helsinki_audience.py](./events/management/commands/add_helsinki_audience.py).
Concepts defined in `NEW_SOTE_KEYWORDS_DATA` were not found in YSO, and therefore were hard-coded manually.

### How to use it?
  ```bash
  python manage.py add_helsinki_audience
  ```

Creates a Helsinki audience keywords set into the database.

## add_helsinki_topics

### What is it?

*add_helsinki_topics* is a django management command for creating a set of *topics* keywords in the database which is then exposed through `/keyword_set` endpoint.

Basic example would be an event in which they would talk about welfare.

"Discussion" and "Welfare" are keywords that the event creator would pick from the choices in the *topics* keywords set created by this command.

### What depends on it?
All the topics used by this command are existing YSO concepts, hand-picked in [add_helsinki_topics.py](./events/management/commands/add_helsinki_topics.py).

If you're running the [Linked Events UI](https://github.com/City-of-Helsinki/linkedevents-ui),
you need this command as the UI needs to show a list of event *topics* keywords for the event creator to choose for the event they would like to create.

### How to use it?
  ```bash
  python manage.py add_helsinki_topics
  ```

Creates a Helsinki topic keywords set into the database.

## import_organizations

### What is it?

*import_organizations* is an importer for importing all City of Helsinki organization **divisions** while maintaining their **hierarchy** into the database.

Basic example would be, say City of Helsinki has A, B, and C divisions, and A and B have two sub-divisions themselves.

This importer would import all 5 divisions while maintaining the hierarchy within the divisions.


### What depends on it?
If you're having an application whose target users are City of Helsinki organization employees, you need this importer.

Then, you can assign required permissions to users in django-admin based on which division they belong to.

### How to use it?
  ```bash
  python manage.py import_organizations https://api.hel.fi/paatos/v1/organization/ -s helsinki:ahjo
  ```

Imports all City of Helsinki organization divisions into the database while maintaining their hierarchy.


## install_templates

### What is it?

*install_templates* is a django management command for giving the browsable API which comes from django-rest-framework
a Helsinki brand look and feel and also instructions for the API user.

Basic example would be the live version of [Linked Events API for Helsinki city](https://api.hel.fi/linkedevents/v1/event/)
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

*kulke*, short for *Kulttuurikeskukset*, is an importer which imports *events* from City of Helsinki cultural centers (http://annantalo.fi, http://vuotalo.fi, http://malmitalo.fi etc.).

**NOTE**: To get access to data from City of Helsinki cultural centers, you need to have access to City of Helsinki internal network.
Specifics of how to get this access for City of Helsinki developers will be documented here later.

### What depends on it?
If you'd like to have events organized by City of Helsinki cultural centers in your Linked Events application instance, you need this importer.

### How to use it?
  ```bash
  python manage.py event_import kulke --events
  ```

Imports all events organized by City of Helsinki cultural centers into the database.

This is scheduled to run `hourly` on the instance as data changes often.

## lippupiste

### What is it?

*lippupiste* is an importer which imports *events* from Lippupiste Oy (https://lippu.fi); currently used only for importing [Helsinki City Theater](https://hkt.fi/) events.

**NOTE**: To get access to data from Lippupiste, you need to have an agreement with Lippupiste Oy. The data is not publicly available at the moment.

### What depends on it?
If you'd like to have events marketed by Lippupiste anywhere in Finland in your Linked Events application instance, you need this importer.

### How to use it?
  ```bash
  python manage.py event_import lippupiste --events
  ```

Imports events marketed by Lippupiste Oy into the database. Currently, the importer only imports plays by the Helsinki City Theater; the imported locations and events can be filtered in the importer code.

This is scheduled to run `hourly` on the instance as data changes often.
