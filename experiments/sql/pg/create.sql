CREATE TABLE {{table}} (doc_id integer, doc jsonb COMPRESSION lz4) WITH (autovacuum_enabled=false)
