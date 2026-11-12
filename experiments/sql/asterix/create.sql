CREATE TYPE {{table}}_type AS OPEN {doc_id: bigint};
CREATE DATASET {{table}}({{table}}_type) PRIMARY KEY doc_id
WITH {"storage-format": {"format": "row"}};
