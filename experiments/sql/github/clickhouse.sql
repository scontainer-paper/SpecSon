-- query: G-C1-1 | Business query
SELECT doc_id FROM {{table}} WHERE {{relational_filter}} AND doc.payload.issue.state = 'open' AND doc.payload.issue.comments >= 10 FORMAT JSONCompactEachRow;

-- query: G-C1-2 | Business query
SELECT doc_id FROM {{table}} WHERE {{relational_filter}} AND doc.type = 'ForkEvent'
  AND doc.payload.forkee.size >= 10240 FORMAT JSONCompactEachRow;

-- query: G-C1-3 | Business query
SELECT doc_id FROM {{table}} WHERE {{relational_filter}} AND doc.payload.issue.state = 'open' AND doc.payload.issue.reactions.total_count >= 5 FORMAT JSONCompactEachRow;

-- query: G-C1-4 | Business query
SELECT doc_id FROM {{table}} WHERE {{relational_filter}} AND doc.type = 'IssueCommentEvent' AND doc.payload.action = 'created'
  AND doc.payload.issue.comments >= 5 FORMAT JSONCompactEachRow;

-- query: G-C2-1 | Business query
SELECT doc_id FROM {{table}} WHERE {{relational_filter}} AND arrayExists((x0) -> x0 = 'bug',doc.payload.issue.labels.name) FORMAT JSONCompactEachRow;

-- query: G-C2-2 | Business query
SELECT doc_id FROM {{table}} WHERE {{relational_filter}} AND arrayExists((x0) -> x0 >= 104857600,doc.payload.release.assets.size) FORMAT JSONCompactEachRow;

-- query: G-C2-3 | Business query
SELECT doc_id FROM {{table}} WHERE {{relational_filter}} AND arrayReduce('sumOrNull',doc.payload.release.assets.size) >= 104857600 FORMAT JSONCompactEachRow;

-- query: G-C2-4 | Business query
SELECT doc_id FROM {{table}} WHERE {{relational_filter}} AND arrayReduce('avgOrNull',doc.payload.release.assets.size) >= 10485760 FORMAT JSONCompactEachRow;

-- query: G-C3-1 | Business query
SELECT doc_id FROM {{table}} WHERE {{relational_filter}} AND arrayExists((x0,x1) -> x1 >= 10485760 AND x0 = 'application/zip',doc.payload.release.assets.content_type,doc.payload.release.assets.size) FORMAT JSONCompactEachRow;

-- query: G-C3-2 | Business query
SELECT doc_id FROM {{table}} WHERE {{relational_filter}} AND arrayExists((x0,x1) -> x1 = 'User' AND x0 = doc.payload.issue.user.login,doc.payload.issue.assignees.login,doc.payload.issue.assignees.type) FORMAT JSONCompactEachRow;

-- query: G-C3-3 | Business query
SELECT doc_id FROM {{table}} WHERE {{relational_filter}} AND arrayExists(m -> m.page_name = 'Home' AND m.action = 'edited',doc.payload.pages) FORMAT JSONCompactEachRow;

-- query: G-C3-4 | Business query
SELECT doc_id FROM {{table}} WHERE {{relational_filter}} AND arrayExists(m -> m.state = 'uploaded' AND m.content_type = 'application/zip' AND m.uploader.type = 'Bot',doc.payload.release.assets) FORMAT JSONCompactEachRow;

-- query: G-C4-1 | Business query
WITH arrayFilter(t -> t.state = 'uploaded' AND t.size >= 1048576 AND t.content_type = 'application/octet-stream',doc.payload.release.assets) AS selected SELECT doc_id,toJSONString(tuple(doc.repo.name AS repository,doc.payload.release.tag_name AS tag,length(selected) AS assets,arrayReduce('sumOrNull',arrayMap(t -> t.size,selected)) AS bytes,arrayReduce('sumOrNull',arrayMap(t -> t.download_count,selected)) AS downloads)) AS result FROM {{table}} WHERE {{relational_filter}} AND length(selected) >= 1 FORMAT JSONCompactEachRow;

-- query: G-C4-2 | Business query
WITH arrayFilter(t -> t.state = 'uploaded' AND t.content_type = 'application/zip',doc.payload.release.assets) AS selected SELECT doc_id,toJSONString(tuple(doc.repo.name AS repository,doc.payload.release.tag_name AS tag,length(selected) AS zip_assets,arrayReduce('sumOrNull',arrayMap(t -> t.size,selected)) AS bytes,arrayReduce('avgOrNull',arrayMap(t -> t.size,selected)) AS avg_bytes)) AS result FROM {{table}} WHERE {{relational_filter}} AND arrayReduce('avgOrNull',arrayMap(t -> t.size,selected)) >= 10485760 FORMAT JSONCompactEachRow;

-- query: G-C4-3 | Business query
WITH arrayFilter(t -> t.state = 'uploaded' AND t.uploader.type = 'Bot',doc.payload.release.assets) AS selected SELECT doc_id,toJSONString(tuple(doc.repo.name AS repository,doc.payload.release.tag_name AS tag,length(selected) AS bot_assets,arrayReduce('sumOrNull',arrayMap(t -> t.download_count,selected)) AS downloads,arrayReduce('avgOrNull',arrayMap(t -> t.size,selected)) AS avg_bytes)) AS result FROM {{table}} WHERE {{relational_filter}} AND length(selected) >= 1 FORMAT JSONCompactEachRow;

-- query: G-C4-4 | Business query
WITH arrayFilter(t -> t.type = 'User',doc.payload.issue.assignees) AS selected SELECT doc_id,toJSONString(tuple(doc.repo.name AS repository,doc.payload.issue.html_url AS issue,doc.payload.issue.title AS title,doc.payload.issue.comments AS comments,length(selected) AS human_assignees)) AS result FROM {{table}} WHERE {{relational_filter}} AND (doc.payload.issue.state = 'open') AND length(selected) >= 2
    AND arrayExists(t -> t.login = doc.payload.issue.user.login,selected) FORMAT JSONCompactEachRow;
