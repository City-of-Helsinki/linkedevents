# Importers

<!-- vim-markdown-toc GFM -->

* [YSO - General Finnish ontology **(Required)**](#yso---general-finnish-ontology-required)
  * [What is it?](#what-is-it)
  * [What depends on it?](#what-depends-on-it)
  * [How to use it?](#how-to-use-it)
* [tprek - Location registry **(Required)**](#tprek---location-registry-required)
  * [What is it?](#what-is-it-1)
  * [What depends on it?](#what-depends-on-it-1)
  * [How to use it?](#how-to-use-it-1)
* [osoite - Location registry](#osoite---location-registry)
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
* [add_helfi_topics](#add_helfi_topics)
  * [What is it?](#what-is-it-6)
  * [What depends on it?](#what-depends-on-it-6)
  * [How to use it?](#how-to-use-it-6)

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

[add_helfi_topics](#what-depends-on-it-6) also depends on this importer.

### How to use it?
  ```bash
  python manage.py event_import yso --keywords --all
  ```

Imports all keywords in YSO into the database, without maintaining the existing hierarechy between the concepts.

## tprek - Location registry **(Required)**

### What is it?

*tprek*, short for *Toimipisterekisteri*, is a location registry service giving access to addresses in Helsinki through a REST API.

Basic example would be the address of a concert in a certain theather hall.

### What depends on it?
Linked Events application has *events*. Events must have addresses.

By default, all event addresses are from *tprek* location registery.

Therefore, all events depend on *tprek* addresses to be present.

### How to use it?
  ```bash
  python manage.py event_import tprek --places
  ```

Imports all addresses in *tprek* location registery into the database.

## osoite - Location registry

### What is it?

*osoite*, short for *Pääkaupunkiseudun osoiteluettelo*, is a Metropolitan address list importer.

Basic example would be the address of a concert in a very new building whose address is not available in *tprek*.

### What depends on it?
If you want to give the users of your application the ability to add events with addresses which are not present in *tprek*, you need *osoite*.

In other words, *osoite* is fallback for *tprek*.

### How to use it?
  ```bash
  python manage.py event_import osoite --places
  ```

Imports all addresses in *osoite* location registery into the database.

## helmet - Helsinki Metropolitan Area Libraries

### What is it?

*helmet* is an importer for Helsinki Metropolitan Area Libraries.

Basic example would be an event oranized by Helsinki city center library for children, which you can import with this importer.

### What depends on it?
If you want to populate the database with events organized by Helmet, you need *helmet* importer.

### How to use it?
  ```bash
  python manage.py event_import helmet --events
  ```

Imports all events organized by Helmet into the database.

## espoo - Espoo city

### What is it?

*espoo* is an importer for Espoo city.

Basic example would be an event oranized by Espoo city for its residents, which you can import with this importer.

### What depends on it?
If you want to populate the database with events organized by Espoo city, you need *espoo* importer.

### How to use it?
  ```bash
  python manage.py event_import espoo --events
  ```

Imports all events organized by Espoo city into the database.

## add_helsinki_audience

### What is it?

*add_helsinki_audience* is an importer for adding different *audience* keywords in the database.

Basic example would be an event whose target audience are elderly immigrants.

"Elderly" and "Immigrant" are keywords you can import with this importer.

### What depends on it?
If you're running the [Linked Events UI](https://github.com/City-of-Helsinki/linkedevents-ui),
you need this importer as the UI needs to show a list of *audience* categories for the user to choose for the event they would like to create.

Some, not all, of these keywords are from YSO. Therefore this importer depends on YSO importer data being present.

### How to use it?
  ```bash
  python manage.py add_helsinki_audience
  ```

Imports all target audience keywords into the database.

## add_helfi_topics

### What is it?

*add_helfi_topics* is an importer for adding different event *topics* keywords in the database.

Basic example would be an event in which they would talk about daycare for families and housing.

"Daycare and education" and "Housing and environment" are keywords you can import with this importer.

### What depends on it?
If you're running the [Linked Events UI](https://github.com/City-of-Helsinki/linkedevents-ui),
you need this importer as the UI needs to show a list of event *topics* categories for the user to choose for the event they would like to create.

Some, not all, of these keywords are from YSO. Therefore this importer depends on YSO importer data being present.

### How to use it?
  ```bash
  python manage.py add_helfi_topics
  ```

Imports all event *topics* keywords into the database.
