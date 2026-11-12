-- query: O-C1-1 | Business query
SELECT doc_id FROM {{table}} PREWHERE {{relational_filter}} AND doc.publication_year >= 2020 AND doc.cited_by_count >= 50 FORMAT JSONCompactEachRow;

-- query: O-C1-2 | Business query
SELECT doc_id FROM {{table}} PREWHERE {{relational_filter}} AND doc.type = 'article' AND doc.publication_year >= 2020 AND doc.is_retracted = false FORMAT JSONCompactEachRow;

-- query: O-C1-3 | Business query
SELECT doc_id FROM {{table}} PREWHERE {{relational_filter}} AND doc.authors_count >= 10 AND doc.countries_distinct_count >= 3 FORMAT JSONCompactEachRow;

-- query: O-C1-4 | Business query
SELECT doc_id FROM {{table}} PREWHERE {{relational_filter}} AND doc.cited_by_count >= 20 WHERE doc.open_access.oa_status = 'gold' AND doc.cited_by_count >= 20 FORMAT JSONCompactEachRow;

-- query: O-C2-1 | Business query
SELECT doc_id FROM {{table}} PREWHERE {{relational_filter}} AND arrayExists(x -> x = 'pubmed',doc.indexed_in) FORMAT JSONCompactEachRow;

-- query: O-C2-2 | Business query
SELECT doc_id FROM {{table}} PREWHERE {{relational_filter}} AND arrayExists(x -> x >= 20,doc.counts_by_year.cited_by_count) FORMAT JSONCompactEachRow;

-- query: O-C2-3 | Business query
SELECT doc_id FROM {{table}} PREWHERE {{relational_filter}} AND arrayReduce('sumOrNull',doc.counts_by_year.cited_by_count) >= 100 FORMAT JSONCompactEachRow;

-- query: O-C2-4 | Business query
SELECT doc_id FROM {{table}} PREWHERE {{relational_filter}} AND arrayReduce('avgOrNull',doc.counts_by_year.cited_by_count) >= 10 FORMAT JSONCompactEachRow;

-- query: O-C3-1 | Business query
SELECT doc_id FROM {{table}} PREWHERE {{relational_filter}} AND arrayExists((oa,pub) -> oa=true AND pub=true,doc.locations.is_oa,doc.locations.is_published) WHERE arrayExists((oa,published,kind) -> oa = true AND published = true AND CAST(kind,'Nullable(String)') = 'journal',doc.locations.is_oa,doc.locations.is_published,doc.locations.source.type) FORMAT JSONCompactEachRow;

-- query: O-C3-2 | Business query
SELECT doc_id FROM {{table}} PREWHERE {{relational_filter}} AND arrayExists((corresponding,countries,kinds) -> corresponding = true AND arrayExists((country,kind) -> country = 'US' AND kind = 'education',countries,kinds),doc.authorships.is_corresponding,doc.authorships.institutions.country_code,doc.authorships.institutions.type) FORMAT JSONCompactEachRow;

-- query: O-C3-3 | Business query
SELECT doc_id FROM {{table}} PREWHERE {{relational_filter}} AND arrayExists((position,countries,kinds) -> position = 'first' AND arrayExists((country,kind) -> country = 'GB' AND kind = 'healthcare',countries,kinds),doc.authorships.author_position,doc.authorships.institutions.country_code,doc.authorships.institutions.type) FORMAT JSONCompactEachRow;

-- query: O-C3-4 | Business query
SELECT doc_id FROM {{table}} PREWHERE {{relational_filter}} AND arrayExists((year,citations) -> year >= 2020 AND year <= 2024 AND citations >= 20,doc.counts_by_year.year,doc.counts_by_year.cited_by_count) FORMAT JSONCompactEachRow;

-- query: O-C4-1 | Business query
WITH arrayFilter((citations,year) -> year >= 2020 AND year <= 2024,doc.counts_by_year.cited_by_count,doc.counts_by_year.year) AS selected,
arrayReduce('sumOrNull',selected) AS total
SELECT doc_id,toJSONString(tuple(doc.id AS id,doc.title AS title,doc.publication_year AS publication_year,total AS citations_2020_2024,arrayReduce('avgOrNull',selected) AS avg_recorded_year,length(selected) AS recorded_years))
FROM {{table}} PREWHERE {{relational_filter}} AND total >= 50 FORMAT JSONCompactEachRow;

-- query: O-C4-2 | Business query
WITH arrayFilter((citations,year) -> year >= 2020 AND year <= 2024,doc.counts_by_year.cited_by_count,doc.counts_by_year.year) AS selected,
arrayReduce('sumOrNull',selected) AS total
SELECT doc_id,toJSONString(tuple(doc.id AS id,doc.title AS title,total AS citations_2020_2024,arrayReduce('avgOrNull',selected) AS avg_recorded_year))
FROM {{table}} PREWHERE {{relational_filter}} AND total >= 1 AND arrayExists((corresponding,countries,kinds) -> corresponding = true AND arrayExists((country,kind) -> country = 'US' AND kind = 'education',countries,kinds),doc.authorships.is_corresponding,doc.authorships.institutions.country_code,doc.authorships.institutions.type) FORMAT JSONCompactEachRow;

-- query: O-C4-3 | Business query
WITH arrayMap((corresponding,author_id,author_name,countries,kinds) -> tuple(corresponding,CAST(author_id,'Nullable(String)'),CAST(author_name,'Nullable(String)'),arrayCount((country,kind) -> country = 'US' AND kind = 'education',countries,kinds)),doc.authorships.is_corresponding,doc.authorships.author.id,doc.authorships.author.display_name,doc.authorships.institutions.country_code,doc.authorships.institutions.type) AS authors
SELECT doc_id,toJSONString(tuple(doc.id AS work_id,doc.title AS title,author.2 AS author_id,author.3 AS author_name,author.4 AS us_education_affiliations))
FROM {{table}} ARRAY JOIN arrayFilter(a -> a.1 = true AND a.4 >= 2,authors) AS author WHERE {{relational_filter}} FORMAT JSONCompactEachRow;

-- query: O-C4-4 | Business query
WITH arrayCount((oa,published,license,kind) -> oa = true AND published = true AND license = 'cc-by' AND CAST(kind,'Nullable(String)') = 'journal',doc.locations.is_oa,doc.locations.is_published,doc.locations.license,doc.locations.source.type) AS matched
SELECT doc_id,toJSONString(tuple(doc.id AS id,doc.title AS title,doc.cited_by_count AS cited_by_count,matched AS reusable_published_locations))
FROM {{table}} PREWHERE {{relational_filter}} AND arrayExists((oa,pub) -> oa=true AND pub=true,doc.locations.is_oa,doc.locations.is_published) WHERE matched >= 1 FORMAT JSONCompactEachRow;
