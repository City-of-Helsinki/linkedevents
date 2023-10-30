DROP INDEX IF EXISTS events_eventfulltext_id_index;
DROP MATERIALIZED VIEW IF EXISTS events_eventfulltext;

CREATE MATERIALIZED VIEW events_eventfulltext AS
SELECT event.id                                                                     AS event_id,
       place.id                                                                     AS place_id,
       event.last_modified_time                                                     AS event_last_modified_time,
       place.last_modified_time                                                     AS place_last_modified_time,

       -- The weights can be adjusted using an environment variable, see refresh_full_text command
       setweight(to_tsvector('finnish', coalesce(event.name_fi, '')), 'A') ||
       setweight(to_tsvector('finnish', coalesce(event.short_description_fi, '')), 'C') ||
       setweight(to_tsvector('finnish', coalesce(event.description_fi, '')), 'D') ||
       setweight(to_tsvector('finnish', coalesce(place.name_fi, '')), 'A') ||
       setweight(to_tsvector('finnish', coalesce(event_keywords.name_fi, '')), 'B') as search_vector_fi,

       setweight(to_tsvector('english', coalesce(event.name_en, '')), 'A') ||
       setweight(to_tsvector('english', coalesce(event.short_description_en, '')), 'C') ||
       setweight(to_tsvector('english', coalesce(event.description_en, '')), 'D') ||
       setweight(to_tsvector('english', coalesce(place.name_en, '')), 'A') ||
       setweight(to_tsvector('english', coalesce(event_keywords.name_en, '')), 'B') as search_vector_en,

       setweight(to_tsvector('swedish', coalesce(event.name_sv, '')), 'A') ||
       setweight(to_tsvector('swedish', coalesce(event.short_description_sv, '')), 'C') ||
       setweight(to_tsvector('swedish', coalesce(event.description_sv, '')), 'D') ||
       setweight(to_tsvector('swedish', coalesce(place.name_sv, '')), 'A') ||
       setweight(to_tsvector('swedish', coalesce(event_keywords.name_sv, '')), 'B') as search_vector_sv

FROM events_event event
         LEFT OUTER JOIN events_place place ON event.location_id = place.id
         -- Join the keywords, aggregated as a string
         LEFT OUTER JOIN (SELECT event_id,
                                 string_agg(name_fi, ' ') AS name_fi,
                                 string_agg(name_en, ' ') AS name_en,
                                 string_agg(name_sv, ' ') AS name_sv
                          FROM events_event_keywords
                                   LEFT OUTER JOIN events_keyword ON events_event_keywords.keyword_id = events_keyword.id
                          GROUP BY 1) AS event_keywords ON event_keywords.event_id = event.id;

-- Required when refreshing the materialized view concurrently
CREATE UNIQUE INDEX events_eventfulltext_id_index ON events_eventfulltext (event_id);
