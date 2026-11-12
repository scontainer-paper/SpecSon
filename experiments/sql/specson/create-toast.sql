CREATE TABLE {{table}} (doc_id integer, doc specson.specson COMPRESSION lz4) WITH (autovacuum_enabled=false, specson_storage=toast)
