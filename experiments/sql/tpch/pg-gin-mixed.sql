-- query: H-C1-1 | Mixed table GIN query
SELECT d.doc_id FROM {{table}} d WHERE (d.doc @? '$ ? (@.orderstatus == "O" && @.totalprice >= 200000)'::jsonpath);

-- query: H-C1-2 | Mixed table GIN query
SELECT d.doc_id FROM {{table}} d WHERE (d.doc @? '$ ? (@.customer.mktsegment == "AUTOMOBILE" && @.customer.acctbal < 0 && @.totalprice >= 100000)'::jsonpath);

-- query: H-C1-3 | Mixed table GIN query
SELECT d.doc_id FROM {{table}} d WHERE (d.doc @? '$ ? (@.orderdate >= "1995-01-01" && @.orderdate < "1996-01-01" && @.totalprice >= 150000)'::jsonpath);

-- query: H-C1-4 | Mixed table GIN query
SELECT d.doc_id FROM {{table}} d WHERE (d.doc @? '$ ? (@.customer.nation.region.name == "EUROPE" && @.orderpriority == "1-URGENT" && @.totalprice >= 100000)'::jsonpath);

-- query: H-C2-1 | Mixed table GIN query
SELECT d.doc_id FROM {{table}} d WHERE (d.doc @? '$.lineitems[*] ? (@.receiptdate > @.commitdate)'::jsonpath);

-- query: H-C2-2 | Mixed table GIN query
SELECT d.doc_id FROM {{table}} d WHERE (d.doc @? '$.lineitems[*] ? (@.returnflag == "R")'::jsonpath);

-- query: H-C2-3 | Mixed table GIN query
SELECT d.doc_id
FROM (SELECT * FROM {{table}} WHERE doc ? 'lineitems') d CROSS JOIN LATERAL
 jsonb_array_elements(NULLIF(d.doc->'lineitems', 'null'::jsonb)) AS item
GROUP BY d.doc_id
HAVING sum((item->>'quantity')::numeric) >= 200;

-- query: H-C2-4 | Mixed table GIN query
SELECT d.doc_id
FROM (SELECT * FROM {{table}} WHERE doc ? 'lineitems') d CROSS JOIN LATERAL
 jsonb_array_elements(NULLIF(d.doc->'lineitems', 'null'::jsonb)) AS item
GROUP BY d.doc_id
HAVING avg((item->>'quantity')::numeric) >= 30;

-- query: H-C3-1 | Mixed table GIN query
SELECT d.doc_id FROM {{table}} d WHERE (d.doc @? '$.lineitems[*] ? (@.shipmode == "AIR" && @.quantity >= 30)'::jsonpath);

-- query: H-C3-2 | Mixed table GIN query
SELECT d.doc_id FROM {{table}} d WHERE (d.doc @? '$.lineitems[*] ? (@.partsupp.supplier.nation.name == "SAUDI ARABIA" && @.receiptdate > @.commitdate)'::jsonpath);

-- query: H-C3-3 | Mixed table GIN query
SELECT d.doc_id FROM {{table}} d WHERE (d.doc @? '$.lineitems[*] ? (@.partsupp.part.brand == "Brand#12" && @.partsupp.part.size >= 20 && @.quantity <= 10)'::jsonpath);

-- query: H-C3-4 | Mixed table GIN query
SELECT d.doc_id FROM {{table}} d WHERE (d.doc @? '$.lineitems[*] ? (@.shipmode == "SHIP" && @.partsupp.supplier.nation.name != $.customer.nation.name && @.partsupp.supplier.nation.name != null && $.customer.nation.name != null)'::jsonpath);

-- query: H-C4-1 | Mixed table GIN query
SELECT d.doc_id, jsonb_build_object(
 'orderkey', (d.doc->>'orderkey')::bigint,
 'priority', d.doc->>'orderpriority',
 'customer_country', d.doc#>>'{customer,nation,name}',
 'shipmode', item->>'shipmode', 'late_lines', count(*),
 'gross_value', sum((item->>'extendedprice')::numeric),
 'avg_quantity', avg((item->>'quantity')::numeric))
FROM (SELECT * FROM (SELECT * FROM {{table}} WHERE doc @? '$.lineitems[*] ? (@.linestatus == "F")'::jsonpath) WHERE doc ? 'lineitems') d CROSS JOIN LATERAL
 jsonb_array_elements(NULLIF(d.doc->'lineitems', 'null'::jsonb)) AS item
WHERE item->>'receiptdate' > item->>'commitdate' AND item->>'linestatus' = 'F'
GROUP BY d.doc_id, (d.doc->>'orderkey')::bigint, d.doc->>'orderpriority',
 d.doc#>>'{customer,nation,name}', item->>'shipmode';

-- query: H-C4-2 | Mixed table GIN query
SELECT d.doc_id,q.* FROM (SELECT * FROM {{table}} WHERE doc @? '$ ? (@.orderstatus == "F" && exists(@.lineitems[*] ? (@.returnflag == "R" && @.linestatus == "F")))'::jsonpath) d CROSS JOIN LATERAL (
SELECT jsonb_build_object('orderkey', (d.doc->>'orderkey')::bigint, 'customer', d.doc#>>'{customer,name}',
  'supplier_country', summary.country, 'returned_lines', summary.lines,
  'gross_value', summary.gross, 'avg_discount', summary.discount)
FROM LATERAL (
  SELECT item#>>'{partsupp,supplier,nation,name}' AS country, count(*) AS lines,
    sum((item->>'extendedprice')::numeric) AS gross, avg((item->>'discount')::numeric) AS discount
  FROM jsonb_array_elements(NULLIF(d.doc->'lineitems', 'null'::jsonb)) AS item
  WHERE item->>'returnflag' = 'R' AND item->>'linestatus' = 'F'
  GROUP BY item#>>'{partsupp,supplier,nation,name}'
) AS summary WHERE d.doc->>'orderstatus' = 'F'
) q;

-- query: H-C4-3 | Mixed table GIN query
SELECT d.doc_id,q.* FROM (SELECT * FROM {{table}} WHERE doc @? '$.lineitems[*] ? (@.shipmode == "AIR")'::jsonpath) d CROSS JOIN LATERAL (
SELECT jsonb_build_object('orderkey', (d.doc->>'orderkey')::bigint, 'orderdate', d.doc->>'orderdate',
  'customer_country', d.doc#>>'{customer,nation,name}', 'air_lines', summary.lines,
  'quantity', summary.quantity, 'gross_value', summary.gross)
FROM LATERAL (
  SELECT count(*) AS lines, sum((item->>'quantity')::numeric) AS quantity,
    sum((item->>'extendedprice')::numeric) AS gross
  FROM jsonb_array_elements(NULLIF(d.doc->'lineitems', 'null'::jsonb)) AS item
  WHERE item->>'shipmode' = 'AIR'
    AND item#>>'{partsupp,supplier,nation,name}' <> d.doc#>>'{customer,nation,name}'
  HAVING count(*) >= 1
) AS summary
) q;

-- query: H-C4-4 | Mixed table GIN query
SELECT d.doc_id,q.* FROM (SELECT * FROM {{table}} WHERE doc @? '$ ? (@.orderpriority == "1-URGENT" || @.orderpriority == "2-HIGH")'::jsonpath) d CROSS JOIN LATERAL (
SELECT jsonb_build_object('orderkey', (d.doc->>'orderkey')::bigint, 'priority', d.doc->>'orderpriority',
  'segment', d.doc#>>'{customer,mktsegment}', 'large_lines', summary.lines,
  'quantity', summary.quantity, 'gross_value', summary.gross, 'avg_quantity', summary.average)
FROM LATERAL (
  SELECT count(*) AS lines, sum((item->>'quantity')::numeric) AS quantity,
    sum((item->>'extendedprice')::numeric) AS gross, avg((item->>'quantity')::numeric) AS average
  FROM jsonb_array_elements(NULLIF(d.doc->'lineitems', 'null'::jsonb)) AS item
  WHERE (item#>>'{partsupp,part,size}')::bigint >= 20 AND (item->>'quantity')::numeric >= 30
  HAVING count(*) >= 1
) AS summary WHERE d.doc->>'orderpriority' = '1-URGENT' OR d.doc->>'orderpriority' = '2-HIGH'
) q;
