-- query: YB-C1-1 | Business query
SELECT VALUE d.doc_id FROM {{table}} d WHERE ((d.`doc`.`is_open` = 1) AND (d.`doc`.`stars` >= 4) AND (d.`doc`.`review_count` >= 100));

-- query: YB-C1-2 | Business query
SELECT VALUE d.doc_id FROM {{table}} d WHERE ((d.`doc`.`city` = "Philadelphia") AND (d.`doc`.`is_open` = 1) AND (d.`doc`.`stars` >= 4));

-- query: YB-C1-3 | Business query
SELECT VALUE d.doc_id FROM {{table}} d WHERE ((d.`doc`.`stars` >= 4) AND (d.`doc`.`is_open` = 1) AND (d.`doc`.`attributes`.`GoodForKids` = "True") AND (d.`doc`.`attributes`.`RestaurantsTakeOut` = "True"));

-- query: YB-C1-4 | Business query
SELECT VALUE d.doc_id FROM {{table}} d WHERE ((d.`doc`.`review_count` >= 50) AND (d.`doc`.`is_open` = 1) AND (d.`doc`.`attributes`.`RestaurantsDelivery` = "True") AND (d.`doc`.`attributes`.`BusinessAcceptsCreditCards` = "True"));
