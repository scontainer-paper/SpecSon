-- query: O-C1-1 | Business query
SELECT VALUE d.doc_id FROM {{table}} d WHERE ((d.`doc`.`publication_year` >= 2020) AND (d.`doc`.`cited_by_count` >= 50));

-- query: O-C1-2 | Business query
SELECT VALUE d.doc_id FROM {{table}} d WHERE ((d.`doc`.`type` = "article") AND (d.`doc`.`publication_year` >= 2020) AND (d.`doc`.`is_retracted` = false));

-- query: O-C1-3 | Business query
SELECT VALUE d.doc_id FROM {{table}} d WHERE ((d.`doc`.`authors_count` >= 10) AND (d.`doc`.`countries_distinct_count` >= 3));

-- query: O-C1-4 | Business query
SELECT VALUE d.doc_id FROM {{table}} d WHERE ((d.`doc`.`open_access`.`oa_status` = "gold") AND (d.`doc`.`cited_by_count` >= 20));

-- query: O-C2-1 | Business query
SELECT VALUE d.doc_id FROM {{table}} d WHERE (SOME a IN if_missing_or_null(d.`doc`.`indexed_in`,[]) SATISFIES (a = "pubmed"));

-- query: O-C2-2 | Business query
SELECT VALUE d.doc_id FROM {{table}} d WHERE (SOME a IN if_missing_or_null(d.`doc`.`counts_by_year`,[]) SATISFIES (a.`cited_by_count` >= 20));

-- query: O-C2-3 | Business query
SELECT VALUE d.doc_id FROM {{table}} d WHERE (array_sum((SELECT VALUE a.`cited_by_count` FROM if_missing_or_null(d.`doc`.`counts_by_year`,[]) a WHERE true)) >= 100);

-- query: O-C2-4 | Business query
SELECT VALUE d.doc_id FROM {{table}} d WHERE (array_avg((SELECT VALUE a.`cited_by_count` FROM if_missing_or_null(d.`doc`.`counts_by_year`,[]) a WHERE true)) >= 10);

-- query: O-C3-1 | Business query
SELECT VALUE d.doc_id FROM {{table}} d WHERE (SOME a IN if_missing_or_null(d.`doc`.`locations`,[]) SATISFIES ((a.`is_oa` = true) AND (a.`is_published` = true) AND (a.`source`.`type` = "journal")));

-- query: O-C3-2 | Business query
SELECT DISTINCT VALUE d.doc_id FROM {{table}} d UNNEST d.`doc`.`authorships` a UNNEST a.`institutions` i WHERE ((a.`is_corresponding` = true) AND ((i.`country_code` = "US") AND (i.`type` = "education")));

-- query: O-C3-3 | Business query
SELECT DISTINCT VALUE d.doc_id FROM {{table}} d UNNEST d.`doc`.`authorships` a UNNEST a.`institutions` i WHERE ((a.`author_position` = "first") AND ((i.`country_code` = "GB") AND (i.`type` = "healthcare")));

-- query: O-C3-4 | Business query
SELECT VALUE d.doc_id FROM {{table}} d WHERE (SOME a IN if_missing_or_null(d.`doc`.`counts_by_year`,[]) SATISFIES (((a.`year` >= 2020) AND (a.`year` <= 2024)) AND (a.`cited_by_count` >= 20)));

-- query: O-C4-1 | Business query
SELECT VALUE {"doc_id":document_id,"result":{"id": if_missing_or_null(field_0,null), "title": if_missing_or_null(field_1,null), "publication_year": if_missing_or_null(field_2,null), "citations_2020_2024": if_missing_or_null(sum(a.`cited_by_count`),null), "avg_recorded_year": if_missing_or_null(avg(a.`cited_by_count`),null), "recorded_years": if_missing_or_null(count(*),null)}} FROM {{table}} d UNNEST d.`doc`.`counts_by_year` a WHERE (true AND ((a.`year` >= 2020) AND (a.`year` <= 2024))) GROUP BY d.doc_id AS document_id, d.`doc`.`id` AS field_0, d.`doc`.`title` AS field_1, d.`doc`.`publication_year` AS field_2 HAVING (sum(a.`cited_by_count`) >= 50);

-- query: O-C4-2 | Business query
WITH matched AS (SELECT DISTINCT VALUE d.doc_id FROM {{table}} d UNNEST d.`doc`.`authorships` a UNNEST a.`institutions` i WHERE ((a.`is_corresponding` = true) AND ((i.`country_code` = "US") AND (i.`type` = "education")))) SELECT VALUE {"doc_id":document_id,"result":{"id": if_missing_or_null(field_0,null), "title": if_missing_or_null(field_1,null), "citations_2020_2024": if_missing_or_null(sum(a.`cited_by_count`),null), "avg_recorded_year": if_missing_or_null(avg(a.`cited_by_count`),null)}} FROM {{table}} d JOIN matched m ON d.doc_id=m UNNEST d.`doc`.`counts_by_year` a WHERE (true AND ((a.`year` >= 2020) AND (a.`year` <= 2024))) GROUP BY d.doc_id AS document_id, d.`doc`.`id` AS field_0, d.`doc`.`title` AS field_1 HAVING (sum(a.`cited_by_count`) >= 1);

-- query: O-C4-3 | Business query
SELECT VALUE {"doc_id":d.doc_id,"result":{"work_id": if_missing_or_null(d.`doc`.`id`,null), "title": if_missing_or_null(d.`doc`.`title`,null), "author_id": if_missing_or_null(a.`author`.`id`,null), "author_name": if_missing_or_null(a.`author`.`display_name`,null), "us_education_affiliations": if_missing_or_null(s.`n`,null)}} FROM {{table}} d UNNEST if_missing_or_null(d.`doc`.`authorships`,[]) a, (SELECT VALUE {"n": count(*)} FROM if_missing_or_null(a.`institutions`,[]) i WHERE ((i.`country_code` = "US") AND (i.`type` = "education"))) s WHERE (true AND (s.`n` >= 2) AND (a.`is_corresponding` = true));

-- query: O-C4-4 | Business query
SELECT VALUE {"doc_id":d.doc_id,"result":{"id": if_missing_or_null(d.`doc`.`id`,null), "title": if_missing_or_null(d.`doc`.`title`,null), "cited_by_count": if_missing_or_null(d.`doc`.`cited_by_count`,null), "reusable_published_locations": if_missing_or_null(s.`n`,null)}} FROM {{table}} d, (SELECT VALUE {"n": count(*)} FROM if_missing_or_null(d.`doc`.`locations`,[]) a WHERE ((a.`is_oa` = true) AND (a.`is_published` = true) AND (a.`license` = "cc-by") AND (a.`source`.`type` = "journal"))) s WHERE (true AND (s.`n` >= 1));
