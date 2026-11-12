-- query: H-C1-1 | Business query
SELECT d.doc_id
FROM {{table}} d
WHERE EXISTS (SELECT 1
WHERE d.doc->>'orderstatus' = 'O' AND (d.doc->>'totalprice')::numeric(18,2) >= 200000);

-- query: H-C1-2 | Business query
SELECT d.doc_id
FROM {{table}} d
WHERE EXISTS (SELECT 1
WHERE d.doc->'customer'->>'mktsegment' = 'AUTOMOBILE'
  AND (d.doc->'customer'->>'acctbal')::numeric(18,2) < 0 AND (d.doc->>'totalprice')::numeric(18,2) >= 100000);

-- query: H-C1-3 | Business query
SELECT d.doc_id
FROM {{table}} d
WHERE EXISTS (SELECT 1
WHERE d.doc->>'orderdate' >= '1995-01-01' AND d.doc->>'orderdate' < '1996-01-01'
  AND (d.doc->>'totalprice')::numeric(18,2) >= 150000);

-- query: H-C1-4 | Business query
SELECT d.doc_id
FROM {{table}} d
WHERE EXISTS (SELECT 1
WHERE d.doc->'customer'->'nation'->'region'->>'name' = 'EUROPE'
  AND d.doc->>'orderpriority' = '1-URGENT' AND (d.doc->>'totalprice')::numeric(18,2) >= 100000);

-- query: H-C2-1 | Business query
SELECT d.doc_id
FROM {{table}} d
WHERE JSON_EXISTS((d.doc->'lineitems')::json, '$[*] ? (@.receiptdate > @.commitdate)');

-- query: H-C2-2 | Business query
SELECT DISTINCT d.doc_id
FROM {{table}} d CROSS JOIN LATERAL json_array_elements(NULLIF(d.doc->'lineitems', 'null'::jsonb)::json) AS item(v)

WHERE item.v->>'returnflag' = 'R';

-- query: H-C2-3 | Business query
SELECT d.doc_id
FROM {{table}} d CROSS JOIN LATERAL json_array_elements(NULLIF(d.doc->'lineitems', 'null'::jsonb)::json) AS item(v)
GROUP BY d.doc_id
HAVING sum((item.v->>'quantity')::numeric(18,2))>=200;

-- query: H-C2-4 | Business query
SELECT d.doc_id
FROM {{table}} d CROSS JOIN LATERAL json_array_elements(NULLIF(d.doc->'lineitems', 'null'::jsonb)::json) AS item(v)
GROUP BY d.doc_id
HAVING avg((item.v->>'quantity')::numeric(18,2))>=30;

-- query: H-C3-1 | Business query
SELECT DISTINCT d.doc_id
FROM {{table}} d CROSS JOIN LATERAL json_array_elements(NULLIF(d.doc->'lineitems', 'null'::jsonb)::json) AS item(v)

WHERE item.v->>'shipmode' = 'AIR' AND (item.v->>'quantity')::numeric(18,2) >= 30;

-- query: H-C3-2 | Business query
SELECT DISTINCT d.doc_id
FROM {{table}} d CROSS JOIN LATERAL json_array_elements(NULLIF(d.doc->'lineitems', 'null'::jsonb)::json) AS item(v)

WHERE item.v->'partsupp'->'supplier'->'nation'->>'name' = 'SAUDI ARABIA'
    AND item.v->>'receiptdate' > item.v->>'commitdate';

-- query: H-C3-3 | Business query
SELECT DISTINCT d.doc_id
FROM {{table}} d CROSS JOIN LATERAL json_array_elements(NULLIF(d.doc->'lineitems', 'null'::jsonb)::json) AS item(v)

WHERE item.v->'partsupp'->'part'->>'brand' = 'Brand#12'
    AND (item.v->'partsupp'->'part'->>'size')::bigint >= 20 AND (item.v->>'quantity')::numeric(18,2) <= 10;

-- query: H-C3-4 | Business query
SELECT DISTINCT d.doc_id
FROM {{table}} d CROSS JOIN LATERAL json_array_elements(NULLIF(d.doc->'lineitems', 'null'::jsonb)::json) AS item(v)

WHERE item.v->>'shipmode' = 'SHIP'
    AND item.v->'partsupp'->'supplier'->'nation'->>'name' <> d.doc->'customer'->'nation'->>'name';

-- query: H-C4-1 | Business query
SELECT d.doc_id,json_object('orderkey' VALUE any_value((d.doc->>'orderkey')::bigint),'priority' VALUE any_value(d.doc->>'orderpriority'),'customer_country' VALUE any_value(d.doc->'customer'->'nation'->>'name'),'shipmode' VALUE item.v->>'shipmode','late_lines' VALUE count(*),'gross_value' VALUE sum((item.v->>'extendedprice')::numeric(18,2)),'avg_quantity' VALUE avg((item.v->>'quantity')::numeric(18,2)))
FROM {{table}} d CROSS JOIN LATERAL json_array_elements(NULLIF(d.doc->'lineitems', 'null'::jsonb)::json) AS item(v)
WHERE item.v->>'receiptdate'>item.v->>'commitdate' AND item.v->>'linestatus'='F'
GROUP BY d.doc_id,item.v->>'shipmode';

-- query: H-C4-2 | Business query
SELECT d.doc_id,json_object('orderkey' VALUE any_value((d.doc->>'orderkey')::bigint),'customer' VALUE any_value(d.doc->'customer'->>'name'),'supplier_country' VALUE item.v->'partsupp'->'supplier'->'nation'->>'name','returned_lines' VALUE count(*),'gross_value' VALUE sum((item.v->>'extendedprice')::numeric(18,2)),'avg_discount' VALUE avg((item.v->>'discount')::numeric(18,2)))
FROM {{table}} d CROSS JOIN LATERAL json_array_elements(NULLIF(d.doc->'lineitems', 'null'::jsonb)::json) AS item(v)
WHERE d.doc->>'orderstatus'='F' AND item.v->>'returnflag'='R' AND item.v->>'linestatus'='F'
GROUP BY d.doc_id,item.v->'partsupp'->'supplier'->'nation'->>'name';

-- query: H-C4-3 | Business query
SELECT d.doc_id,json_object('orderkey' VALUE any_value((d.doc->>'orderkey')::bigint),'orderdate' VALUE any_value(d.doc->>'orderdate'),'customer_country' VALUE any_value(d.doc->'customer'->'nation'->>'name'),'air_lines' VALUE count(*),'quantity' VALUE sum((item.v->>'quantity')::numeric(18,2)),'gross_value' VALUE sum((item.v->>'extendedprice')::numeric(18,2)))
FROM {{table}} d CROSS JOIN LATERAL json_array_elements(NULLIF(d.doc->'lineitems', 'null'::jsonb)::json) AS item(v)
WHERE item.v->>'shipmode'='AIR' AND item.v->'partsupp'->'supplier'->'nation'->>'name'<>d.doc->'customer'->'nation'->>'name'
GROUP BY d.doc_id;

-- query: H-C4-4 | Business query
SELECT d.doc_id,json_object('orderkey' VALUE any_value((d.doc->>'orderkey')::bigint),'priority' VALUE any_value(d.doc->>'orderpriority'),'segment' VALUE any_value(d.doc->'customer'->>'mktsegment'),'large_lines' VALUE count(*),'quantity' VALUE sum((item.v->>'quantity')::numeric(18,2)),'gross_value' VALUE sum((item.v->>'extendedprice')::numeric(18,2)),'avg_quantity' VALUE avg((item.v->>'quantity')::numeric(18,2)))
FROM {{table}} d CROSS JOIN LATERAL json_array_elements(NULLIF(d.doc->'lineitems', 'null'::jsonb)::json) AS item(v)
WHERE (d.doc->>'orderpriority'='1-URGENT' OR d.doc->>'orderpriority'='2-HIGH') AND (item.v->'partsupp'->'part'->>'size')::bigint>=20 AND (item.v->>'quantity')::numeric(18,2)>=30
GROUP BY d.doc_id;
