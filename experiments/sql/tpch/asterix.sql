-- query: H-C1-1 | Business query
SELECT VALUE d.doc_id FROM {{table}} d WHERE ((d.`doc`.`orderstatus` = "O") AND (d.`doc`.`totalprice` >= 200000));

-- query: H-C1-2 | Business query
SELECT VALUE d.doc_id FROM {{table}} d WHERE ((d.`doc`.`customer`.`mktsegment` = "AUTOMOBILE") AND (d.`doc`.`customer`.`acctbal` < 0) AND (d.`doc`.`totalprice` >= 100000));

-- query: H-C1-3 | Business query
SELECT VALUE d.doc_id FROM {{table}} d WHERE ((d.`doc`.`orderdate` >= "1995-01-01") AND (d.`doc`.`orderdate` < "1996-01-01") AND (d.`doc`.`totalprice` >= 150000));

-- query: H-C1-4 | Business query
SELECT VALUE d.doc_id FROM {{table}} d WHERE ((d.`doc`.`customer`.`nation`.`region`.`name` = "EUROPE") AND (d.`doc`.`orderpriority` = "1-URGENT") AND (d.`doc`.`totalprice` >= 100000));

-- query: H-C2-1 | Business query
SELECT DISTINCT VALUE d.doc_id FROM {{table}} d UNNEST d.`doc`.`lineitems` a WHERE (a.`receiptdate` > a.`commitdate`);

-- query: H-C2-2 | Business query
SELECT DISTINCT VALUE d.doc_id FROM {{table}} d UNNEST d.`doc`.`lineitems` a WHERE (a.`returnflag` = "R");

-- query: H-C2-3 | Business query
SELECT VALUE d.doc_id FROM {{table}} d WHERE (array_sum((SELECT VALUE a.`quantity` FROM if_missing_or_null(d.`doc`.`lineitems`,[]) a WHERE true)) >= 200);

-- query: H-C2-4 | Business query
SELECT VALUE d.doc_id FROM {{table}} d WHERE (array_avg((SELECT VALUE a.`quantity` FROM if_missing_or_null(d.`doc`.`lineitems`,[]) a WHERE true)) >= 30);

-- query: H-C3-1 | Business query
SELECT DISTINCT VALUE d.doc_id FROM {{table}} d UNNEST d.`doc`.`lineitems` a WHERE ((a.`shipmode` = "AIR") AND (a.`quantity` >= 30));

-- query: H-C3-2 | Business query
SELECT DISTINCT VALUE d.doc_id FROM {{table}} d UNNEST d.`doc`.`lineitems` a WHERE ((a.`partsupp`.`supplier`.`nation`.`name` = "SAUDI ARABIA") AND (a.`receiptdate` > a.`commitdate`));

-- query: H-C3-3 | Business query
SELECT DISTINCT VALUE d.doc_id FROM {{table}} d UNNEST d.`doc`.`lineitems` a WHERE ((a.`partsupp`.`part`.`brand` = "Brand#12") AND (a.`partsupp`.`part`.`size` >= 20) AND (a.`quantity` <= 10));

-- query: H-C3-4 | Business query
SELECT DISTINCT VALUE d.doc_id FROM {{table}} d UNNEST d.`doc`.`lineitems` a WHERE ((a.`shipmode` = "SHIP") AND ((a.`partsupp`.`supplier`.`nation`.`name` IS VALUED) AND (d.`doc`.`customer`.`nation`.`name` IS VALUED) AND (a.`partsupp`.`supplier`.`nation`.`name` != d.`doc`.`customer`.`nation`.`name`)));

-- query: H-C4-1 | Business query
SELECT VALUE {"doc_id":document_id,"result":{"orderkey": if_missing_or_null(field_0,null), "priority": if_missing_or_null(field_1,null), "customer_country": if_missing_or_null(field_2,null), "shipmode": if_missing_or_null(group_key,null), "late_lines": if_missing_or_null(count(*),null), "gross_value": if_missing_or_null(sum(a.`extendedprice`),null), "avg_quantity": if_missing_or_null(avg(a.`quantity`),null)}} FROM {{table}} d UNNEST d.`doc`.`lineitems` a WHERE (true AND ((a.`receiptdate` > a.`commitdate`) AND (a.`linestatus` = "F"))) GROUP BY d.doc_id AS document_id, d.`doc`.`orderkey` AS field_0, d.`doc`.`orderpriority` AS field_1, d.`doc`.`customer`.`nation`.`name` AS field_2, a.`shipmode` AS group_key HAVING true;

-- query: H-C4-2 | Business query
SELECT VALUE {"doc_id":document_id,"result":{"orderkey": if_missing_or_null(field_0,null), "customer": if_missing_or_null(field_1,null), "supplier_country": if_missing_or_null(group_key,null), "returned_lines": if_missing_or_null(count(*),null), "gross_value": if_missing_or_null(sum(a.`extendedprice`),null), "avg_discount": if_missing_or_null(avg(a.`discount`),null)}} FROM {{table}} d UNNEST d.`doc`.`lineitems` a WHERE ((d.`doc`.`orderstatus` = "F") AND ((a.`returnflag` = "R") AND (a.`linestatus` = "F"))) GROUP BY d.doc_id AS document_id, d.`doc`.`orderkey` AS field_0, d.`doc`.`customer`.`name` AS field_1, a.`partsupp`.`supplier`.`nation`.`name` AS group_key HAVING true;

-- query: H-C4-3 | Business query
SELECT VALUE {"doc_id":document_id,"result":{"orderkey": if_missing_or_null(field_0,null), "orderdate": if_missing_or_null(field_1,null), "customer_country": if_missing_or_null(field_2,null), "air_lines": if_missing_or_null(count(*),null), "quantity": if_missing_or_null(sum(a.`quantity`),null), "gross_value": if_missing_or_null(sum(a.`extendedprice`),null)}} FROM {{table}} d UNNEST d.`doc`.`lineitems` a WHERE (true AND ((a.`shipmode` = "AIR") AND ((a.`partsupp`.`supplier`.`nation`.`name` IS VALUED) AND (d.`doc`.`customer`.`nation`.`name` IS VALUED) AND (a.`partsupp`.`supplier`.`nation`.`name` != d.`doc`.`customer`.`nation`.`name`)))) GROUP BY d.doc_id AS document_id, d.`doc`.`orderkey` AS field_0, d.`doc`.`orderdate` AS field_1, d.`doc`.`customer`.`nation`.`name` AS field_2 HAVING (count(*) >= 1);

-- query: H-C4-4 | Business query
SELECT VALUE {"doc_id":document_id,"result":{"orderkey": if_missing_or_null(field_0,null), "priority": if_missing_or_null(field_1,null), "segment": if_missing_or_null(field_2,null), "large_lines": if_missing_or_null(count(*),null), "quantity": if_missing_or_null(sum(a.`quantity`),null), "gross_value": if_missing_or_null(sum(a.`extendedprice`),null), "avg_quantity": if_missing_or_null(avg(a.`quantity`),null)}} FROM {{table}} d UNNEST d.`doc`.`lineitems` a WHERE (((d.`doc`.`orderpriority` = "1-URGENT") OR (d.`doc`.`orderpriority` = "2-HIGH")) AND ((a.`partsupp`.`part`.`size` >= 20) AND (a.`quantity` >= 30))) GROUP BY d.doc_id AS document_id, d.`doc`.`orderkey` AS field_0, d.`doc`.`orderpriority` AS field_1, d.`doc`.`customer`.`mktsegment` AS field_2 HAVING (count(*) >= 1);
