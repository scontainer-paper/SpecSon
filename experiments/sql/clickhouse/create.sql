CREATE TABLE {{table}} (doc_id UInt32, doc {{doc_type}})
ENGINE=MergeTree ORDER BY tuple()
SETTINGS enable_block_number_column=1, enable_block_offset_column=1,
fsync_after_insert=1, fsync_part_directory=1
