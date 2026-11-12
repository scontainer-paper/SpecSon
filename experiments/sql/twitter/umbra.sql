-- query: T-C1-1 | Business query
SELECT d.doc_id FROM {{table}} d WHERE EXISTS (SELECT 1 WHERE (d.doc->'user'->>'verified')::boolean = true AND (d.doc->'user'->>'followers_count')::bigint >= 10000);

-- query: T-C1-2 | Business query
SELECT d.doc_id FROM {{table}} d WHERE EXISTS (SELECT 1 WHERE d.doc->>'lang' = 'en' AND (d.doc->'user'->>'followers_count')::bigint >= 1000);

-- query: T-C1-3 | Business query
SELECT d.doc_id FROM {{table}} d WHERE EXISTS (SELECT 1 WHERE d.doc->'retweeted_status'->>'lang' = 'en' AND (d.doc->'retweeted_status'->>'retweet_count')::bigint >= 1000);

-- query: T-C1-4 | Business query
SELECT d.doc_id FROM {{table}} d WHERE EXISTS (SELECT 1 WHERE (d.doc->>'is_quote_status')::boolean = true AND (d.doc->'quoted_status'->>'favorite_count')::bigint >= 1000);

-- query: T-C2-1 | Business query
SELECT d.doc_id FROM {{table}} d WHERE JSON_EXISTS((d.doc->'entities'->'hashtags')::json, '$[*] ? (@.text == "NowPlaying")');

-- query: T-C2-2 | Business query
SELECT DISTINCT d.doc_id FROM {{table}} d CROSS JOIN LATERAL json_array_elements(NULLIF(d.doc->'extended_entities'->'media', 'null'::jsonb)::json) AS media(v)
  WHERE media.v->>'type' = 'video';

-- query: T-C2-3 | Business query
SELECT d.doc_id FROM {{table}} d CROSS JOIN LATERAL json_array_elements(NULLIF(d.doc->'extended_entities'->'media', 'null'::jsonb)::json) AS media(v) GROUP BY d.doc_id HAVING sum((media.v->'video_info'->>'duration_millis')::bigint) >= 60000;

-- query: T-C2-4 | Business query
SELECT d.doc_id FROM {{table}} d CROSS JOIN LATERAL json_array_elements(NULLIF(d.doc->'extended_entities'->'media', 'null'::jsonb)::json) AS media(v) GROUP BY d.doc_id HAVING avg((media.v->'video_info'->>'duration_millis')::bigint) >= 30000;

-- query: T-C3-1 | Business query
SELECT DISTINCT d.doc_id FROM {{table}} d CROSS JOIN LATERAL json_array_elements(NULLIF(d.doc->'extended_entities'->'media', 'null'::jsonb)::json) AS media(v)
  WHERE media.v->>'type' = 'photo' AND (media.v->'sizes'->'large'->>'w')::bigint > (media.v->'sizes'->'large'->>'h')::bigint;

-- query: T-C3-2 | Business query
SELECT DISTINCT d.doc_id FROM {{table}} d CROSS JOIN LATERAL json_array_elements(NULLIF(d.doc->'extended_entities'->'media', 'null'::jsonb)::json) AS media(v)
  WHERE media.v->>'type' = 'video' AND (media.v->'sizes'->'large'->>'h')::bigint > (media.v->'sizes'->'large'->>'w')::bigint;

-- query: T-C3-3 | Business query
SELECT DISTINCT d.doc_id FROM {{table}} d CROSS JOIN LATERAL json_array_elements(NULLIF(d.doc->'extended_entities'->'media', 'null'::jsonb)::json) AS media(v)
  WHERE media.v->>'type' = 'video' AND (media.v->'sizes'->'large'->>'w')::bigint > (media.v->'sizes'->'large'->>'h')::bigint
    AND (media.v->'video_info'->>'duration_millis')::bigint >= 30000;

-- query: T-C3-4 | Business query
SELECT DISTINCT d.doc_id FROM {{table}} d CROSS JOIN LATERAL json_array_elements(NULLIF(d.doc->'retweeted_status'->'extended_entities'->'media', 'null'::jsonb)::json) AS media(v)
  WHERE ((d.doc->'retweeted_status'->>'retweet_count')::bigint >= 1000) AND media.v->>'type' = 'photo' AND (media.v->'sizes'->'large'->>'h')::bigint > (media.v->'sizes'->'large'->>'w')::bigint;

-- query: T-C4-1 | Business query
SELECT d.doc_id,json_object('tweet_id' VALUE any_value(d.doc->>'id_str'),'author' VALUE any_value(d.doc->'user'->>'screen_name'),'followers' VALUE (any_value(d.doc->'user'->>'followers_count'))::bigint,'lang' VALUE any_value(d.doc->>'lang'),'photos' VALUE count(*)) FROM {{table}} d CROSS JOIN LATERAL json_array_elements(NULLIF(d.doc->'extended_entities'->'media', 'null'::jsonb)::json) AS media(v)
  WHERE media.v->>'type' = 'photo'
   GROUP BY d.doc_id HAVING count(*) >= 2;

-- query: T-C4-2 | Business query
SELECT d.doc_id,json_object('tweet_id' VALUE any_value(d.doc->>'id_str'),'author' VALUE any_value(d.doc->'user'->>'screen_name'),'followers' VALUE (any_value(d.doc->'user'->>'followers_count'))::bigint,'lang' VALUE any_value(d.doc->>'lang'),'long_videos' VALUE count(*),'duration_ms' VALUE sum((media.v->'video_info'->>'duration_millis')::bigint),'avg_duration_ms' VALUE avg((media.v->'video_info'->>'duration_millis')::bigint)) FROM {{table}} d CROSS JOIN LATERAL json_array_elements(NULLIF(d.doc->'extended_entities'->'media', 'null'::jsonb)::json) AS media(v)
  WHERE media.v->>'type' = 'video' AND (media.v->'video_info'->>'duration_millis')::bigint >= 30000
   GROUP BY d.doc_id HAVING count(*) >= 1;

-- query: T-C4-3 | Business query
SELECT d.doc_id,json_object('tweet_id' VALUE any_value(d.doc->>'id_str'),'original_id' VALUE any_value(d.doc->'retweeted_status'->>'id_str'),'original_author' VALUE any_value(d.doc->'retweeted_status'->'user'->>'screen_name'),'original_retweets' VALUE (any_value(d.doc->'retweeted_status'->>'retweet_count'))::bigint,'long_videos' VALUE count(*),'duration_ms' VALUE sum((media.v->'video_info'->>'duration_millis')::bigint),'avg_duration_ms' VALUE avg((media.v->'video_info'->>'duration_millis')::bigint)) FROM {{table}} d CROSS JOIN LATERAL json_array_elements(NULLIF(d.doc->'retweeted_status'->'extended_entities'->'media', 'null'::jsonb)::json) AS media(v)
  WHERE ((d.doc->'retweeted_status'->>'retweet_count')::bigint >= 1000) AND (media.v->>'type' = 'video' AND (media.v->'video_info'->>'duration_millis')::bigint >= 30000)
 GROUP BY d.doc_id HAVING count(*) >= 1;

-- query: T-C4-4 | Business query
SELECT d.doc_id,json_object('tweet_id' VALUE any_value(d.doc->>'id_str'),'original_id' VALUE any_value(d.doc->'quoted_status'->>'id_str'),'original_author' VALUE any_value(d.doc->'quoted_status'->'user'->>'screen_name'),'original_likes' VALUE (any_value(d.doc->'quoted_status'->>'favorite_count'))::bigint,'landscape_photos' VALUE count(*)) FROM {{table}} d CROSS JOIN LATERAL json_array_elements(NULLIF(d.doc->'quoted_status'->'extended_entities'->'media', 'null'::jsonb)::json) AS media(v)
  WHERE ((d.doc->>'is_quote_status')::boolean = true
  AND (d.doc->'quoted_status'->>'favorite_count')::bigint >= 1000) AND (media.v->>'type' = 'photo' AND (media.v->'sizes'->'large'->>'w')::bigint > (media.v->'sizes'->'large'->>'h')::bigint)
 GROUP BY d.doc_id HAVING count(*) >= 1;
