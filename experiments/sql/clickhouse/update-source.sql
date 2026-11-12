CREATE TABLE {{snapshot}} ENGINE=Join(ANY,LEFT,doc_id) AS
SELECT doc_id,toJSONString(doc) AS raw FROM {{table}}
WHERE doc_id >= {{batch_start}} AND doc_id < {{batch_end}}
