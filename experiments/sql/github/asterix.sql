-- query: G-C1-1 | Business query
SELECT VALUE d.doc_id FROM {{table}} d WHERE ((d.`doc`.`payload`.`issue`.`state` = "open") AND (d.`doc`.`payload`.`issue`.`comments` >= 10));

-- query: G-C1-2 | Business query
SELECT VALUE d.doc_id FROM {{table}} d WHERE ((d.`doc`.`type` = "ForkEvent") AND (d.`doc`.`payload`.`forkee`.`size` >= 10240));

-- query: G-C1-3 | Business query
SELECT VALUE d.doc_id FROM {{table}} d WHERE ((d.`doc`.`payload`.`issue`.`state` = "open") AND (d.`doc`.`payload`.`issue`.`reactions`.`total_count` >= 5));

-- query: G-C1-4 | Business query
SELECT VALUE d.doc_id FROM {{table}} d WHERE ((d.`doc`.`type` = "IssueCommentEvent") AND (d.`doc`.`payload`.`action` = "created") AND (d.`doc`.`payload`.`issue`.`comments` >= 5));

-- query: G-C2-1 | Business query
SELECT DISTINCT VALUE d.doc_id FROM {{table}} d UNNEST d.`doc`.`payload`.`issue`.`labels` a WHERE (a.`name` = "bug");

-- query: G-C2-2 | Business query
SELECT VALUE d.doc_id FROM {{table}} d WHERE (SOME a IN if_missing_or_null(d.`doc`.`payload`.`release`.`assets`,[]) SATISFIES (a.`size` >= 104857600));

-- query: G-C2-3 | Business query
SELECT VALUE d.doc_id FROM {{table}} d WHERE (array_sum((SELECT VALUE a.`size` FROM if_missing_or_null(d.`doc`.`payload`.`release`.`assets`,[]) a WHERE true)) >= 104857600);

-- query: G-C2-4 | Business query
SELECT VALUE d.doc_id FROM {{table}} d WHERE (array_avg((SELECT VALUE a.`size` FROM if_missing_or_null(d.`doc`.`payload`.`release`.`assets`,[]) a WHERE true)) >= 10485760);

-- query: G-C3-1 | Business query
SELECT DISTINCT VALUE d.doc_id FROM {{table}} d UNNEST d.`doc`.`payload`.`release`.`assets` a WHERE ((a.`size` >= 10485760) AND (a.`content_type` = "application/zip"));

-- query: G-C3-2 | Business query
SELECT DISTINCT VALUE d.doc_id FROM {{table}} d UNNEST d.`doc`.`payload`.`issue`.`assignees` a WHERE ((a.`type` = "User") AND (a.`login` = d.`doc`.`payload`.`issue`.`user`.`login`));

-- query: G-C3-3 | Business query
SELECT DISTINCT VALUE d.doc_id FROM {{table}} d UNNEST d.`doc`.`payload`.`pages` a WHERE ((a.`page_name` = "Home") AND (a.`action` = "edited"));

-- query: G-C3-4 | Business query
SELECT DISTINCT VALUE d.doc_id FROM {{table}} d UNNEST d.`doc`.`payload`.`release`.`assets` a WHERE ((a.`state` = "uploaded") AND (a.`content_type` = "application/zip") AND (a.`uploader`.`type` = "Bot"));

-- query: G-C4-1 | Business query
SELECT VALUE {"doc_id":document_id,"result":{"repository": if_missing_or_null(field_0,null), "tag": if_missing_or_null(field_1,null), "assets": if_missing_or_null(count(*),null), "bytes": if_missing_or_null(sum(a.`size`),null), "downloads": if_missing_or_null(sum(a.`download_count`),null)}} FROM {{table}} d UNNEST d.`doc`.`payload`.`release`.`assets` a WHERE (true AND ((a.`state` = "uploaded") AND (a.`size` >= 1048576) AND (a.`content_type` = "application/octet-stream"))) GROUP BY d.doc_id AS document_id, d.`doc`.`repo`.`name` AS field_0, d.`doc`.`payload`.`release`.`tag_name` AS field_1 HAVING (count(*) >= 1);

-- query: G-C4-2 | Business query
SELECT VALUE {"doc_id":document_id,"result":{"repository": if_missing_or_null(field_0,null), "tag": if_missing_or_null(field_1,null), "zip_assets": if_missing_or_null(count(*),null), "bytes": if_missing_or_null(sum(a.`size`),null), "avg_bytes": if_missing_or_null(avg(a.`size`),null)}} FROM {{table}} d UNNEST d.`doc`.`payload`.`release`.`assets` a WHERE (true AND ((a.`state` = "uploaded") AND (a.`content_type` = "application/zip"))) GROUP BY d.doc_id AS document_id, d.`doc`.`repo`.`name` AS field_0, d.`doc`.`payload`.`release`.`tag_name` AS field_1 HAVING (avg(a.`size`) >= 10485760);

-- query: G-C4-3 | Business query
SELECT VALUE {"doc_id":document_id,"result":{"repository": if_missing_or_null(field_0,null), "tag": if_missing_or_null(field_1,null), "bot_assets": if_missing_or_null(count(*),null), "downloads": if_missing_or_null(sum(a.`download_count`),null), "avg_bytes": if_missing_or_null(avg(a.`size`),null)}} FROM {{table}} d UNNEST d.`doc`.`payload`.`release`.`assets` a WHERE (true AND ((a.`state` = "uploaded") AND (a.`uploader`.`type` = "Bot"))) GROUP BY d.doc_id AS document_id, d.`doc`.`repo`.`name` AS field_0, d.`doc`.`payload`.`release`.`tag_name` AS field_1 HAVING (count(*) >= 1);

-- query: G-C4-4 | Business query
SELECT VALUE {"doc_id":d.doc_id,"result":{"repository": if_missing_or_null(d.`doc`.`repo`.`name`,null), "issue": if_missing_or_null(d.`doc`.`payload`.`issue`.`html_url`,null), "title": if_missing_or_null(d.`doc`.`payload`.`issue`.`title`,null), "comments": if_missing_or_null(d.`doc`.`payload`.`issue`.`comments`,null), "human_assignees": if_missing_or_null(s.`n`,null)}} FROM {{table}} d, (SELECT VALUE {"n": count(*), "hits": sum(CASE WHEN (a.`login` = d.`doc`.`payload`.`issue`.`user`.`login`) THEN 1 ELSE 0 END)} FROM if_missing_or_null(d.`doc`.`payload`.`issue`.`assignees`,[]) a WHERE (a.`type` = "User")) s WHERE ((d.`doc`.`payload`.`issue`.`state` = "open") AND ((s.`n` >= 2) AND (s.`hits` > 0)));
