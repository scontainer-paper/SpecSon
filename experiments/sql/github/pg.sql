-- query: G-C1-1 | Business query
SELECT d.doc_id FROM {{table}} d WHERE EXISTS (SELECT 1 WHERE d.doc#>>'{payload,issue,state}' = 'open' AND (d.doc#>>'{payload,issue,comments}')::bigint >= 10);

-- query: G-C1-2 | Business query
SELECT d.doc_id FROM {{table}} d WHERE EXISTS (SELECT 1 WHERE d.doc->>'type' = 'ForkEvent'
  AND (d.doc#>>'{payload,forkee,size}')::bigint >= 10240);

-- query: G-C1-3 | Business query
SELECT d.doc_id FROM {{table}} d WHERE EXISTS (SELECT 1 WHERE d.doc#>>'{payload,issue,state}' = 'open' AND (d.doc#>>'{payload,issue,reactions,total_count}')::bigint >= 5);

-- query: G-C1-4 | Business query
SELECT d.doc_id FROM {{table}} d WHERE EXISTS (SELECT 1 WHERE d.doc->>'type' = 'IssueCommentEvent' AND d.doc#>>'{payload,action}' = 'created'
  AND (d.doc#>>'{payload,issue,comments}')::bigint >= 5);

-- query: G-C2-1 | Business query
SELECT d.doc_id FROM {{table}} d WHERE JSON_EXISTS(d.doc, '$.payload.issue.labels[*] ? (@.name == "bug")');

-- query: G-C2-2 | Business query
SELECT d.doc_id FROM {{table}} d WHERE JSON_EXISTS(d.doc, '$.payload.release.assets[*] ? (@.size >= 104857600)');

-- query: G-C2-3 | Business query
WITH items AS MATERIALIZED (SELECT d.doc_id,asset->>'size' AS v0 FROM (SELECT * FROM {{table}} WHERE doc#>'{payload,release,assets}' IS NOT NULL) d CROSS JOIN LATERAL jsonb_array_elements(NULLIF(d.doc#>'{payload,release,assets}', 'null'::jsonb)) AS asset) SELECT i.doc_id FROM items i GROUP BY i.doc_id HAVING sum((i.v0)::bigint) >= 104857600;

-- query: G-C2-4 | Business query
WITH items AS MATERIALIZED (SELECT d.doc_id,asset->>'size' AS v0 FROM (SELECT * FROM {{table}} WHERE doc#>'{payload,release,assets}' IS NOT NULL) d CROSS JOIN LATERAL jsonb_array_elements(NULLIF(d.doc#>'{payload,release,assets}', 'null'::jsonb)) AS asset) SELECT i.doc_id FROM items i GROUP BY i.doc_id HAVING avg((i.v0)::bigint) >= 10485760;

-- query: G-C3-1 | Business query
SELECT d.doc_id FROM {{table}} d WHERE JSON_EXISTS(d.doc, '$.payload.release.assets[*] ? (@.size >= 10485760 && @.content_type == "application/zip")');

-- query: G-C3-2 | Business query
SELECT DISTINCT d.doc_id FROM (SELECT * FROM {{table}} WHERE doc#>'{payload,issue,assignees}' IS NOT NULL) d CROSS JOIN LATERAL jsonb_array_elements(NULLIF(d.doc#>'{payload,issue,assignees}', 'null'::jsonb)) AS assignee
  WHERE assignee->>'type' = 'User' AND assignee->>'login' = d.doc#>>'{payload,issue,user,login}';

-- query: G-C3-3 | Business query
SELECT d.doc_id FROM {{table}} d WHERE JSON_EXISTS(d.doc, '$.payload.pages[*] ? (@.page_name == "Home" && @.action == "edited")');

-- query: G-C3-4 | Business query
SELECT d.doc_id FROM {{table}} d WHERE JSON_EXISTS(d.doc, '$.payload.release.assets[*] ? (@.state == "uploaded" && @.content_type == "application/zip" && @.uploader.type == "Bot")');

-- query: G-C4-1 | Business query
SELECT d.doc_id,q.* FROM {{table}} d CROSS JOIN LATERAL (SELECT jsonb_build_object('repository', d.doc#>>'{repo,name}', 'tag', d.doc#>>'{payload,release,tag_name}',
  'assets', summary.assets, 'bytes', summary.bytes, 'downloads', summary.downloads)
FROM LATERAL (
  SELECT count(*) AS assets, sum((asset->>'size')::bigint) AS bytes, sum((asset->>'download_count')::bigint) AS downloads
  FROM jsonb_array_elements(NULLIF(d.doc#>'{payload,release,assets}', 'null'::jsonb)) AS asset
  WHERE asset->>'state' = 'uploaded' AND (asset->>'size')::bigint >= 1048576 AND asset->>'content_type' = 'application/octet-stream'
  HAVING count(*) >= 1
) AS summary) q WHERE JSON_EXISTS(d.doc, '$.payload.release.assets[*]');

-- query: G-C4-2 | Business query
SELECT d.doc_id,q.* FROM {{table}} d CROSS JOIN LATERAL (SELECT jsonb_build_object('repository', d.doc#>>'{repo,name}', 'tag', d.doc#>>'{payload,release,tag_name}',
  'zip_assets', summary.assets, 'bytes', summary.bytes, 'avg_bytes', summary.avg_bytes)
FROM LATERAL (
  SELECT count(*) AS assets, sum((asset->>'size')::bigint) AS bytes, avg((asset->>'size')::bigint) AS avg_bytes
  FROM jsonb_array_elements(NULLIF(d.doc#>'{payload,release,assets}', 'null'::jsonb)) AS asset
  WHERE asset->>'state' = 'uploaded' AND asset->>'content_type' = 'application/zip'
  HAVING avg((asset->>'size')::bigint) >= 10485760
) AS summary) q WHERE JSON_EXISTS(d.doc, '$.payload.release.assets[*]');

-- query: G-C4-3 | Business query
SELECT d.doc_id,q.* FROM {{table}} d CROSS JOIN LATERAL (SELECT jsonb_build_object('repository', d.doc#>>'{repo,name}', 'tag', d.doc#>>'{payload,release,tag_name}',
  'bot_assets', summary.assets, 'downloads', summary.downloads, 'avg_bytes', summary.avg_bytes)
FROM LATERAL (
  SELECT count(*) AS assets, sum((asset->>'download_count')::bigint) AS downloads, avg((asset->>'size')::bigint) AS avg_bytes
  FROM jsonb_array_elements(NULLIF(d.doc#>'{payload,release,assets}', 'null'::jsonb)) AS asset
  WHERE asset->>'state' = 'uploaded' AND asset#>>'{uploader,type}' = 'Bot'
  HAVING count(*) >= 1
) AS summary) q WHERE JSON_EXISTS(d.doc, '$.payload.release.assets[*]');

-- query: G-C4-4 | Business query
SELECT d.doc_id,q.* FROM {{table}} d CROSS JOIN LATERAL (SELECT jsonb_build_object('repository', d.doc#>>'{repo,name}', 'issue', d.doc#>>'{payload,issue,html_url}',
  'title', d.doc#>>'{payload,issue,title}', 'comments', (d.doc#>>'{payload,issue,comments}')::bigint, 'human_assignees', summary.people)
FROM LATERAL (
  SELECT count(*) AS people FROM jsonb_array_elements(NULLIF(d.doc#>'{payload,issue,assignees}', 'null'::jsonb)) AS assignee
  WHERE assignee->>'type' = 'User'
  HAVING count(*) >= 2
    AND bool_or(assignee->>'login' = d.doc#>>'{payload,issue,user,login}')
) AS summary
WHERE d.doc#>>'{payload,issue,state}' = 'open') q;
