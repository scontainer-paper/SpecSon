-- query: G-C1-1 | Business query
SELECT d.doc_id FROM {{table}} d WHERE EXISTS (SELECT 1 WHERE d.doc->'payload'->'issue'->>'state' = 'open' AND (d.doc->'payload'->'issue'->>'comments')::bigint >= 10);

-- query: G-C1-2 | Business query
SELECT d.doc_id FROM {{table}} d WHERE EXISTS (SELECT 1 WHERE d.doc->>'type' = 'ForkEvent'
  AND (d.doc->'payload'->'forkee'->>'size')::bigint >= 10240);

-- query: G-C1-3 | Business query
SELECT d.doc_id FROM {{table}} d WHERE EXISTS (SELECT 1 WHERE d.doc->'payload'->'issue'->>'state' = 'open' AND (d.doc->'payload'->'issue'->'reactions'->>'total_count')::bigint >= 5);

-- query: G-C1-4 | Business query
SELECT d.doc_id FROM {{table}} d WHERE EXISTS (SELECT 1 WHERE d.doc->>'type' = 'IssueCommentEvent' AND d.doc->'payload'->>'action' = 'created'
  AND (d.doc->'payload'->'issue'->>'comments')::bigint >= 5);

-- query: G-C2-1 | Business query
SELECT d.doc_id FROM {{table}} d WHERE JSON_EXISTS((d.doc->'payload'->'issue'->'labels')::json, '$[*] ? (@.name == "bug")');

-- query: G-C2-2 | Business query
SELECT d.doc_id FROM {{table}} d WHERE JSON_EXISTS((d.doc->'payload'->'release'->'assets')::json, '$[*] ? (@.size >= 104857600)');

-- query: G-C2-3 | Business query
SELECT d.doc_id FROM {{table}} d CROSS JOIN LATERAL json_array_elements(NULLIF(d.doc->'payload'->'release'->'assets', 'null'::jsonb)::json) AS asset(v) GROUP BY d.doc_id HAVING sum((asset.v->>'size')::bigint) >= 104857600;

-- query: G-C2-4 | Business query
SELECT d.doc_id FROM {{table}} d CROSS JOIN LATERAL json_array_elements(NULLIF(d.doc->'payload'->'release'->'assets', 'null'::jsonb)::json) AS asset(v) GROUP BY d.doc_id HAVING avg((asset.v->>'size')::bigint) >= 10485760;

-- query: G-C3-1 | Business query
SELECT d.doc_id FROM {{table}} d WHERE JSON_EXISTS((d.doc->'payload'->'release'->'assets')::json, '$[*] ? (@.size >= 10485760 && @.content_type == "application/zip")');

-- query: G-C3-2 | Business query
SELECT DISTINCT d.doc_id FROM {{table}} d CROSS JOIN LATERAL json_array_elements(NULLIF(d.doc->'payload'->'issue'->'assignees', 'null'::jsonb)::json) AS assignee(v)
  WHERE assignee.v->>'type' = 'User' AND assignee.v->>'login' = d.doc->'payload'->'issue'->'user'->>'login';

-- query: G-C3-3 | Business query
SELECT d.doc_id FROM {{table}} d WHERE JSON_EXISTS((d.doc->'payload'->'pages')::json, '$[*] ? (@.page_name == "Home" && @.action == "edited")');

-- query: G-C3-4 | Business query
SELECT d.doc_id FROM {{table}} d WHERE JSON_EXISTS((d.doc->'payload'->'release'->'assets')::json, '$[*] ? (@.state == "uploaded" && @.content_type == "application/zip" && @.uploader.type == "Bot")');

-- query: G-C4-1 | Business query
SELECT d.doc_id,json_object('repository' VALUE any_value(d.doc->'repo'->>'name'),'tag' VALUE any_value(d.doc->'payload'->'release'->>'tag_name'),'assets' VALUE count(*),'bytes' VALUE sum((asset.v->>'size')::bigint),'downloads' VALUE sum((asset.v->>'download_count')::bigint)) FROM {{table}} d CROSS JOIN LATERAL json_array_elements(NULLIF(d.doc->'payload'->'release'->'assets', 'null'::jsonb)::json) AS asset(v)
  WHERE asset.v->>'state' = 'uploaded' AND (asset.v->>'size')::bigint >= 1048576 AND asset.v->>'content_type' = 'application/octet-stream'
   GROUP BY d.doc_id HAVING count(*) >= 1;

-- query: G-C4-2 | Business query
SELECT d.doc_id,json_object('repository' VALUE any_value(d.doc->'repo'->>'name'),'tag' VALUE any_value(d.doc->'payload'->'release'->>'tag_name'),'zip_assets' VALUE count(*),'bytes' VALUE sum((asset.v->>'size')::bigint),'avg_bytes' VALUE avg((asset.v->>'size')::bigint)) FROM {{table}} d CROSS JOIN LATERAL json_array_elements(NULLIF(d.doc->'payload'->'release'->'assets', 'null'::jsonb)::json) AS asset(v)
  WHERE asset.v->>'state' = 'uploaded' AND asset.v->>'content_type' = 'application/zip'
   GROUP BY d.doc_id HAVING avg((asset.v->>'size')::bigint) >= 10485760;

-- query: G-C4-3 | Business query
SELECT d.doc_id,json_object('repository' VALUE any_value(d.doc->'repo'->>'name'),'tag' VALUE any_value(d.doc->'payload'->'release'->>'tag_name'),'bot_assets' VALUE count(*),'downloads' VALUE sum((asset.v->>'download_count')::bigint),'avg_bytes' VALUE avg((asset.v->>'size')::bigint)) FROM {{table}} d CROSS JOIN LATERAL json_array_elements(NULLIF(d.doc->'payload'->'release'->'assets', 'null'::jsonb)::json) AS asset(v)
  WHERE asset.v->>'state' = 'uploaded' AND asset.v->'uploader'->>'type' = 'Bot'
   GROUP BY d.doc_id HAVING count(*) >= 1;

-- query: G-C4-4 | Business query
SELECT d.doc_id,json_object('repository' VALUE any_value(d.doc->'repo'->>'name'),'issue' VALUE any_value(d.doc->'payload'->'issue'->>'html_url'),'title' VALUE any_value(d.doc->'payload'->'issue'->>'title'),'comments' VALUE (any_value(d.doc->'payload'->'issue'->>'comments'))::bigint,'human_assignees' VALUE count(*)) FROM {{table}} d CROSS JOIN LATERAL json_array_elements(NULLIF(d.doc->'payload'->'issue'->'assignees', 'null'::jsonb)::json) AS assignee(v)
  WHERE (d.doc->'payload'->'issue'->>'state' = 'open') AND (assignee.v->>'type' = 'User')
 GROUP BY d.doc_id HAVING count(*) >= 2
    AND bool_or(assignee.v->>'login' = d.doc->'payload'->'issue'->'user'->>'login');
