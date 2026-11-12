-- query: YB-C1-1 | Business query
SELECT d.doc_id FROM {{table}} d WHERE EXISTS (SELECT 1 WHERE (d.doc->>'is_open')::bigint = 1
  AND (d.doc->>'stars')::double precision >= '4'::double precision AND (d.doc->>'review_count')::bigint >= 100);

-- query: YB-C1-2 | Business query
SELECT d.doc_id FROM {{table}} d WHERE EXISTS (SELECT 1 WHERE d.doc->>'city' = 'Philadelphia' AND (d.doc->>'is_open')::bigint = 1
  AND (d.doc->>'stars')::double precision >= '4'::double precision);

-- query: YB-C1-3 | Business query
SELECT d.doc_id FROM {{table}} d WHERE EXISTS (SELECT 1 WHERE (d.doc->>'stars')::double precision >= '4'::double precision AND (d.doc->>'is_open')::bigint = 1
  AND d.doc#>>'{attributes,GoodForKids}' = 'True' AND d.doc#>>'{attributes,RestaurantsTakeOut}' = 'True');

-- query: YB-C1-4 | Business query
SELECT d.doc_id FROM {{table}} d WHERE EXISTS (SELECT 1 WHERE (d.doc->>'review_count')::bigint >= 50 AND (d.doc->>'is_open')::bigint = 1
  AND d.doc#>>'{attributes,RestaurantsDelivery}' = 'True'
  AND d.doc#>>'{attributes,BusinessAcceptsCreditCards}' = 'True');
