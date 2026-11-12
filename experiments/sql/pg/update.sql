UPDATE {{table}} AS target SET doc=(source.doc::text)::jsonb
FROM {{table}} AS source
WHERE source.doc_id=(target.doc_id/100)*100
    +least(100,{{rows}}-(target.doc_id/100)*100)-1-mod(target.doc_id,100)
