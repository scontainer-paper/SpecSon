-- query: O-C1-1 | Business query
SELECT d.doc_id FROM {{table}} d WHERE EXISTS (SELECT 1 WHERE (d.doc->>'publication_year')::bigint >= 2020 AND (d.doc->>'cited_by_count')::bigint >= 50);

-- query: O-C1-2 | Business query
SELECT d.doc_id FROM {{table}} d WHERE EXISTS (SELECT 1 WHERE d.doc->>'type' = 'article' AND (d.doc->>'publication_year')::bigint >= 2020 AND (d.doc->>'is_retracted')::boolean = false);

-- query: O-C1-3 | Business query
SELECT d.doc_id FROM {{table}} d WHERE EXISTS (SELECT 1 WHERE (d.doc->>'authors_count')::bigint >= 10 AND (d.doc->>'countries_distinct_count')::bigint >= 3);

-- query: O-C1-4 | Business query
SELECT d.doc_id FROM {{table}} d WHERE EXISTS (SELECT 1 WHERE d.doc->'open_access'->>'oa_status' = 'gold' AND (d.doc->>'cited_by_count')::bigint >= 20);

-- query: O-C2-1 | Business query
SELECT d.doc_id FROM {{table}} d WHERE JSON_EXISTS((d.doc->'indexed_in')::json, '$[*] ? (@ == "pubmed")');

-- query: O-C2-2 | Business query
SELECT DISTINCT d.doc_id FROM {{table}} d CROSS JOIN LATERAL json_array_elements(NULLIF(d.doc->'counts_by_year', 'null'::jsonb)::json) AS annual(v)
  WHERE (annual.v->>'cited_by_count')::bigint >= 20;

-- query: O-C2-3 | Business query
SELECT d.doc_id FROM {{table}} d CROSS JOIN LATERAL json_array_elements(NULLIF(d.doc->'counts_by_year', 'null'::jsonb)::json) AS annual(v) GROUP BY d.doc_id HAVING sum((annual.v->>'cited_by_count')::bigint) >= 100;

-- query: O-C2-4 | Business query
SELECT d.doc_id FROM {{table}} d CROSS JOIN LATERAL json_array_elements(NULLIF(d.doc->'counts_by_year', 'null'::jsonb)::json) AS annual(v) GROUP BY d.doc_id HAVING avg((annual.v->>'cited_by_count')::bigint) >= 10;

-- query: O-C3-1 | Business query
SELECT DISTINCT d.doc_id FROM {{table}} d CROSS JOIN LATERAL json_array_elements(NULLIF(d.doc->'locations', 'null'::jsonb)::json) AS location(v)
  WHERE (location.v->>'is_oa')::boolean = true AND (location.v->>'is_published')::boolean = true AND location.v->'source'->>'type' = 'journal';

-- query: O-C3-2 | Business query
SELECT DISTINCT d.doc_id FROM {{table}} d
CROSS JOIN LATERAL json_array_elements(NULLIF(d.doc->'authorships','null'::jsonb)::json) author(v)
CROSS JOIN LATERAL json_array_elements(NULLIF(author.v->'institutions','null'::json)) institution(v)
WHERE JSON_VALUE(author.v,'$.is_corresponding')::boolean=true AND JSON_VALUE(institution.v,'$.country_code')='US' AND JSON_VALUE(institution.v,'$.type')='education';

-- query: O-C3-3 | Business query
SELECT DISTINCT d.doc_id FROM {{table}} d
CROSS JOIN LATERAL json_array_elements(NULLIF(d.doc->'authorships','null'::jsonb)::json) author(v)
CROSS JOIN LATERAL json_array_elements(NULLIF(author.v->'institutions','null'::json)) institution(v)
WHERE JSON_VALUE(author.v,'$.author_position')='first' AND JSON_VALUE(institution.v,'$.country_code')='GB' AND JSON_VALUE(institution.v,'$.type')='healthcare';

-- query: O-C3-4 | Business query
SELECT DISTINCT d.doc_id FROM {{table}} d CROSS JOIN LATERAL json_array_elements(NULLIF(d.doc->'counts_by_year', 'null'::jsonb)::json) AS annual(v)
  WHERE (annual.v->>'year')::bigint >= 2020 AND (annual.v->>'year')::bigint <= 2024 AND (annual.v->>'cited_by_count')::bigint >= 20;

-- query: O-C4-1 | Business query
SELECT d.doc_id,json_object('id' VALUE any_value(d.doc->>'id'),'title' VALUE any_value(d.doc->>'title'),'publication_year' VALUE (any_value(d.doc->>'publication_year'))::bigint,'citations_2020_2024' VALUE sum((annual.v->>'cited_by_count')::bigint),'avg_recorded_year' VALUE avg((annual.v->>'cited_by_count')::bigint),'recorded_years' VALUE count(*)) FROM {{table}} d CROSS JOIN LATERAL json_array_elements(NULLIF(d.doc->'counts_by_year', 'null'::jsonb)::json) AS annual(v)
  WHERE (annual.v->>'year')::bigint >= 2020 AND (annual.v->>'year')::bigint <= 2024
   GROUP BY d.doc_id HAVING sum((annual.v->>'cited_by_count')::bigint) >= 50;

-- query: O-C4-2 | Business query
SELECT d.doc_id,json_object('id' VALUE any_value(d.doc->>'id'),'title' VALUE any_value(d.doc->>'title'),'citations_2020_2024' VALUE sum((annual.v->>'cited_by_count')::bigint),'avg_recorded_year' VALUE avg((annual.v->>'cited_by_count')::bigint)) FROM {{table}} d CROSS JOIN LATERAL json_array_elements(NULLIF(d.doc->'counts_by_year', 'null'::jsonb)::json) AS annual(v)
  WHERE (EXISTS (
  SELECT 1 FROM json_array_elements(NULLIF(d.doc->'authorships', 'null'::jsonb)::json) AS author(v)
  WHERE (author.v->>'is_corresponding')::boolean = true AND EXISTS (
    SELECT 1 FROM json_array_elements(NULLIF(author.v->'institutions', 'null'::json)::json) AS institution(v)
    WHERE institution.v->>'country_code' = 'US' AND institution.v->>'type' = 'education'))) AND ((annual.v->>'year')::bigint >= 2020 AND (annual.v->>'year')::bigint <= 2024)
 GROUP BY d.doc_id HAVING sum((annual.v->>'cited_by_count')::bigint) >= 1;

-- query: O-C4-3 | Business query
SELECT d.doc_id,json_object('work_id' VALUE any_value(d.doc->>'id'),'title' VALUE any_value(d.doc->>'title'),
'author_id' VALUE any_value(JSON_VALUE(author.v,'$.author.id')),'author_name' VALUE any_value(JSON_VALUE(author.v,'$.author.display_name')),'us_education_affiliations' VALUE count(*))
FROM {{table}} d CROSS JOIN LATERAL json_array_elements(NULLIF(d.doc->'authorships','null'::jsonb)::json) WITH ORDINALITY author(v,n)
CROSS JOIN LATERAL json_array_elements(NULLIF(author.v->'institutions','null'::json)) institution(v)
WHERE JSON_VALUE(author.v,'$.is_corresponding')::boolean=true AND JSON_VALUE(institution.v,'$.country_code')='US' AND JSON_VALUE(institution.v,'$.type')='education'
GROUP BY d.doc_id,author.n HAVING count(*)>=2;

-- query: O-C4-4 | Business query
SELECT d.doc_id,json_object('id' VALUE any_value(d.doc->>'id'),'title' VALUE any_value(d.doc->>'title'),'cited_by_count' VALUE (any_value(d.doc->>'cited_by_count'))::bigint,'reusable_published_locations' VALUE count(*)) FROM {{table}} d CROSS JOIN LATERAL json_array_elements(NULLIF(d.doc->'locations', 'null'::jsonb)::json) AS location(v)
  WHERE (location.v->>'is_oa')::boolean = true AND (location.v->>'is_published')::boolean = true
    AND location.v->>'license' = 'cc-by' AND location.v->'source'->>'type' = 'journal'
   GROUP BY d.doc_id HAVING count(*) >= 1;
