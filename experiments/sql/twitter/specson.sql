-- query: T-C1-1 | Business query
SELECT d.doc_id FROM {{table}} d WHERE EXISTS (SELECT 1 WHERE (d.doc#>>'{user,verified}')::boolean = true AND (d.doc#>>'{user,followers_count}')::bigint >= 10000);

-- query: T-C1-2 | Business query
SELECT d.doc_id FROM {{table}} d WHERE EXISTS (SELECT 1 WHERE d.doc->>'lang' = 'en' AND (d.doc#>>'{user,followers_count}')::bigint >= 1000);

-- query: T-C1-3 | Business query
SELECT d.doc_id FROM {{table}} d WHERE EXISTS (SELECT 1 WHERE d.doc#>>'{retweeted_status,lang}' = 'en' AND (d.doc#>>'{retweeted_status,retweet_count}')::bigint >= 1000);

-- query: T-C1-4 | Business query
SELECT d.doc_id FROM {{table}} d WHERE EXISTS (SELECT 1 WHERE (d.doc->>'is_quote_status')::boolean = true AND (d.doc#>>'{quoted_status,favorite_count}')::bigint >= 1000);

-- query: T-C2-1 | Business query
SELECT d.doc_id FROM {{table}} d WHERE EXISTS (SELECT 1 WHERE EXISTS (
  SELECT 1 FROM jsonb_array_elements(NULLIF(d.doc#>'{entities,hashtags}', 'null'::jsonb)) AS tag
  WHERE tag->>'text' = 'NowPlaying'));

-- query: T-C2-2 | Business query
SELECT d.doc_id FROM {{table}} d WHERE EXISTS (SELECT 1 WHERE EXISTS (
  SELECT 1 FROM jsonb_array_elements(NULLIF(d.doc#>'{extended_entities,media}', 'null'::jsonb)) AS media
  WHERE media->>'type' = 'video'));

-- query: T-C2-3 | Business query
SELECT d.doc_id FROM {{table}} d WHERE EXISTS (SELECT 1 WHERE (SELECT sum((media#>>'{video_info,duration_millis}')::bigint)
  FROM jsonb_array_elements(NULLIF(d.doc#>'{extended_entities,media}', 'null'::jsonb)) AS media) >= 60000);

-- query: T-C2-4 | Business query
SELECT d.doc_id FROM {{table}} d WHERE EXISTS (SELECT 1 WHERE (SELECT avg((media#>>'{video_info,duration_millis}')::bigint)
  FROM jsonb_array_elements(NULLIF(d.doc#>'{extended_entities,media}', 'null'::jsonb)) AS media) >= 30000);

-- query: T-C3-1 | Business query
SELECT d.doc_id FROM {{table}} d WHERE EXISTS (SELECT 1 WHERE EXISTS (
  SELECT 1 FROM jsonb_array_elements(NULLIF(d.doc#>'{extended_entities,media}', 'null'::jsonb)) AS media
  WHERE media->>'type' = 'photo' AND (media#>>'{sizes,large,w}')::bigint > (media#>>'{sizes,large,h}')::bigint));

-- query: T-C3-2 | Business query
SELECT d.doc_id FROM {{table}} d WHERE EXISTS (SELECT 1 WHERE EXISTS (
  SELECT 1 FROM jsonb_array_elements(NULLIF(d.doc#>'{extended_entities,media}', 'null'::jsonb)) AS media
  WHERE media->>'type' = 'video' AND (media#>>'{sizes,large,h}')::bigint > (media#>>'{sizes,large,w}')::bigint));

-- query: T-C3-3 | Business query
SELECT d.doc_id FROM {{table}} d WHERE EXISTS (SELECT 1 WHERE EXISTS (
  SELECT 1 FROM jsonb_array_elements(NULLIF(d.doc#>'{extended_entities,media}', 'null'::jsonb)) AS media
  WHERE media->>'type' = 'video' AND (media#>>'{sizes,large,w}')::bigint > (media#>>'{sizes,large,h}')::bigint
    AND (media#>>'{video_info,duration_millis}')::bigint >= 30000));

-- query: T-C3-4 | Business query
SELECT d.doc_id FROM {{table}} d WHERE EXISTS (SELECT 1 WHERE (d.doc#>>'{retweeted_status,retweet_count}')::bigint >= 1000 AND EXISTS (
  SELECT 1 FROM jsonb_array_elements(NULLIF(d.doc#>'{retweeted_status,extended_entities,media}', 'null'::jsonb)) AS media
  WHERE media->>'type' = 'photo' AND (media#>>'{sizes,large,h}')::bigint > (media#>>'{sizes,large,w}')::bigint));

-- query: T-C4-1 | Business query
SELECT d.doc_id,q.* FROM {{table}} d CROSS JOIN LATERAL (SELECT jsonb_build_object('tweet_id', d.doc->>'id_str', 'author', d.doc#>>'{user,screen_name}',
  'followers', (d.doc#>>'{user,followers_count}')::bigint, 'lang', d.doc->>'lang', 'photos', summary.photos)
FROM LATERAL (
  SELECT count(*) AS photos
  FROM jsonb_array_elements(NULLIF(d.doc#>'{extended_entities,media}', 'null'::jsonb)) AS media
  WHERE media->>'type' = 'photo'
  HAVING count(*) >= 2
) AS summary) q;

-- query: T-C4-2 | Business query
SELECT d.doc_id,q.* FROM {{table}} d CROSS JOIN LATERAL (SELECT jsonb_build_object('tweet_id', d.doc->>'id_str', 'author', d.doc#>>'{user,screen_name}',
  'followers', (d.doc#>>'{user,followers_count}')::bigint, 'lang', d.doc->>'lang',
  'long_videos', summary.videos, 'duration_ms', summary.duration, 'avg_duration_ms', summary.average)
FROM LATERAL (
  SELECT count(*) AS videos, sum((media#>>'{video_info,duration_millis}')::bigint) AS duration,
    avg((media#>>'{video_info,duration_millis}')::bigint) AS average
  FROM jsonb_array_elements(NULLIF(d.doc#>'{extended_entities,media}', 'null'::jsonb)) AS media
  WHERE media->>'type' = 'video' AND (media#>>'{video_info,duration_millis}')::bigint >= 30000
  HAVING count(*) >= 1
) AS summary) q;

-- query: T-C4-3 | Business query
SELECT d.doc_id,q.* FROM {{table}} d CROSS JOIN LATERAL (SELECT jsonb_build_object('tweet_id', d.doc->>'id_str', 'original_id', d.doc#>>'{retweeted_status,id_str}',
  'original_author', d.doc#>>'{retweeted_status,user,screen_name}',
  'original_retweets', (d.doc#>>'{retweeted_status,retweet_count}')::bigint,
  'long_videos', summary.videos, 'duration_ms', summary.duration, 'avg_duration_ms', summary.average)
FROM LATERAL (
  SELECT count(*) AS videos, sum((media#>>'{video_info,duration_millis}')::bigint) AS duration,
    avg((media#>>'{video_info,duration_millis}')::bigint) AS average
  FROM jsonb_array_elements(NULLIF(d.doc#>'{retweeted_status,extended_entities,media}', 'null'::jsonb)) AS media
  WHERE media->>'type' = 'video' AND (media#>>'{video_info,duration_millis}')::bigint >= 30000
  HAVING count(*) >= 1
) AS summary WHERE (d.doc#>>'{retweeted_status,retweet_count}')::bigint >= 1000) q;

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
