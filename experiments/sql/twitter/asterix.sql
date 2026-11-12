-- query: T-C1-1 | Business query
SELECT VALUE d.doc_id FROM {{table}} d WHERE ((d.`doc`.`user`.`verified` = true) AND (d.`doc`.`user`.`followers_count` >= 10000));

-- query: T-C1-2 | Business query
SELECT VALUE d.doc_id FROM {{table}} d WHERE ((d.`doc`.`lang` = "en") AND (d.`doc`.`user`.`followers_count` >= 1000));

-- query: T-C1-3 | Business query
SELECT VALUE d.doc_id FROM {{table}} d WHERE ((d.`doc`.`retweeted_status`.`lang` = "en") AND (d.`doc`.`retweeted_status`.`retweet_count` >= 1000));

-- query: T-C1-4 | Business query
SELECT VALUE d.doc_id FROM {{table}} d WHERE ((d.`doc`.`is_quote_status` = true) AND (d.`doc`.`quoted_status`.`favorite_count` >= 1000));

-- query: T-C2-1 | Business query
SELECT VALUE d.doc_id FROM {{table}} d WHERE (SOME a IN if_missing_or_null(d.`doc`.`entities`.`hashtags`,[]) SATISFIES (a.`text` = "NowPlaying"));

-- query: T-C2-2 | Business query
SELECT VALUE d.doc_id FROM {{table}} d WHERE (SOME a IN if_missing_or_null(d.`doc`.`extended_entities`.`media`,[]) SATISFIES (a.`type` = "video"));

-- query: T-C2-3 | Business query
SELECT VALUE d.doc_id FROM {{table}} d WHERE (array_sum((SELECT VALUE a.`video_info`.`duration_millis` FROM if_missing_or_null(d.`doc`.`extended_entities`.`media`,[]) a WHERE true)) >= 60000);

-- query: T-C2-4 | Business query
SELECT VALUE d.doc_id FROM {{table}} d WHERE (array_avg((SELECT VALUE a.`video_info`.`duration_millis` FROM if_missing_or_null(d.`doc`.`extended_entities`.`media`,[]) a WHERE true)) >= 30000);

-- query: T-C3-1 | Business query
SELECT DISTINCT VALUE d.doc_id FROM {{table}} d UNNEST d.`doc`.`extended_entities`.`media` a WHERE ((a.`type` = "photo") AND (a.`sizes`.`large`.`w` > a.`sizes`.`large`.`h`));

-- query: T-C3-2 | Business query
SELECT DISTINCT VALUE d.doc_id FROM {{table}} d UNNEST d.`doc`.`extended_entities`.`media` a WHERE ((a.`type` = "video") AND (a.`sizes`.`large`.`h` > a.`sizes`.`large`.`w`));

-- query: T-C3-3 | Business query
SELECT DISTINCT VALUE d.doc_id FROM {{table}} d UNNEST d.`doc`.`extended_entities`.`media` a WHERE ((a.`type` = "video") AND (a.`sizes`.`large`.`w` > a.`sizes`.`large`.`h`) AND (a.`video_info`.`duration_millis` >= 30000));

-- query: T-C3-4 | Business query
SELECT VALUE d.doc_id FROM {{table}} d WHERE ((d.`doc`.`retweeted_status`.`retweet_count` >= 1000) AND (SOME a IN if_missing_or_null(d.`doc`.`retweeted_status`.`extended_entities`.`media`,[]) SATISFIES ((a.`type` = "photo") AND (a.`sizes`.`large`.`h` > a.`sizes`.`large`.`w`))));

-- query: T-C4-1 | Business query
SELECT VALUE {"doc_id":document_id,"result":{"tweet_id": if_missing_or_null(field_0,null), "author": if_missing_or_null(field_1,null), "followers": if_missing_or_null(field_2,null), "lang": if_missing_or_null(field_3,null), "photos": if_missing_or_null(count(*),null)}} FROM {{table}} d UNNEST d.`doc`.`extended_entities`.`media` a WHERE (true AND (a.`type` = "photo")) GROUP BY d.doc_id AS document_id, d.`doc`.`id_str` AS field_0, d.`doc`.`user`.`screen_name` AS field_1, d.`doc`.`user`.`followers_count` AS field_2, d.`doc`.`lang` AS field_3 HAVING (count(*) >= 2);

-- query: T-C4-2 | Business query
SELECT VALUE {"doc_id":document_id,"result":{"tweet_id": if_missing_or_null(field_0,null), "author": if_missing_or_null(field_1,null), "followers": if_missing_or_null(field_2,null), "lang": if_missing_or_null(field_3,null), "long_videos": if_missing_or_null(count(*),null), "duration_ms": if_missing_or_null(sum(a.`video_info`.`duration_millis`),null), "avg_duration_ms": if_missing_or_null(avg(a.`video_info`.`duration_millis`),null)}} FROM {{table}} d UNNEST d.`doc`.`extended_entities`.`media` a WHERE (true AND ((a.`type` = "video") AND (a.`video_info`.`duration_millis` >= 30000))) GROUP BY d.doc_id AS document_id, d.`doc`.`id_str` AS field_0, d.`doc`.`user`.`screen_name` AS field_1, d.`doc`.`user`.`followers_count` AS field_2, d.`doc`.`lang` AS field_3 HAVING (count(*) >= 1);

-- query: T-C4-3 | Business query
SELECT VALUE {"doc_id":d.doc_id,"result":{"tweet_id": if_missing_or_null(d.`doc`.`id_str`,null), "original_id": if_missing_or_null(d.`doc`.`retweeted_status`.`id_str`,null), "original_author": if_missing_or_null(d.`doc`.`retweeted_status`.`user`.`screen_name`,null), "original_retweets": if_missing_or_null(d.`doc`.`retweeted_status`.`retweet_count`,null), "long_videos": if_missing_or_null(s.`n`,null), "duration_ms": if_missing_or_null(s.`duration`,null), "avg_duration_ms": if_missing_or_null(s.`average`,null)}} FROM {{table}} d, (SELECT VALUE {"n": count(*), "duration": sum(a.`video_info`.`duration_millis`), "average": avg(a.`video_info`.`duration_millis`)} FROM if_missing_or_null(d.`doc`.`retweeted_status`.`extended_entities`.`media`,[]) a WHERE ((a.`type` = "video") AND (a.`video_info`.`duration_millis` >= 30000))) s WHERE ((d.`doc`.`retweeted_status`.`retweet_count` >= 1000) AND (s.`n` >= 1));

-- query: T-C4-4 | Business query
SELECT VALUE {"doc_id":d.doc_id,"result":{"tweet_id": if_missing_or_null(d.`doc`.`id_str`,null), "original_id": if_missing_or_null(d.`doc`.`quoted_status`.`id_str`,null), "original_author": if_missing_or_null(d.`doc`.`quoted_status`.`user`.`screen_name`,null), "original_likes": if_missing_or_null(d.`doc`.`quoted_status`.`favorite_count`,null), "landscape_photos": if_missing_or_null(s.`n`,null)}} FROM {{table}} d, (SELECT VALUE {"n": count(*)} FROM if_missing_or_null(d.`doc`.`quoted_status`.`extended_entities`.`media`,[]) a WHERE ((a.`type` = "photo") AND (a.`sizes`.`large`.`w` > a.`sizes`.`large`.`h`))) s WHERE (((d.`doc`.`is_quote_status` = true) AND (d.`doc`.`quoted_status`.`favorite_count` >= 1000)) AND (s.`n` >= 1));
