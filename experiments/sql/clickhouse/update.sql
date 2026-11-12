UPDATE {{table}} SET doc=CAST(joinGet('{{snapshot}}','raw',
    toUInt32(intDiv(doc_id,100)*100+least(100,{{rows}}-intDiv(doc_id,100)*100)-1-modulo(doc_id,100))) AS {{doc_type}})
WHERE doc_id >= {{batch_start}} AND doc_id < {{batch_end}}
