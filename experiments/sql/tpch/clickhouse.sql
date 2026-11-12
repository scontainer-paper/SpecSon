-- query: H-C1-1 | Business query
SELECT doc_id FROM {{table}} WHERE {{relational_filter}} AND doc.orderstatus='O' AND doc.totalprice>=200000 FORMAT JSONCompactEachRow;

-- query: H-C1-2 | Business query
SELECT doc_id FROM {{table}} WHERE {{relational_filter}} AND doc.customer.mktsegment='AUTOMOBILE' AND doc.customer.acctbal<0 AND doc.totalprice>=100000 FORMAT JSONCompactEachRow;

-- query: H-C1-3 | Business query
SELECT doc_id FROM {{table}} WHERE {{relational_filter}} AND doc.orderdate>='1995-01-01' AND doc.orderdate<'1996-01-01' AND doc.totalprice>=150000 FORMAT JSONCompactEachRow;

-- query: H-C1-4 | Business query
SELECT doc_id FROM {{table}} WHERE {{relational_filter}} AND doc.customer.nation.region.name='EUROPE' AND doc.orderpriority='1-URGENT' AND doc.totalprice>=100000 FORMAT JSONCompactEachRow;

-- query: H-C2-1 | Business query
SELECT doc_id FROM {{table}} WHERE {{relational_filter}} AND arrayExists((receipt,commit) -> receipt>commit,doc.lineitems.receiptdate,doc.lineitems.commitdate) FORMAT JSONCompactEachRow;

-- query: H-C2-2 | Business query
SELECT doc_id FROM {{table}} WHERE {{relational_filter}} AND arrayExists(flag -> flag='R',doc.lineitems.returnflag) FORMAT JSONCompactEachRow;

-- query: H-C2-3 | Business query
SELECT doc_id FROM {{table}} WHERE {{relational_filter}} AND arrayReduce('sumOrNull',doc.lineitems.quantity)>=200 FORMAT JSONCompactEachRow;

-- query: H-C2-4 | Business query
SELECT doc_id FROM {{table}} WHERE {{relational_filter}} AND arrayReduce('avgOrNull',doc.lineitems.quantity)>=30 FORMAT JSONCompactEachRow;

-- query: H-C3-1 | Business query
SELECT doc_id FROM {{table}} WHERE {{relational_filter}} AND arrayExists((mode,quantity) -> mode='AIR' AND quantity>=30,doc.lineitems.shipmode,doc.lineitems.quantity) FORMAT JSONCompactEachRow;

-- query: H-C3-2 | Business query
SELECT doc_id FROM {{table}} WHERE {{relational_filter}} AND arrayExists((nation,receipt,commit) -> nation='SAUDI ARABIA' AND receipt>commit,doc.lineitems.partsupp.supplier.nation.name,doc.lineitems.receiptdate,doc.lineitems.commitdate) FORMAT JSONCompactEachRow;

-- query: H-C3-3 | Business query
SELECT doc_id FROM {{table}} WHERE {{relational_filter}} AND arrayExists((brand,size,quantity) -> brand='Brand#12' AND size>=20 AND quantity<=10,doc.lineitems.partsupp.part.brand,doc.lineitems.partsupp.part.size,doc.lineitems.quantity) FORMAT JSONCompactEachRow;

-- query: H-C3-4 | Business query
SELECT doc_id FROM {{table}} WHERE {{relational_filter}} AND arrayExists((mode,nation) -> mode='SHIP' AND nation<>doc.customer.nation.name,doc.lineitems.shipmode,doc.lineitems.partsupp.supplier.nation.name) FORMAT JSONCompactEachRow;

-- query: H-C4-1 | Business query
SELECT doc_id,toJSONString(tuple(any(doc.orderkey) AS orderkey,any(doc.orderpriority) AS priority,any(doc.customer.nation.name) AS customer_country,item_5 AS shipmode,count() AS late_lines,sumOrNull(item_1) AS gross_value,avgOrNull(item_3) AS avg_quantity)) AS result FROM {{table}} ARRAY JOIN doc.lineitems.commitdate AS item_0,doc.lineitems.extendedprice AS item_1,doc.lineitems.linestatus AS item_2,doc.lineitems.quantity AS item_3,doc.lineitems.receiptdate AS item_4,doc.lineitems.shipmode AS item_5 WHERE {{relational_filter}} AND item_4>item_0 AND item_2='F' GROUP BY doc_id,item_5 FORMAT JSONCompactEachRow;

-- query: H-C4-2 | Business query
SELECT doc_id,toJSONString(tuple(any(doc.orderkey) AS orderkey,any(doc.customer.name) AS customer,item_3 AS supplier_country,count() AS returned_lines,sumOrNull(item_1) AS gross_value,avgOrNull(item_0) AS avg_discount)) AS result FROM {{table}} ARRAY JOIN doc.lineitems.discount AS item_0,doc.lineitems.extendedprice AS item_1,doc.lineitems.linestatus AS item_2,doc.lineitems.partsupp.supplier.nation.name AS item_3,doc.lineitems.returnflag AS item_4 WHERE {{relational_filter}} AND doc.orderstatus='F' AND item_4='R' AND item_2='F' GROUP BY doc_id,item_3 FORMAT JSONCompactEachRow;

-- query: H-C4-3 | Business query
WITH arrayFilter((item,mode,nation) -> mode='AIR' AND nation<>doc.customer.nation.name,arrayZip(doc.lineitems.quantity,doc.lineitems.extendedprice),doc.lineitems.shipmode,doc.lineitems.partsupp.supplier.nation.name) AS matched SELECT doc_id,toJSONString(tuple(doc.orderkey AS orderkey,doc.orderdate AS orderdate,doc.customer.nation.name AS customer_country,length(matched) AS air_lines,arrayReduce('sumOrNull',arrayMap(x -> x.1,matched)) AS quantity,arrayReduce('sumOrNull',arrayMap(x -> x.2,matched)) AS gross_value)) AS result FROM {{table}} WHERE {{relational_filter}} AND notEmpty(matched) FORMAT JSONCompactEachRow;

-- query: H-C4-4 | Business query
WITH arrayFilter((item,size) -> size>=20 AND item.1>=30,arrayZip(doc.lineitems.quantity,doc.lineitems.extendedprice),doc.lineitems.partsupp.part.size) AS matched SELECT doc_id,toJSONString(tuple(doc.orderkey AS orderkey,doc.orderpriority AS priority,doc.customer.mktsegment AS segment,length(matched) AS large_lines,arrayReduce('sumOrNull',arrayMap(x -> x.1,matched)) AS quantity,arrayReduce('sumOrNull',arrayMap(x -> x.2,matched)) AS gross_value,arrayReduce('avgOrNull',arrayMap(x -> x.1,matched)) AS avg_quantity)) AS result FROM {{table}} WHERE {{relational_filter}} AND notEmpty(matched) AND (doc.orderpriority='1-URGENT' OR doc.orderpriority='2-HIGH') FORMAT JSONCompactEachRow;
