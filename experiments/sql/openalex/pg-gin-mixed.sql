-- query: O-C1-1 | Mixed table GIN query
SELECT d.doc_id FROM {{table}} d WHERE (d.doc @? '$ ? (@.publication_year >= 2020 && @.cited_by_count >= 50)'::jsonpath);

-- query: O-C1-2 | Mixed table GIN query
SELECT d.doc_id FROM {{table}} d WHERE (d.doc @? '$ ? (@.type == "article" && @.publication_year >= 2020 && @.is_retracted == false)'::jsonpath);

-- query: O-C1-3 | Mixed table GIN query
SELECT d.doc_id FROM {{table}} d WHERE (d.doc @? '$ ? (@.authors_count >= 10 && @.countries_distinct_count >= 3)'::jsonpath);

-- query: O-C1-4 | Mixed table GIN query
SELECT d.doc_id FROM {{table}} d WHERE d.doc @? '$ ? (@.open_access.oa_status == "gold" && @.cited_by_count >= 20)'::jsonpath;

-- query: O-C2-1 | Mixed table GIN query
SELECT d.doc_id FROM {{table}} d WHERE d.doc @? '$.indexed_in[*] ? (@ == "pubmed")'::jsonpath;

-- query: O-C2-2 | Mixed table GIN query
SELECT d.doc_id FROM {{table}} d WHERE (d.doc @? '$.counts_by_year[*] ? (@.cited_by_count >= 20)'::jsonpath);

-- query: O-C2-3 | Mixed table GIN query
SELECT d.doc_id
FROM (SELECT * FROM {{table}} WHERE doc ? 'counts_by_year') d CROSS JOIN LATERAL
 jsonb_array_elements(NULLIF(d.doc->'counts_by_year', 'null'::jsonb)) AS annual
GROUP BY d.doc_id HAVING sum((annual->>'cited_by_count')::bigint) >= 100;

-- query: O-C2-4 | Mixed table GIN query
SELECT d.doc_id
FROM (SELECT * FROM {{table}} WHERE doc ? 'counts_by_year') d CROSS JOIN LATERAL
 jsonb_array_elements(NULLIF(d.doc->'counts_by_year', 'null'::jsonb)) AS annual
GROUP BY d.doc_id HAVING avg((annual->>'cited_by_count')::bigint) >= 10;

-- query: O-C3-1 | Mixed table GIN query
SELECT d.doc_id FROM {{table}} d WHERE d.doc @? '$.locations[*] ? (@.is_oa == true && @.is_published == true && @.source.type == "journal")'::jsonpath;

-- query: O-C3-2 | Mixed table GIN query
SELECT d.doc_id FROM {{table}} d WHERE (d.doc @? '$.authorships[*] ? (@.is_corresponding == true && exists(@.institutions[*] ? (@.country_code == "US" && @.type == "education")))'::jsonpath);

-- query: O-C3-3 | Mixed table GIN query
SELECT d.doc_id FROM {{table}} d WHERE (d.doc @? '$.authorships[*] ? (@.author_position == "first" && exists(@.institutions[*] ? (@.country_code == "GB" && @.type == "healthcare")))'::jsonpath);

-- query: O-C3-4 | Mixed table GIN query
SELECT DISTINCT d.doc_id
FROM (SELECT * FROM {{table}} WHERE doc ? 'counts_by_year') d CROSS JOIN LATERAL
 jsonb_array_elements(NULLIF(d.doc->'counts_by_year', 'null'::jsonb)) AS annual
WHERE (annual->>'year')::bigint >= 2020 AND (annual->>'year')::bigint <= 2024
 AND (annual->>'cited_by_count')::bigint >= 20;

-- query: O-C4-1 | Mixed table GIN query
SELECT d.doc_id,q.* FROM (SELECT * FROM {{table}} WHERE doc ? 'counts_by_year') d CROSS JOIN LATERAL (SELECT jsonb_build_object('id', d.doc->>'id', 'title', d.doc->>'title', 'publication_year', (d.doc->>'publication_year')::bigint,
  'citations_2020_2024', summary.total, 'avg_recorded_year', summary.average, 'recorded_years', summary.years)
FROM LATERAL (
  SELECT sum((annual->>'cited_by_count')::bigint) AS total, avg((annual->>'cited_by_count')::bigint) AS average, count(*) AS years
  FROM jsonb_array_elements(NULLIF(d.doc->'counts_by_year', 'null'::jsonb)) AS annual
  WHERE (annual->>'year')::bigint >= 2020 AND (annual->>'year')::bigint <= 2024
  HAVING sum((annual->>'cited_by_count')::bigint) >= 50
) AS summary) q;

-- query: O-C4-2 | Mixed table GIN query
SELECT d.doc_id,q.* FROM (SELECT * FROM {{table}} WHERE doc @? '$.authorships[*] ? (@.is_corresponding == true && exists(@.institutions[*] ? (@.country_code == "US" && @.type == "education")))'::jsonpath) d CROSS JOIN LATERAL (SELECT jsonb_build_object('id', d.doc->>'id', 'title', d.doc->>'title', 'citations_2020_2024', summary.total, 'avg_recorded_year', summary.average)
FROM LATERAL (
  SELECT sum(annual.f0) AS total, avg(annual.f0) AS average
  FROM JSON_TABLE(d.doc->'counts_by_year', '$[*]' COLUMNS (f0 bigint PATH '$.cited_by_count' NULL ON EMPTY ERROR ON ERROR, f1 bigint PATH '$.year' NULL ON EMPTY ERROR ON ERROR)) AS annual
  WHERE annual.f1 >= 2020 AND annual.f1 <= 2024
  HAVING sum(annual.f0) >= 1
) AS summary WHERE (d.doc @? '$.authorships[*] ? (@.is_corresponding == true && exists(@.institutions[*] ? (@.country_code == "US" && @.type == "education")))'::jsonpath)) q;

-- query: O-C4-3 | Mixed table GIN query
SELECT d.doc_id,q.* FROM (SELECT * FROM {{table}} WHERE doc @? '$.authorships[*] ? (@.is_corresponding == true && exists(@.institutions[*] ? (@.country_code == "US" && @.type == "education")))'::jsonpath) d CROSS JOIN LATERAL (SELECT jsonb_build_object('work_id', d.doc->>'id', 'title', d.doc->>'title', 'author_id', author#>>'{author,id}',
  'author_name', author#>>'{author,display_name}', 'us_education_affiliations', summary.institutions)
FROM jsonb_path_query(d.doc, '$.authorships[*] ? (@.is_corresponding == true)') AS author,
LATERAL (
  SELECT count(*) AS institutions FROM jsonb_array_elements(NULLIF(author->'institutions', 'null'::jsonb)) AS institution
  WHERE institution->>'country_code' = 'US' AND institution->>'type' = 'education'
  HAVING count(*) >= 2
) AS summary) q;

-- query: O-C4-4 | Mixed table GIN query
SELECT d.doc_id,q.* FROM (SELECT * FROM {{table}} WHERE doc @? '$.locations[*] ? (@.is_oa == true && @.is_published == true && @.license == "cc-by" && @.source.type == "journal")'::jsonpath) d CROSS JOIN LATERAL (SELECT jsonb_build_object('id', d.doc->>'id', 'title', d.doc->>'title', 'cited_by_count', (d.doc->>'cited_by_count')::bigint,
  'reusable_published_locations', summary.locations)
FROM LATERAL (
  SELECT count(*) AS locations FROM jsonb_array_elements(NULLIF(d.doc->'locations', 'null'::jsonb)) AS location
  WHERE (location->>'is_oa')::boolean = true AND (location->>'is_published')::boolean = true
    AND location->>'license' = 'cc-by' AND location#>>'{source,type}' = 'journal'
  HAVING count(*) >= 1
) AS summary) q;
