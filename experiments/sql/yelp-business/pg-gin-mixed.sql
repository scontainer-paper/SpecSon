-- query: YB-C1-1 | Mixed table GIN query
SELECT d.doc_id FROM (SELECT * FROM {{table}} WHERE doc @? '$ ? (@.is_open == 1 && @.stars >= 4 && @.review_count >= 100)'::jsonpath) d WHERE EXISTS (SELECT 1 WHERE (d.doc->>'is_open')::bigint = 1
  AND (d.doc->>'stars')::double precision >= '4'::double precision AND (d.doc->>'review_count')::bigint >= 100);

-- query: YB-C1-2 | Mixed table GIN query
SELECT d.doc_id FROM {{table}} d WHERE d.doc @? '$ ? (@.city == "Philadelphia" && @.is_open == 1 && @.stars >= 4)'::jsonpath;

-- query: YB-C1-3 | Mixed table GIN query
SELECT d.doc_id FROM {{table}} d WHERE d.doc @? '$ ? (@.stars >= 4 && @.is_open == 1 && @.attributes.GoodForKids == "True" && @.attributes.RestaurantsTakeOut == "True")'::jsonpath;

-- query: YB-C1-4 | Mixed table GIN query
SELECT d.doc_id FROM {{table}} d WHERE d.doc @? '$ ? (@.review_count >= 50 && @.is_open == 1 && @.attributes.RestaurantsDelivery == "True" && @.attributes.BusinessAcceptsCreditCards == "True")'::jsonpath;
