-- query: T-C1-1 | Business query
SELECT doc_id FROM {{table}} WHERE {{relational_filter}} AND doc.user.verified = true AND doc.user.followers_count >= 10000 FORMAT JSONCompactEachRow;

-- query: T-C1-2 | Business query
SELECT doc_id FROM {{table}} WHERE {{relational_filter}} AND doc.lang = 'en' AND doc.user.followers_count >= 1000 FORMAT JSONCompactEachRow;

-- query: T-C1-3 | Business query
SELECT doc_id FROM {{table}} WHERE {{relational_filter}} AND doc.retweeted_status.lang = 'en' AND doc.retweeted_status.retweet_count >= 1000 FORMAT JSONCompactEachRow;

-- query: T-C1-4 | Business query
SELECT doc_id FROM {{table}} WHERE {{relational_filter}} AND doc.is_quote_status = true AND doc.quoted_status.favorite_count >= 1000 FORMAT JSONCompactEachRow;

-- query: T-C2-1 | Business query
SELECT doc_id FROM {{table}} WHERE {{relational_filter}} AND arrayExists((x0) -> x0 = 'NowPlaying',doc.entities.hashtags.text) FORMAT JSONCompactEachRow;

-- query: T-C2-2 | Business query
SELECT doc_id FROM {{table}} WHERE {{relational_filter}} AND arrayExists((x0) -> x0 = 'video',doc.extended_entities.media.type) FORMAT JSONCompactEachRow;

-- query: T-C2-3 | Business query
SELECT doc_id FROM {{table}} WHERE {{relational_filter}} AND arrayReduce('sumOrNull',doc.extended_entities.media.video_info.duration_millis) >= 60000 FORMAT JSONCompactEachRow;

-- query: T-C2-4 | Business query
SELECT doc_id FROM {{table}} WHERE {{relational_filter}} AND arrayReduce('avgOrNull',doc.extended_entities.media.video_info.duration_millis) >= 30000 FORMAT JSONCompactEachRow;

-- query: T-C3-1 | Business query
SELECT doc_id FROM {{table}} WHERE {{relational_filter}} AND arrayExists((x0,x1,x2) -> x2 = 'photo' AND x1 > x0,doc.extended_entities.media.sizes.large.h,doc.extended_entities.media.sizes.large.w,doc.extended_entities.media.type) FORMAT JSONCompactEachRow;

-- query: T-C3-2 | Business query
SELECT doc_id FROM {{table}} WHERE {{relational_filter}} AND arrayExists((x0,x1,x2) -> x2 = 'video' AND x0 > x1,doc.extended_entities.media.sizes.large.h,doc.extended_entities.media.sizes.large.w,doc.extended_entities.media.type) FORMAT JSONCompactEachRow;

-- query: T-C3-3 | Business query
SELECT doc_id FROM {{table}} WHERE {{relational_filter}} AND arrayExists((x0,x1,x2,x3) -> x2 = 'video' AND x1 > x0
    AND x3 >= 30000,doc.extended_entities.media.sizes.large.h,doc.extended_entities.media.sizes.large.w,doc.extended_entities.media.type,doc.extended_entities.media.video_info.duration_millis) FORMAT JSONCompactEachRow;

-- query: T-C3-4 | Business query
SELECT doc_id FROM {{table}} WHERE {{relational_filter}} AND doc.retweeted_status.retweet_count >= 1000 AND arrayExists((x0,x1,x2) -> x2 = 'photo' AND x0 > x1,doc.retweeted_status.extended_entities.media.sizes.large.h,doc.retweeted_status.extended_entities.media.sizes.large.w,doc.retweeted_status.extended_entities.media.type) FORMAT JSONCompactEachRow;

-- query: T-C4-1 | Business query
WITH arrayFilter(t -> t.1 = 'photo',arrayZip(doc.extended_entities.media.type)) AS selected SELECT doc_id,toJSONString(tuple(doc.id_str AS tweet_id,doc.user.screen_name AS author,doc.user.followers_count AS followers,doc.lang AS lang,length(selected) AS photos)) AS result FROM {{table}} WHERE {{relational_filter}} AND length(selected) >= 2 FORMAT JSONCompactEachRow;

-- query: T-C4-2 | Business query
WITH arrayFilter(t -> t.1 = 'video' AND t.2 >= 30000,arrayZip(doc.extended_entities.media.type,doc.extended_entities.media.video_info.duration_millis)) AS selected SELECT doc_id,toJSONString(tuple(doc.id_str AS tweet_id,doc.user.screen_name AS author,doc.user.followers_count AS followers,doc.lang AS lang,length(selected) AS long_videos,arrayReduce('sumOrNull',arrayMap(t -> t.2,selected)) AS duration_ms,arrayReduce('avgOrNull',arrayMap(t -> t.2,selected)) AS avg_duration_ms)) AS result FROM {{table}} WHERE {{relational_filter}} AND length(selected) >= 1 FORMAT JSONCompactEachRow;

-- query: T-C4-3 | Business query
WITH arrayFilter(t -> t.1 = 'video' AND t.2 >= 30000,arrayZip(doc.retweeted_status.extended_entities.media.type,doc.retweeted_status.extended_entities.media.video_info.duration_millis)) AS selected SELECT doc_id,toJSONString(tuple(doc.id_str AS tweet_id,doc.retweeted_status.id_str AS original_id,doc.retweeted_status.user.screen_name AS original_author,doc.retweeted_status.retweet_count AS original_retweets,length(selected) AS long_videos,arrayReduce('sumOrNull',arrayMap(t -> t.2,selected)) AS duration_ms,arrayReduce('avgOrNull',arrayMap(t -> t.2,selected)) AS avg_duration_ms)) AS result FROM {{table}} WHERE {{relational_filter}} AND (doc.retweeted_status.retweet_count >= 1000) AND length(selected) >= 1 FORMAT JSONCompactEachRow;

-- query: T-C4-4 | Business query
WITH arrayFilter(t -> t.3 = 'photo' AND t.2 > t.1,arrayZip(doc.quoted_status.extended_entities.media.sizes.large.h,doc.quoted_status.extended_entities.media.sizes.large.w,doc.quoted_status.extended_entities.media.type)) AS selected SELECT doc_id,toJSONString(tuple(doc.id_str AS tweet_id,doc.quoted_status.id_str AS original_id,doc.quoted_status.user.screen_name AS original_author,doc.quoted_status.favorite_count AS original_likes,length(selected) AS landscape_photos)) AS result FROM {{table}} WHERE {{relational_filter}} AND (doc.is_quote_status = true
  AND doc.quoted_status.favorite_count >= 1000) AND length(selected) >= 1 FORMAT JSONCompactEachRow;
