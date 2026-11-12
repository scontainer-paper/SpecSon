-- query: H-C1-1 | Business query
SELECT d.doc_id FROM {{table}} d WHERE EXISTS (SELECT 1 WHERE d.doc->>'orderstatus' = 'O' AND (d.doc->>'totalprice')::numeric >= 200000);

-- query: H-C1-2 | Business query
SELECT d.doc_id FROM {{table}} d WHERE EXISTS (SELECT 1 WHERE d.doc#>>'{customer,mktsegment}' = 'AUTOMOBILE'
  AND (d.doc#>>'{customer,acctbal}')::numeric < 0 AND (d.doc->>'totalprice')::numeric >= 100000);

-- query: H-C1-3 | Business query
SELECT d.doc_id FROM {{table}} d WHERE EXISTS (SELECT 1 WHERE d.doc->>'orderdate' >= '1995-01-01' AND d.doc->>'orderdate' < '1996-01-01'
  AND (d.doc->>'totalprice')::numeric >= 150000);

-- query: H-C1-4 | Business query
SELECT d.doc_id FROM {{table}} d WHERE EXISTS (SELECT 1 WHERE d.doc#>>'{customer,nation,region,name}' = 'EUROPE'
  AND d.doc->>'orderpriority' = '1-URGENT' AND (d.doc->>'totalprice')::numeric >= 100000);

-- query: H-C2-1 | Business query
SELECT d.doc_id FROM {{table}} d WHERE EXISTS (SELECT 1 WHERE EXISTS (
  SELECT 1 FROM jsonb_array_elements(NULLIF(d.doc->'lineitems', 'null'::jsonb)) AS item
  WHERE item->>'receiptdate' > item->>'commitdate'));

-- query: H-C2-2 | Business query
SELECT d.doc_id FROM {{table}} d WHERE EXISTS (SELECT 1 WHERE EXISTS (
  SELECT 1 FROM jsonb_array_elements(NULLIF(d.doc->'lineitems', 'null'::jsonb)) AS item
  WHERE item->>'returnflag' = 'R'));

-- query: H-C2-3 | Business query
SELECT d.doc_id FROM {{table}} d WHERE EXISTS (SELECT 1 WHERE (SELECT sum((item->>'quantity')::numeric)
  FROM jsonb_array_elements(NULLIF(d.doc->'lineitems', 'null'::jsonb)) AS item) >= 200);

-- query: H-C2-4 | Business query
SELECT d.doc_id FROM {{table}} d WHERE EXISTS (SELECT 1 WHERE (SELECT avg((item->>'quantity')::numeric)
  FROM jsonb_array_elements(NULLIF(d.doc->'lineitems', 'null'::jsonb)) AS item) >= 30);

-- query: H-C3-1 | Business query
SELECT d.doc_id FROM {{table}} d WHERE EXISTS (SELECT 1 WHERE EXISTS (
  SELECT 1 FROM jsonb_array_elements(NULLIF(d.doc->'lineitems', 'null'::jsonb)) AS item
  WHERE item->>'shipmode' = 'AIR' AND (item->>'quantity')::numeric >= 30));

-- query: H-C3-2 | Business query
SELECT d.doc_id FROM {{table}} d WHERE EXISTS (SELECT 1 WHERE EXISTS (
  SELECT 1 FROM jsonb_array_elements(NULLIF(d.doc->'lineitems', 'null'::jsonb)) AS item
  WHERE item#>>'{partsupp,supplier,nation,name}' = 'SAUDI ARABIA'
    AND item->>'receiptdate' > item->>'commitdate'));

-- query: H-C3-3 | Business query
SELECT d.doc_id FROM {{table}} d WHERE EXISTS (SELECT 1 WHERE EXISTS (
  SELECT 1 FROM jsonb_array_elements(NULLIF(d.doc->'lineitems', 'null'::jsonb)) AS item
  WHERE item#>>'{partsupp,part,brand}' = 'Brand#12'
    AND (item#>>'{partsupp,part,size}')::bigint >= 20 AND (item->>'quantity')::numeric <= 10));

-- query: H-C3-4 | Business query
SELECT d.doc_id FROM {{table}} d WHERE EXISTS (SELECT 1 WHERE EXISTS (
  SELECT 1 FROM jsonb_array_elements(NULLIF(d.doc->'lineitems', 'null'::jsonb)) AS item
  WHERE item->>'shipmode' = 'SHIP'
    AND item#>>'{partsupp,supplier,nation,name}' <> d.doc#>>'{customer,nation,name}'));

-- query: H-C4-1 | Business query
SELECT d.doc_id,q.* FROM {{table}} d CROSS JOIN LATERAL (SELECT jsonb_build_object('orderkey', (d.doc->>'orderkey')::bigint, 'priority', d.doc->>'orderpriority',
  'customer_country', d.doc#>>'{customer,nation,name}', 'shipmode', summary.mode,
  'late_lines', summary.lines, 'gross_value', summary.gross, 'avg_quantity', summary.quantity)
FROM LATERAL (
  SELECT item->>'shipmode' AS mode, count(*) AS lines,
    sum((item->>'extendedprice')::numeric) AS gross, avg((item->>'quantity')::numeric) AS quantity
  FROM jsonb_array_elements(NULLIF(d.doc->'lineitems', 'null'::jsonb)) AS item
  WHERE item->>'receiptdate' > item->>'commitdate' AND item->>'linestatus' = 'F'
  GROUP BY item->>'shipmode'
) AS summary) q;

-- query: H-C4-2 | Business query
SELECT d.doc_id,q.* FROM {{table}} d CROSS JOIN LATERAL (SELECT jsonb_build_object('orderkey', (d.doc->>'orderkey')::bigint, 'customer', d.doc#>>'{customer,name}',
  'supplier_country', summary.country, 'returned_lines', summary.lines,
  'gross_value', summary.gross, 'avg_discount', summary.discount)
FROM LATERAL (
  SELECT item#>>'{partsupp,supplier,nation,name}' AS country, count(*) AS lines,
    sum((item->>'extendedprice')::numeric) AS gross, avg((item->>'discount')::numeric) AS discount
  FROM jsonb_array_elements(NULLIF(d.doc->'lineitems', 'null'::jsonb)) AS item
  WHERE item->>'returnflag' = 'R' AND item->>'linestatus' = 'F'
  GROUP BY item#>>'{partsupp,supplier,nation,name}'
) AS summary WHERE d.doc->>'orderstatus' = 'F') q;

-- query: H-C4-3 | Business query
SELECT d.doc_id,q.* FROM {{table}} d CROSS JOIN LATERAL (SELECT jsonb_build_object('orderkey', (d.doc->>'orderkey')::bigint, 'orderdate', d.doc->>'orderdate',
  'customer_country', d.doc#>>'{customer,nation,name}', 'air_lines', summary.lines,
  'quantity', summary.quantity, 'gross_value', summary.gross)
FROM LATERAL (
  SELECT count(*) AS lines, sum((item->>'quantity')::numeric) AS quantity,
    sum((item->>'extendedprice')::numeric) AS gross
  FROM jsonb_array_elements(NULLIF(d.doc->'lineitems', 'null'::jsonb)) AS item
  WHERE item->>'shipmode' = 'AIR'
    AND item#>>'{partsupp,supplier,nation,name}' <> d.doc#>>'{customer,nation,name}'
  HAVING count(*) >= 1
) AS summary) q;

-- query: H-C4-4 | Business query
SELECT d.doc_id,q.* FROM {{table}} d CROSS JOIN LATERAL (SELECT jsonb_build_object('orderkey', (d.doc->>'orderkey')::bigint, 'priority', d.doc->>'orderpriority',
  'segment', d.doc#>>'{customer,mktsegment}', 'large_lines', summary.lines,
  'quantity', summary.quantity, 'gross_value', summary.gross, 'avg_quantity', summary.average)
FROM LATERAL (
  SELECT count(*) AS lines, sum((item->>'quantity')::numeric) AS quantity,
    sum((item->>'extendedprice')::numeric) AS gross, avg((item->>'quantity')::numeric) AS average
  FROM jsonb_array_elements(NULLIF(d.doc->'lineitems', 'null'::jsonb)) AS item
  WHERE (item#>>'{partsupp,part,size}')::bigint >= 20 AND (item->>'quantity')::numeric >= 30
  HAVING count(*) >= 1
) AS summary WHERE d.doc->>'orderpriority' = '1-URGENT' OR d.doc->>'orderpriority' = '2-HIGH') q;
