-- query: YB-C1-1 | Business query
SELECT doc_id FROM {{table}} WHERE {{relational_filter}} AND doc.is_open = 1
  AND doc.stars >= 4 AND doc.review_count >= 100 FORMAT JSONCompactEachRow;

-- query: YB-C1-2 | Business query
SELECT doc_id FROM {{table}} WHERE {{relational_filter}} AND doc.city = 'Philadelphia' AND doc.is_open = 1
  AND doc.stars >= 4 FORMAT JSONCompactEachRow;

-- query: YB-C1-3 | Business query
SELECT doc_id FROM {{table}} WHERE {{relational_filter}} AND doc.stars >= 4 AND doc.is_open = 1
  AND doc.attributes.GoodForKids = 'True' AND doc.attributes.RestaurantsTakeOut = 'True' FORMAT JSONCompactEachRow;

-- query: YB-C1-4 | Business query
SELECT doc_id FROM {{table}} WHERE {{relational_filter}} AND doc.review_count >= 50 AND doc.is_open = 1
  AND doc.attributes.RestaurantsDelivery = 'True'
  AND doc.attributes.BusinessAcceptsCreditCards = 'True' FORMAT JSONCompactEachRow;
