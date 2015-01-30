=================
Linked Events API
=================

Updated 2014-12-18

.. contents::

.. toctree::
   :maxdepth: 2

Introduction
------------

Linked events public REST API responds to GET requests and lives at the
http://api.hel.fi/linkedevents/v0.1/.
This API requires no authentication and it provides
`browsable API <http://www.django-rest-framework.org/topics/browsable-api>`_.

Testing and examples
--------------------

Examples
________
Functional example requests are provided in examples. (TODO)

Test form
_________

There is a form for testing API at URL
`http://linkedevents.rista.net/demoform/ <http://linkedevents.rista.net/demoform/>`_.
Note that above URL is temporary and it will change in 2015 spring.

Test script
___________
Simple command line test script exists:
`linkedevents_api_test.py <http://linkedevents.rista.net/static/demoform/linkedevents_api_test.py>`_
(written in Python) makes a request to
the API and prints results to the terminal

An example::

    $ python linkedevents_api_test.py -p data_source=kulke -p start=2014-12-15
    Namespace(param=['data_source=kulke', 'start=2014-12-15'], url='http://api.hel.fi/linkedevents/v0.1/event/', verbosity=0)
    META:
    previous None
    next http://api.hel.fi/linkedevents/v0.1/event/?data_source=kulke&start=2014-12-15&page=2
    count 353
    DATA:
    2014-12-18T17:00:00Z Swinging Christmas - Antti Sarpila Swing Band, feat. Johanna Iivanainen (fi)
    2015-05-20T16:00:00Z Nits? - 40-vuotisjuhlakonsertti (fi)
    2014-12-15T16:00:00Z Yhteislaulua (fi)
    2014-12-19T16:30:00Z Helsingin Balettiakatemian joulujuhlanäytös (fi)

Endpoints
---------

==============   ===============
Endpoint         Description
==============   ===============
event            All events, multiple ways to filter the result
keyword          Categories, can be filtered by event data sources
place            Event venues, can be filtered by event data sources
language         List all available languages
search           Search endpoint, uses Django haystack and Elasticsearch
==============   ===============

Check all database fields from
`Event model's source <https://github.com/City-of-Helsinki/linkedevents/blob/master/events/models.py>`_

Event endpoint's source, see _filter_event_queryset() function in
`EventViewSet <https://github.com/City-of-Helsinki/linkedevents/blob/master/events/api.py>`_

Event
_____

`Event <http://api.hel.fi/linkedevents/v0.1/event/>`_
is the most important endpoint in Linked events and it supports
several filter parameters.

.. http:get:: /v0.1/event/?(optional query parameters)

   :query page_size: How many records are returned per query. Default is 20.
   :query page: Which page is requested. If e.g. page_size is 20 and page is 3
          records from 61 to 80 are returned.
   :query text: String to search from all text fields, all language versions,
          case insensitive.
   :query start: Return Events which have start_time or end_time greater than
          given date. Date is in format YYYY-mm-dd, e.g. `2014-12-15` or
          string `today`.
   :query end: Return Events which have start_time or end_time smaller than
          given date. Date is in format YYYY-mm-dd, e.g. `2014-12-15` or
          string `today`.
   :query last_modified_since: Return only events modified after this timestamp,
          which in format YYYY-mm-ddTHH:MM:SSZ, e.g. `2014-12-15T11:33:55Z`.
          Note `Z` postfix, which means UTC time.
   :query bbox: Restrict events inside the rectangle west,south,east,north,
          e.g. `24.9348,60.1762,24.9681,60.1889`.
   :query data_source: Source of event, e.g. `matko`, `kulke`, `helmet`
   :query location: Location id, e.g. `tprek:7254`. Separate multiple ids with
          comma ','
   :query keyword: Keyword id, e.g. `yso:p7254`. Separate multiple ids with
          comma ','
   :query recurring: If `super`, return only event aggregates, if `sub`,
          return everything except aggregates. If not set, return all events.
   :query permanency: If `short`, return events which have time interval between
          their end_time and start_time less than one day. If `long`, return
          events with duration longer than one day. If not set, return all
          events.

   **Example request**:

   .. sourcecode:: http

      GET /v0.1/event/?start=2014-12-15&end=2014-12-16 HTTP/1.1
      Host: example.com
      Accept: application/json, text/javascript

   **Example response**:

   .. sourcecode:: http

    HTTP 200 OK
    Allow: GET, HEAD, OPTIONS
    Vary: Accept
    Content-Type: application/json; charset=utf-8

    {
        "data": [ ... list of events ... ],
        "meta": {
            "previous": null,
            "next": "http://example.com/v0.1/event/?page=2&end=2014-12-16&start=2014-12-15",
            "count": 56
        }
    }

..  this is comment
..   :query sort: one of ``hit``, ``created-at``
..   :query offset: offset number. default is 0
..   :query limit: limit number. default is 30
..   :reqheader Accept: the response content type depends on
..                      :mailheader:`Accept` header
..   :reqheader Authorization: optional OAuth token to authenticate
..   :resheader Content-Type: this depends on :mailheader:`Accept`
..                            header of request
..   :statuscode 200: no error
..   :statuscode 404: there's no user


Keyword
_______

`Keyword <http://api.hel.fi/linkedevents/v0.1/keyword/>`_
endpoint returns all keywords which have ever been in use by default.

.. http:get:: /v0.1/keyword/?(optional query parameters)

   :query show_all_keywords: If defined and not empty (e.g. `1`), all Keywords
          are returned. Please note that this is normally not very reasonable,
          because this set contains Keywords which are never linked to any
          Event.
   :query event.data_source: Return only Keywords which are linked to Events
          which are linked to given
          data source, e.g. `matko`, `kulke`, `helmet`. Virtually this takes
          all Events of given data source and returns all Keywords used in those
          events. May be useful when combined with event.start and/or event.end.
   :query event.start: See `event.data_source` above and in addition Event's
          start filter.
   :query event.end: See `event.data_source` above and in addition Event's
          end filter.
   :query data_source: Return only Keywords which have value in data_source field
   :query page_size: See Event
   :query page: See Event

   **Example request**:

   .. sourcecode:: http

      GET /v0.1/keyword/?data_source=kulke HTTP/1.1
      Host: example.com
      Accept: application/json, text/javascript

   **Example response**:

   .. sourcecode:: http

    HTTP 200 OK
    Allow: GET, HEAD, OPTIONS
    Vary: Accept
    Content-Type: application/json; charset=utf-8

    {
        "data": [
            {
                "id": "yso:p21160",
                "data_source": "yso",
                "image": null,
                "origin_id": null,
                "created_time": "2014-11-07T11:01:52.406Z",
                "last_modified_time": "2014-11-07T11:01:52.406Z",
                "last_modified_by": null,
                "aggregate": false,
                "alt_labels": [
                    4289,
                    2366
                ],
                "name": {
                    "en": "literature (domain)",
                    "fi": "kirjallisuus (erikoisala)",
                    "sv": "litteratur (verksamhetssf\u00e4r)"
                },
                "@id": "http://example.com/v0.1/keyword/yso%3Ap21160/",
                "@type": "Keyword"
            },
            ...
        ],
        "meta": {
            "previous": null,
            "count": 60,
            "next": "http://example.com/v0.1/keyword/?data_source=kulke&page=2"
        }
    }

Place
_____

`Place <http://api.hel.fi/linkedevents/v0.1/place/>`_
endpoint returns all places which have ever been in use by default.

.. http:get:: /v0.1/place/?(optional query parameters)

   :query show_all_places: If defined and not empty (e.g. `1`), all Places
          are returned. Please note that this is normally not very reasonable,
          because this set contains Places which are never linked to any
          Event.
   :query event.*: see Keyword
   :query data_source: Return only Places which have value in data_source field
   :query page_size: See Event
   :query page: See Event

   **Example request**:

   .. sourcecode:: http

      GET /v0.1/place/?data_source=kulke HTTP/1.1
      Host: example.com
      Accept: application/json, text/javascript

   **Example response**:

   .. sourcecode:: http

    HTTP 200 OK
    Allow: GET, HEAD, OPTIONS
    Vary: Accept
    Content-Type: application/json; charset=utf-8

    {
        "data": [
            {
                "id": "tprek:7259",
                "custom_data": null,
                "data_source": "tprek",
                "image": null,
                "origin_id": "7259",
                "created_time": null,
                "last_modified_time": "2014-11-07T10:58:46.663Z",
                "last_modified_by": null,
                "publisher": "ahjo:021600",
                "parent": null,
                "email": null,
                "contact_type": null,
                "address_region": null,
                "postal_code": "00900",
                "post_office_box_num": null,
                "address_country": null,
                "deleted": false,
                "position": {
                    "coordinates": [
                        25.07988,
                        60.212097
                    ],
                    "type": "Point"
                },
                "info_url": null,
                "address_locality": {
                    "en": "Helsinki",
                    "fi": "Helsinki",
                    "sv": "Helsingfors"
                },
                "street_address": {
                    "en": "Turunlinnantie 1",
                    "fi": "Turunlinnantie 1",
                    "sv": "\u00c5bohusv\u00e4gen 1"
                },
                "description": null,
                "name": {
                    "en": "Stoa",
                    "fi": "Stoa",
                    "sv": "Stoa"
                },
                "telephone": null,
                "@id": "http://example.com/v0.1/place/tprek%3A7259/",
                "@type": "Place"
            },
            ...
        ],
        "meta": {
            "previous": null,
            "count": 9,
            "next": null
        }
    }

Language
________

`Language <http://api.hel.fi/linkedevents/v0.1/language/>`_
endpoint just returns list of languages used in Linked events.

.. http:get:: /v0.1/language/

Search
______

`Search <http://api.hel.fi/linkedevents/v0.1/search/>`_
endpoint uses Django Haystack and
`Elasticsearch <http://www.elasticsearch.org/>`_ search engine to provide
search functionality.

.. http:get:: /v0.1/search/?(mandatory query parameters)

   :query q: mandatory search phrase

Note that search is not currently fully functional.
