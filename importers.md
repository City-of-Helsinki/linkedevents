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

> Ontology is the philosophical study of being. More broadly, it studies concepts that directly relate to being, in particular
> becoming, existence, reality, as well as the basic categories of being and their relations.
>
> From https://en.wikipedia.org/wiki/Ontology

YSO, short for *Yleinen suomalainen ontologia*, is basically a +30,000 collection of **concepts** in Finnish culture, translated in 3 languages.

> General Finnish Ontology YSO is a trilingual ontology consisting mainly of general concepts.
> YSO has been founded on the basis of concepts in Finnish cultural sphere.
>
> From https://finto.fi/yso/en/. You can browse the concepts there if you wish

Basic example would be, let's say a guitar player coming to Helsinki to perform in a concert and use suana afterwards.

We might categorize it with "concert", "popular music", and "sauna" *concepts*.

These *concepts* come from YSO.

### What depends on it?
Linked Events application has *events*. Events must be described by *concepts*.
Therefore, all events depend on YSO.

### What does the importer do?
  ```bash
  python manage.py event_import yso --all
  ```

Imports all keywords in YSO into the database, without maintaining the existing hierarechy between the concepts.
