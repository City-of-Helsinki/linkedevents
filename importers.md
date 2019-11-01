# Importers

<!-- vim-markdown-toc GFM -->

* [YSO - General Finnish ontology **(Required)**](#yso---general-finnish-ontology-required)
  * [What is it?](#what-is-it)
  * [What depends on it?](#what-depends-on-it)
  * [What does the importer do?](#what-does-the-importer-do)

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

### What does the importer do?
  ```bash
  python manage.py event_import yso --keywords --all
  ```

Imports all keywords in YSO into the database, without maintaining the existing hierarechy between the concepts.
