UPDATE {{table}} AS target SET doc=specson.specson_encode({{schema_id}},source.doc::text)
FROM {{table}} AS source
WHERE source.doc_id=(target.doc_id/100)*100
    +least(100,{{rows}}-(target.doc_id/100)*100)-1-mod(target.doc_id,100)
