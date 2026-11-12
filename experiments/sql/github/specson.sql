-- query: G-C1-1 | Business query
SELECT d.doc_id FROM {{table}} d WHERE d.doc#>>'{payload,issue,state}' = 'open' AND (d.doc#>>'{payload,issue,comments}')::bigint >= 10;

-- query: G-C1-2 | Business query
SELECT d.doc_id FROM {{table}} d WHERE d.doc->>'type' = 'ForkEvent'
  AND (d.doc#>>'{payload,forkee,size}')::bigint >= 10240;

-- query: G-C1-3 | Business query
SELECT d.doc_id FROM {{table}} d WHERE d.doc#>>'{payload,issue,state}' = 'open' AND (d.doc#>>'{payload,issue,reactions,total_count}')::bigint >= 5;

-- query: G-C1-4 | Business query
SELECT d.doc_id FROM {{table}} d WHERE d.doc->>'type' = 'IssueCommentEvent' AND d.doc#>>'{payload,action}' = 'created'
  AND (d.doc#>>'{payload,issue,comments}')::bigint >= 5;

-- query: G-C2-1 | Business query
SELECT d.doc_id FROM {{table}} d WHERE EXISTS (SELECT 1 WHERE EXISTS (
  SELECT 1 FROM jsonb_array_elements(NULLIF(d.doc#>'{payload,issue,labels}', 'null'::jsonb)) AS label
  WHERE label->>'name' = 'bug'));

-- query: G-C2-2 | Business query
SELECT d.doc_id FROM {{table}} d WHERE EXISTS (SELECT 1 WHERE EXISTS (
  SELECT 1 FROM jsonb_array_elements(NULLIF(d.doc#>'{payload,release,assets}', 'null'::jsonb)) AS asset
  WHERE (asset->>'size')::bigint >= 104857600));

-- query: G-C2-3 | Business query
SELECT d.doc_id FROM {{table}} d WHERE EXISTS (SELECT 1 WHERE (SELECT sum((asset->>'size')::bigint)
  FROM jsonb_array_elements(NULLIF(d.doc#>'{payload,release,assets}', 'null'::jsonb)) AS asset) >= 104857600);

-- query: G-C2-4 | Business query
SELECT d.doc_id FROM {{table}} d WHERE EXISTS (SELECT 1 WHERE (SELECT avg((asset->>'size')::bigint)
  FROM jsonb_array_elements(NULLIF(d.doc#>'{payload,release,assets}', 'null'::jsonb)) AS asset) >= 10485760);

-- query: G-C3-1 | Business query
SELECT d.doc_id FROM {{table}} d WHERE EXISTS (SELECT 1 WHERE EXISTS (
  SELECT 1 FROM jsonb_array_elements(NULLIF(d.doc#>'{payload,release,assets}', 'null'::jsonb)) AS asset
  WHERE (asset->>'size')::bigint >= 10485760 AND asset->>'content_type' = 'application/zip'));

-- query: G-C3-2 | Business query
SELECT d.doc_id FROM {{table}} d WHERE EXISTS (SELECT 1 WHERE EXISTS (
  SELECT 1 FROM jsonb_array_elements(NULLIF(d.doc#>'{payload,issue,assignees}', 'null'::jsonb)) AS assignee
  WHERE assignee->>'type' = 'User' AND assignee->>'login' = d.doc#>>'{payload,issue,user,login}'));

-- query: G-C3-3 | Business query
SELECT d.doc_id FROM {{table}} d WHERE EXISTS (SELECT 1 WHERE EXISTS (
  SELECT 1 FROM jsonb_array_elements(NULLIF(d.doc#>'{payload,pages}', 'null'::jsonb)) AS page
  WHERE page->>'page_name' = 'Home' AND page->>'action' = 'edited'));

-- query: G-C3-4 | Business query
SELECT d.doc_id FROM {{table}} d WHERE EXISTS (SELECT 1 WHERE EXISTS (
  SELECT 1 FROM jsonb_array_elements(NULLIF(d.doc#>'{payload,release,assets}', 'null'::jsonb)) AS asset
  WHERE asset->>'state' = 'uploaded' AND asset->>'content_type' = 'application/zip' AND asset#>>'{uploader,type}' = 'Bot'));

-- query: G-C4-1 | Business query
SELECT doc_id,result FROM (SELECT d.doc_id,(SELECT jsonb_build_object('repository', d.doc#>>'{repo,name}', 'tag', d.doc#>>'{payload,release,tag_name}',
  'assets', summary.assets, 'bytes', summary.bytes, 'downloads', summary.downloads)
FROM LATERAL (
  SELECT count(*) AS assets, sum((asset->>'size')::bigint) AS bytes, sum((asset->>'download_count')::bigint) AS downloads
  FROM jsonb_array_elements(NULLIF(d.doc#>'{payload,release,assets}', 'null'::jsonb)) AS asset
  WHERE asset->>'state' = 'uploaded' AND (asset->>'size')::bigint >= 1048576 AND asset->>'content_type' = 'application/octet-stream'
  HAVING count(*) >= 1
) AS summary) AS result FROM {{table}} d) s WHERE result IS NOT NULL;

-- query: G-C4-2 | Business query
SELECT doc_id,result FROM (SELECT d.doc_id,(SELECT jsonb_build_object('repository', d.doc#>>'{repo,name}', 'tag', d.doc#>>'{payload,release,tag_name}',
  'zip_assets', summary.assets, 'bytes', summary.bytes, 'avg_bytes', summary.avg_bytes)
FROM LATERAL (
  SELECT count(*) AS assets, sum((asset->>'size')::bigint) AS bytes, avg((asset->>'size')::bigint) AS avg_bytes
  FROM jsonb_array_elements(NULLIF(d.doc#>'{payload,release,assets}', 'null'::jsonb)) AS asset
  WHERE asset->>'state' = 'uploaded' AND asset->>'content_type' = 'application/zip'
  HAVING avg((asset->>'size')::bigint) >= 10485760
) AS summary) AS result FROM {{table}} d) s WHERE result IS NOT NULL;

-- query: G-C4-3 | Business query
SELECT doc_id,result FROM (SELECT d.doc_id,(SELECT jsonb_build_object('repository', d.doc#>>'{repo,name}', 'tag', d.doc#>>'{payload,release,tag_name}',
  'bot_assets', summary.assets, 'downloads', summary.downloads, 'avg_bytes', summary.avg_bytes)
FROM LATERAL (
  SELECT count(*) AS assets, sum((asset->>'download_count')::bigint) AS downloads, avg((asset->>'size')::bigint) AS avg_bytes
  FROM jsonb_array_elements(NULLIF(d.doc#>'{payload,release,assets}', 'null'::jsonb)) AS asset
  WHERE asset->>'state' = 'uploaded' AND asset#>>'{uploader,type}' = 'Bot'
  HAVING count(*) >= 1
) AS summary) AS result FROM {{table}} d) s WHERE result IS NOT NULL;

-- query: G-C4-4 | Business query
SELECT doc_id,result FROM (SELECT d.doc_id,(SELECT jsonb_build_object('repository', d.doc#>>'{repo,name}', 'issue', d.doc#>>'{payload,issue,html_url}',
  'title', d.doc#>>'{payload,issue,title}', 'comments', (d.doc#>>'{payload,issue,comments}')::bigint, 'human_assignees', summary.people)
FROM LATERAL (
  SELECT count(*) AS people FROM jsonb_array_elements(NULLIF(d.doc#>'{payload,issue,assignees}', 'null'::jsonb)) AS assignee
  WHERE assignee->>'type' = 'User'
  HAVING count(*) >= 2
    AND bool_or(assignee->>'login' = d.doc#>>'{payload,issue,user,login}')
) AS summary
WHERE d.doc#>>'{payload,issue,state}' = 'open') AS result FROM {{table}} d) s WHERE result IS NOT NULL;
