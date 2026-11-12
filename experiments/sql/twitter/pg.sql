-- query: T-C1-1 | Business query
SELECT d.doc_id FROM {{table}} d WHERE EXISTS (SELECT 1 WHERE (d.doc#>>'{user,verified}')::boolean = true AND (d.doc#>>'{user,followers_count}')::bigint >= 10000);

-- query: T-C1-2 | Business query
SELECT d.doc_id FROM {{table}} d WHERE JSON_EXISTS(d.doc, '$ ? (@.lang == "en" && @.user.followers_count >= 1000)');

-- query: T-C1-3 | Business query
SELECT d.doc_id FROM {{table}} d WHERE JSON_EXISTS(d.doc, '$ ? (@.retweeted_status.lang == "en" && @.retweeted_status.retweet_count >= 1000)');

-- query: T-C1-4 | Business query
SELECT d.doc_id FROM {{table}} d WHERE JSON_EXISTS(d.doc, '$ ? (@.is_quote_status == true && @.quoted_status.favorite_count >= 1000)');

-- query: T-C2-1 | Business query
SELECT d.doc_id FROM {{table}} d WHERE JSON_EXISTS(d.doc, '$.entities.hashtags[*] ? (@.text == "NowPlaying")');

-- query: T-C2-2 | Business query
SELECT d.doc_id FROM {{table}} d WHERE JSON_EXISTS(d.doc, '$.extended_entities.media[*] ? (@.type == "video")');

-- query: T-C2-3 | Business query
WITH items AS MATERIALIZED (SELECT d.doc_id,media#>>'{video_info,duration_millis}' AS v0 FROM {{table}} d CROSS JOIN LATERAL jsonb_array_elements(NULLIF(d.doc#>'{extended_entities,media}', 'null'::jsonb)) AS media) SELECT i.doc_id FROM items i GROUP BY i.doc_id HAVING sum((i.v0)::bigint) >= 60000;

-- query: T-C2-4 | Business query
WITH items AS MATERIALIZED (SELECT d.doc_id,media#>>'{video_info,duration_millis}' AS v0 FROM {{table}} d CROSS JOIN LATERAL jsonb_array_elements(NULLIF(d.doc#>'{extended_entities,media}', 'null'::jsonb)) AS media) SELECT i.doc_id FROM items i GROUP BY i.doc_id HAVING avg((i.v0)::bigint) >= 30000;

-- query: T-C3-1 | Business query
SELECT d.doc_id FROM {{table}} d WHERE JSON_EXISTS(d.doc, '$.extended_entities.media[*] ? (@.type == "photo" && @.sizes.large.w > @.sizes.large.h)');

-- query: T-C3-2 | Business query
SELECT d.doc_id FROM {{table}} d WHERE JSON_EXISTS(d.doc, '$.extended_entities.media[*] ? (@.type == "video" && @.sizes.large.h > @.sizes.large.w)');

-- query: T-C3-3 | Business query
SELECT d.doc_id FROM {{table}} d WHERE JSON_EXISTS(d.doc, '$.extended_entities.media[*] ? (@.type == "video" && @.sizes.large.w > @.sizes.large.h && @.video_info.duration_millis >= 30000)');

-- query: T-C3-4 | Business query
SELECT d.doc_id FROM {{table}} d WHERE JSON_EXISTS(d.doc, '$.retweeted_status ? (@.retweet_count >= 1000).extended_entities.media[*] ? (@.type == "photo" && @.sizes.large.h > @.sizes.large.w)');

-- query: T-C4-1 | Business query
SELECT d.doc_id,q.* FROM {{table}} d CROSS JOIN LATERAL (SELECT jsonb_build_object('tweet_id', d.doc->>'id_str', 'author', d.doc#>>'{user,screen_name}',
  'followers', (d.doc#>>'{user,followers_count}')::bigint, 'lang', d.doc->>'lang', 'photos', summary.photos)
FROM LATERAL (
  SELECT count(*) AS photos
  FROM jsonb_array_elements(NULLIF(d.doc#>'{extended_entities,media}', 'null'::jsonb)) AS media
  WHERE media->>'type' = 'photo'
  HAVING count(*) >= 2
) AS summary) q WHERE JSON_EXISTS(d.doc, '$.extended_entities.media[*]');

-- query: T-C4-2 | Business query
WITH items AS MATERIALIZED (SELECT d.doc_id,d.doc->>'id_str' AS v0,d.doc#>>'{user,screen_name}' AS v1,d.doc#>>'{user,followers_count}' AS v2,d.doc->>'lang' AS v3,media#>>'{video_info,duration_millis}' AS v4 FROM (SELECT * FROM {{table}} WHERE doc#>'{extended_entities,media}' IS NOT NULL) d CROSS JOIN LATERAL jsonb_array_elements(NULLIF(d.doc#>'{extended_entities,media}', 'null'::jsonb)) AS media
  WHERE media->>'type' = 'video' AND (media#>>'{video_info,duration_millis}')::bigint >= 30000
  ) SELECT i.doc_id,jsonb_build_object('tweet_id', any_value(i.v0), 'author', any_value(i.v1),
  'followers', (any_value(i.v2))::bigint, 'lang', any_value(i.v3),
  'long_videos', count(*), 'duration_ms', sum((i.v4)::bigint), 'avg_duration_ms', avg((i.v4)::bigint)) FROM items i GROUP BY i.doc_id HAVING count(*) >= 1;

-- query: T-C4-3 | Business query
WITH items AS MATERIALIZED (SELECT d.doc_id,d.doc->>'id_str' AS v0,d.doc#>>'{retweeted_status,id_str}' AS v1,d.doc#>>'{retweeted_status,user,screen_name}' AS v2,d.doc#>>'{retweeted_status,retweet_count}' AS v3,media#>>'{video_info,duration_millis}' AS v4 FROM {{table}} d CROSS JOIN LATERAL jsonb_array_elements(NULLIF(d.doc#>'{retweeted_status,extended_entities,media}', 'null'::jsonb)) AS media
  WHERE ((d.doc#>>'{retweeted_status,retweet_count}')::bigint >= 1000) AND (media->>'type' = 'video' AND (media#>>'{video_info,duration_millis}')::bigint >= 30000)
) SELECT i.doc_id,jsonb_build_object('tweet_id', any_value(i.v0), 'original_id', any_value(i.v1),
  'original_author', any_value(i.v2),
  'original_retweets', (any_value(i.v3))::bigint,
  'long_videos', count(*), 'duration_ms', sum((i.v4)::bigint), 'avg_duration_ms', avg((i.v4)::bigint)) FROM items i GROUP BY i.doc_id HAVING count(*) >= 1;

-- query: T-C4-4 | Business query
SELECT d.doc_id,q.* FROM {{table}} d CROSS JOIN LATERAL (SELECT jsonb_build_object('tweet_id', d.doc->>'id_str', 'original_id', d.doc#>>'{quoted_status,id_str}',
  'original_author', d.doc#>>'{quoted_status,user,screen_name}',
  'original_likes', (d.doc#>>'{quoted_status,favorite_count}')::bigint, 'landscape_photos', summary.photos)
FROM LATERAL (
  SELECT count(*) AS photos
  FROM jsonb_array_elements(NULLIF(d.doc#>'{quoted_status,extended_entities,media}', 'null'::jsonb)) AS media
  WHERE media->>'type' = 'photo' AND (media#>>'{sizes,large,w}')::bigint > (media#>>'{sizes,large,h}')::bigint
  HAVING count(*) >= 1
) AS summary WHERE (d.doc->>'is_quote_status')::boolean = true
  AND (d.doc#>>'{quoted_status,favorite_count}')::bigint >= 1000) q;
