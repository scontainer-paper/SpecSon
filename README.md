# SpecSon PostgreSQL experiment bundle

This directory contains the current SpecSon PostgreSQL release artifact, the
formal experiment harness, the experiment schemas and JSONPaths, and the four
canonical synthetic-data generators. The dataset files are distributed
separately: [download the complete dataset bundle from Google Drive](https://drive.google.com/file/d/1uap3LueGqBhA5iiS1uKOl4YxlU_f0sS6/view?usp=sharing).

## Important safety and support limitations

> [!WARNING]
> This PostgreSQL extension is a research prototype, not production software.
> Do not install or run it in a PostgreSQL instance or cluster that contains
> valuable data. It may crash PostgreSQL, corrupt database state, or cause data
> loss. Use only an isolated, disposable experiment instance, with independent
> backups, at your own risk.
>
> Query only with schemas and JSONPath forms that have been validated for this
> release. Unsupported syntax is rejected instead of being treated as a
> different query.

### Unsupported syntax and features

The current release implements PostgreSQL's default `lax` behavior for the
admitted language. `like_regex`, `starts with`, filters, arithmetic, array
selectors, and the `abs()`, `floor()`, and `ceiling()` numeric methods are
supported. The following PostgreSQL JSONPath and SQL API features are not
supported:

| Feature | Example | Current limitation |
|---|---|---|
| Strict path mode | `strict $.a` | Only default/explicit `lax` mode is admitted. |
| Object-member wildcard | `$.*` | Wildcard object-member traversal is not parsed. |
| Recursive descent | `$.**` or `$.**{1 to 3}` | Recursive wildcard traversal is not parsed. |
| General item methods | `$.a.type()`, `$.a.size()`, `$.a.double()`, `$.a.datetime()`, `$.a.keyvalue()` | Only `abs()`, `floor()`, and `ceiling()` are implemented. PostgreSQL 18 conversion/date-time item methods are also outside the admitted language. |
| Free-spacing regular expressions | `$ like_regex "a b" flag "x"` | The `x` flag is not implemented unless `q` makes the pattern literal. Flags `i`, `s`, `m`, and `q` are supported. |
| External JSONPath variables through the SQL API | `$.a ? (@ > $limit)` | Variable syntax is parsed, but the public `specson_query_*` functions do not accept a variables JSON argument. |
| Silent execution through the SQL API | PostgreSQL's `silent => true` argument | Silent execution is not supported by the public functions. |
| Match result mode | `jsonb_path_match(...)` equivalent | Match results are not supported; the public API supports Exists, Count, and Items only. |

## Query results

We extended the paper's JSONPath workload and obtained the following results.

### Extended query workload

#### github

| Schema | Query | Operation | JSONB (ms) | SpecSon (ms) | Speedup | JSONPath |
|---|---|---|---:|---:|---:|---|
| integer | G-X1 | exists | 21.714 | 12.522 | 1.734× | `$.actor.login` |
| integer | G-X1 | count | 76.821 | 13.508 | 5.687× | `$.actor.login` |
| integer | G-X2 | exists | 24.948 | 12.755 | 1.956× | `$.repo.id ? (@ > 0)` |
| integer | G-X2 | count | 84.838 | 17.717 | 4.788× | `$.repo.id ? (@ > 0)` |
| integer | G-X3 | exists | 23.442 | 12.890 | 1.819× | `$.payload.action` |
| integer | G-X3 | count | 60.355 | 14.984 | 4.028× | `$.payload.action` |
| integer | G-X4 | exists | 19.678 | 12.045 | 1.634× | `$.payload.issue.labels[*].name` |
| integer | G-X4 | count | 57.629 | 15.135 | 3.808× | `$.payload.issue.labels[*].name` |
| integer | G-X5 | exists | 20.937 | 12.456 | 1.681× | `$.payload.release.assets[*].uploader.login` |
| integer | G-X5 | count | 58.444 | 14.511 | 4.027× | `$.payload.release.assets[*].uploader.login` |
| integer | G-X6 | exists | 20.541 | 11.999 | 1.712× | `$.payload.release.assets[0].size ? (@ >= 1)` |
| integer | G-X6 | count | 60.931 | 16.373 | 3.721× | `$.payload.release.assets[0].size ? (@ >= 1)` |
| integer | G-X7 | exists | 31.057 | 14.748 | 2.106× | `$ ? (@.public == true && @.actor.id > 0)` |
| integer | G-X7 | count | 92.474 | 15.185 | 6.090× | `$ ? (@.public == true && @.actor.id > 0)` |
| integer | G-X8 | exists | 23.546 | 12.467 | 1.889× | `$ ? (@.type == "IssuesEvent" && exists(@.payload.issue.labels[*] ? (@.default == false && @.color != "")))` |
| integer | G-X8 | count | 66.083 | 15.066 | 4.386× | `$ ? (@.type == "IssuesEvent" && exists(@.payload.issue.labels[*] ? (@.default == false && @.color != "")))` |
| integer | G-X9 | exists | 22.303 | 11.821 | 1.887× | `$ ? (@.type == "IssuesEvent" && exists(@.payload.issue.issue_field_values[*] ? (@.issue_field_name != "" && exists(@.single_select_option.name))))` |
| integer | G-X9 | count | 66.456 | 15.682 | 4.238× | `$ ? (@.type == "IssuesEvent" && exists(@.payload.issue.issue_field_values[*] ? (@.issue_field_name != "" && exists(@.single_select_option.name))))` |
| integer | G-X10 | exists | 24.090 | 11.614 | 2.074× | `$ ? (@.type == "ReleaseEvent" && @.public == true && exists(@.payload.release.assets[*] ? (@.size > 0 && @.uploader.login != "")))` |
| integer | G-X10 | count | 68.215 | 15.447 | 4.416× | `$ ? (@.type == "ReleaseEvent" && @.public == true && exists(@.payload.release.assets[*] ? (@.size > 0 && @.uploader.login != "")))` |
| integer | G-X11 | exists | 19.596 | 12.627 | 1.552× | `$.payload.release.assets[last,0,last,1 to 2] ? (@.size >= 1).uploader.login` |
| integer | G-X11 | count | 58.848 | 15.876 | 3.707× | `$.payload.release.assets[last,0,last,1 to 2] ? (@.size >= 1).uploader.login` |
| integer | G-X12 | exists | 20.127 | 13.966 | 1.441× | `$.payload.issue.labels[last,0,last,0 to 2] ? (@.name != "").name` |
| integer | G-X12 | count | 59.196 | 16.082 | 3.681× | `$.payload.issue.labels[last,0,last,0 to 2] ? (@.name != "").name` |
| integer | G-X13 | exists | 19.841 | 12.257 | 1.619× | `$.payload.pages[last,0,last] ? (@.action != "").title` |
| integer | G-X13 | count | 57.722 | 15.115 | 3.819× | `$.payload.pages[last,0,last] ? (@.action != "").title` |
| integer | G-X14 | exists | 25.623 | 16.346 | 1.568× | `$ ? (exists(@.payload.issue.labels[*] ? (@.name like_regex "^bug$" flag "i")) \|\| exists(@.payload.release.assets[*] ? (@.content_type starts with "audio/")))` |
| integer | G-X14 | count | 65.649 | 20.354 | 3.225× | `$ ? (exists(@.payload.issue.labels[*] ? (@.name like_regex "^bug$" flag "i")) \|\| exists(@.payload.release.assets[*] ? (@.content_type starts with "audio/")))` |
| integer | G-X15 | exists | 22.377 | 11.335 | 1.974× | `$ ? (((@.org.id > 0) is unknown) && @.public == true)` |
| integer | G-X15 | count | 64.706 | 16.516 | 3.918× | `$ ? (((@.org.id > 0) is unknown) && @.public == true)` |
| integer | G-X16 | exists | 20.757 | 13.641 | 1.522× | `$.payload.release.assets[$.actor.id].uploader.login` |
| integer | G-X16 | count | 65.229 | 18.162 | 3.591× | `$.payload.release.assets[$.actor.id].uploader.login` |
| integer | G-X17 | exists | 22.494 | 12.945 | 1.738× | `$ ? (!exists(@.org) \|\| (@.org.login != "" && @.repo.name != ""))` |
| integer | G-X17 | count | 85.158 | 16.159 | 5.270× | `$ ? (!exists(@.org) \|\| (@.org.login != "" && @.repo.name != ""))` |
| integer | G-X18 | exists | 19.791 | 11.130 | 1.778× | `$.payload.issue.labels[*] ? (@.name != "") ? (@.color != "").name` |
| integer | G-X18 | count | 58.693 | 14.998 | 3.913× | `$.payload.issue.labels[*] ? (@.name != "") ? (@.color != "").name` |
| integer | G-X19 | exists | 17.663 | 9.519 | 1.856× | `$.payload.issue.reactions."+1" ? (@ > 0)` |
| integer | G-X19 | count | 55.847 | 13.424 | 4.160× | `$.payload.issue.reactions."+1" ? (@ > 0)` |
| numeric | G-X1 | exists | 21.498 | 10.525 | 2.043× | `$.actor.login` |
| numeric | G-X1 | count | 78.867 | 13.926 | 5.663× | `$.actor.login` |
| numeric | G-X2 | exists | 24.623 | 12.452 | 1.977× | `$.repo.id ? (@ > 0)` |
| numeric | G-X2 | count | 85.219 | 17.286 | 4.930× | `$.repo.id ? (@ > 0)` |
| numeric | G-X3 | exists | 20.946 | 10.909 | 1.920× | `$.payload.action` |
| numeric | G-X3 | count | 59.483 | 15.983 | 3.722× | `$.payload.action` |
| numeric | G-X4 | exists | 19.277 | 10.969 | 1.757× | `$.payload.issue.labels[*].name` |
| numeric | G-X4 | count | 57.616 | 13.741 | 4.193× | `$.payload.issue.labels[*].name` |
| numeric | G-X5 | exists | 22.274 | 11.831 | 1.883× | `$.payload.release.assets[*].uploader.login` |
| numeric | G-X5 | count | 58.026 | 14.419 | 4.024× | `$.payload.release.assets[*].uploader.login` |
| numeric | G-X6 | exists | 19.550 | 10.959 | 1.784× | `$.payload.release.assets[0].size ? (@ >= 1)` |
| numeric | G-X6 | count | 58.062 | 15.179 | 3.825× | `$.payload.release.assets[0].size ? (@ >= 1)` |
| numeric | G-X7 | exists | 31.040 | 13.138 | 2.363× | `$ ? (@.public == true && @.actor.id > 0)` |
| numeric | G-X7 | count | 91.761 | 17.580 | 5.220× | `$ ? (@.public == true && @.actor.id > 0)` |
| numeric | G-X8 | exists | 23.665 | 13.325 | 1.776× | `$ ? (@.type == "IssuesEvent" && exists(@.payload.issue.labels[*] ? (@.default == false && @.color != "")))` |
| numeric | G-X8 | count | 67.549 | 16.824 | 4.015× | `$ ? (@.type == "IssuesEvent" && exists(@.payload.issue.labels[*] ? (@.default == false && @.color != "")))` |
| numeric | G-X9 | exists | 22.024 | 10.451 | 2.107× | `$ ? (@.type == "IssuesEvent" && exists(@.payload.issue.issue_field_values[*] ? (@.issue_field_name != "" && exists(@.single_select_option.name))))` |
| numeric | G-X9 | count | 63.125 | 14.124 | 4.469× | `$ ? (@.type == "IssuesEvent" && exists(@.payload.issue.issue_field_values[*] ? (@.issue_field_name != "" && exists(@.single_select_option.name))))` |
| numeric | G-X10 | exists | 21.842 | 11.461 | 1.906× | `$ ? (@.type == "ReleaseEvent" && @.public == true && exists(@.payload.release.assets[*] ? (@.size > 0 && @.uploader.login != "")))` |
| numeric | G-X10 | count | 64.658 | 13.890 | 4.655× | `$ ? (@.type == "ReleaseEvent" && @.public == true && exists(@.payload.release.assets[*] ? (@.size > 0 && @.uploader.login != "")))` |
| numeric | G-X11 | exists | 20.261 | 11.459 | 1.768× | `$.payload.release.assets[last,0,last,1 to 2] ? (@.size >= 1).uploader.login` |
| numeric | G-X11 | count | 57.305 | 14.731 | 3.890× | `$.payload.release.assets[last,0,last,1 to 2] ? (@.size >= 1).uploader.login` |
| numeric | G-X12 | exists | 19.229 | 11.756 | 1.636× | `$.payload.issue.labels[last,0,last,0 to 2] ? (@.name != "").name` |
| numeric | G-X12 | count | 58.499 | 14.861 | 3.936× | `$.payload.issue.labels[last,0,last,0 to 2] ? (@.name != "").name` |
| numeric | G-X13 | exists | 18.414 | 12.066 | 1.526× | `$.payload.pages[last,0,last] ? (@.action != "").title` |
| numeric | G-X13 | count | 57.804 | 14.095 | 4.101× | `$.payload.pages[last,0,last] ? (@.action != "").title` |
| numeric | G-X14 | exists | 26.658 | 17.798 | 1.498× | `$ ? (exists(@.payload.issue.labels[*] ? (@.name like_regex "^bug$" flag "i")) \|\| exists(@.payload.release.assets[*] ? (@.content_type starts with "audio/")))` |
| numeric | G-X14 | count | 66.934 | 20.903 | 3.202× | `$ ? (exists(@.payload.issue.labels[*] ? (@.name like_regex "^bug$" flag "i")) \|\| exists(@.payload.release.assets[*] ? (@.content_type starts with "audio/")))` |
| numeric | G-X15 | exists | 23.777 | 13.197 | 1.802× | `$ ? (((@.org.id > 0) is unknown) && @.public == true)` |
| numeric | G-X15 | count | 64.397 | 15.635 | 4.119× | `$ ? (((@.org.id > 0) is unknown) && @.public == true)` |
| numeric | G-X16 | exists | 20.715 | 12.735 | 1.627× | `$.payload.release.assets[$.actor.id].uploader.login` |
| numeric | G-X16 | count | 58.354 | 15.566 | 3.749× | `$.payload.release.assets[$.actor.id].uploader.login` |
| numeric | G-X17 | exists | 23.144 | 13.946 | 1.660× | `$ ? (!exists(@.org) \|\| (@.org.login != "" && @.repo.name != ""))` |
| numeric | G-X17 | count | 80.931 | 16.000 | 5.058× | `$ ? (!exists(@.org) \|\| (@.org.login != "" && @.repo.name != ""))` |
| numeric | G-X18 | exists | 21.775 | 15.233 | 1.429× | `$.payload.issue.labels[*] ? (@.name != "") ? (@.color != "").name` |
| numeric | G-X18 | count | 61.155 | 16.316 | 3.748× | `$.payload.issue.labels[*] ? (@.name != "") ? (@.color != "").name` |
| numeric | G-X19 | exists | 19.406 | 11.178 | 1.736× | `$.payload.issue.reactions."+1" ? (@ > 0)` |
| numeric | G-X19 | count | 57.968 | 16.242 | 3.569× | `$.payload.issue.reactions."+1" ? (@ > 0)` |

#### openalex

| Schema | Query | Operation | JSONB (ms) | SpecSon (ms) | Speedup | JSONPath |
|---|---|---|---:|---:|---:|---|
| integer | O-X1 | exists | 392.951 | 125.588 | 3.129× | `$.id` |
| integer | O-X1 | count | 455.814 | 129.840 | 3.511× | `$.id` |
| integer | O-X2 | exists | 394.677 | 126.708 | 3.115× | `$.publication_year ? (@ >= 2020)` |
| integer | O-X2 | count | 459.827 | 136.746 | 3.363× | `$.publication_year ? (@ >= 2020)` |
| integer | O-X3 | exists | 394.012 | 147.153 | 2.678× | `$.counts_by_year[*].year` |
| integer | O-X3 | count | 454.305 | 151.919 | 2.990× | `$.counts_by_year[*].year` |
| integer | O-X4 | exists | 400.683 | 170.246 | 2.354× | `$.authorships[*].author.display_name` |
| integer | O-X4 | count | 505.283 | 178.164 | 2.836× | `$.authorships[*].author.display_name` |
| integer | O-X5 | exists | 403.720 | 193.061 | 2.091× | `$.authorships[0].institutions[*].country_code` |
| integer | O-X5 | count | 466.898 | 198.034 | 2.358× | `$.authorships[0].institutions[*].country_code` |
| integer | O-X6 | exists | 420.658 | 174.646 | 2.409× | `$.concepts[*] ? (@.score >= 0.5)` |
| integer | O-X6 | count | 548.972 | 189.751 | 2.893× | `$.concepts[*] ? (@.score >= 0.5)` |
| integer | O-X7 | exists | 398.237 | 176.360 | 2.258× | `$.locations[*].source.display_name` |
| integer | O-X7 | count | 458.716 | 176.708 | 2.596× | `$.locations[*].source.display_name` |
| integer | O-X8 | exists | 403.157 | 190.244 | 2.119× | `$.authorships[*].affiliations[*].institution_ids[*]` |
| integer | O-X8 | count | 527.085 | 211.218 | 2.495× | `$.authorships[*].affiliations[*].institution_ids[*]` |
| integer | O-X9 | exists | 401.710 | 165.616 | 2.426× | `$.topics[*] ? (@.id == "https://openalex.org/T11101" && @.score >= 0.1).display_name` |
| integer | O-X9 | count | 443.407 | 168.358 | 2.634× | `$.topics[*] ? (@.id == "https://openalex.org/T11101" && @.score >= 0.1).display_name` |
| integer | O-X10 | exists | 412.349 | 177.346 | 2.325× | `$.locations[*] ? (@.is_oa == true && @.is_published == true && @.source.is_in_doaj == true).source.display_name` |
| integer | O-X10 | count | 453.366 | 182.680 | 2.482× | `$.locations[*] ? (@.is_oa == true && @.is_published == true && @.source.is_in_doaj == true).source.display_name` |
| integer | O-X11 | exists | 423.320 | 187.577 | 2.257× | `$.authorships[*] ? (@.is_corresponding == true && exists(@.institutions[*] ? (@.country_code != null && exists(@.lineage[*] ? (@ starts with "https://openalex.org/I")))))` |
| integer | O-X11 | count | 463.722 | 190.616 | 2.433× | `$.authorships[*] ? (@.is_corresponding == true && exists(@.institutions[*] ? (@.country_code != null && exists(@.lineage[*] ? (@ starts with "https://openalex.org/I")))))` |
| integer | O-X12 | exists | 415.366 | 193.500 | 2.147× | `$.authorships[*] ? (exists(@.affiliations[*] ? (@.raw_affiliation_string != "" && exists(@.institution_ids[*] ? (@ starts with "https://openalex.org/I")))))` |
| integer | O-X12 | count | 574.874 | 225.993 | 2.544× | `$.authorships[*] ? (exists(@.affiliations[*] ? (@.raw_affiliation_string != "" && exists(@.institution_ids[*] ? (@ starts with "https://openalex.org/I")))))` |
| integer | O-X13 | exists | 442.626 | 204.167 | 2.168× | `$.authorships[*] ? (exists(@.institutions[*] ? (@.display_name != "" && exists(@.lineage[last,0,last] ? (@ != "")))))` |
| integer | O-X13 | count | 610.084 | 239.653 | 2.546× | `$.authorships[*] ? (exists(@.institutions[*] ? (@.display_name != "" && exists(@.lineage[last,0,last] ? (@ != "")))))` |
| integer | O-X14 | exists | 439.018 | 178.843 | 2.455× | `$.authorships[3,3,0,3,last] ? (@.author.id != null).author.display_name` |
| integer | O-X14 | count | 520.962 | 187.962 | 2.772× | `$.authorships[3,3,0,3,last] ? (@.author.id != null).author.display_name` |
| integer | O-X15 | exists | 430.668 | 219.078 | 1.966× | `$.authorships[*].institutions[last,0,last] ? (@.country_code != null).lineage[last,0]` |
| integer | O-X15 | count | 958.930 | 441.492 | 2.172× | `$.authorships[*].institutions[last,0,last] ? (@.country_code != null).lineage[last,0]` |
| integer | O-X16 | exists | 425.297 | 207.525 | 2.049× | `$.authorships[*].affiliations[*].institution_ids[last,0,last]` |
| integer | O-X16 | count | 677.058 | 274.320 | 2.468× | `$.authorships[*].affiliations[*].institution_ids[last,0,last]` |
| integer | O-X17 | exists | 431.231 | 154.581 | 2.790× | `$.counts_by_year[last,0,last,0 to 2] ? (@.year >= 2020).cited_by_count` |
| integer | O-X17 | count | 489.960 | 159.687 | 3.068× | `$.counts_by_year[last,0,last,0 to 2] ? (@.year >= 2020).cited_by_count` |
| integer | O-X18 | exists | 417.700 | 196.551 | 2.125× | `$.locations[*] ? (exists(@.source.issn[*] ? (@ starts with "0"))).source.display_name` |
| integer | O-X18 | count | 464.087 | 200.454 | 2.315× | `$.locations[*] ? (exists(@.source.issn[*] ? (@ starts with "0"))).source.display_name` |
| integer | O-X19 | exists | 416.994 | 181.770 | 2.294× | `$.locations[*] ? (((@.source.is_oa == true) is unknown)).id` |
| integer | O-X19 | count | 455.827 | 192.706 | 2.365× | `$.locations[*] ? (((@.source.is_oa == true) is unknown)).id` |
| integer | O-X20 | exists | 409.855 | 184.721 | 2.219× | `$.authorships[$.authors_count].author.id` |
| integer | O-X20 | count | 446.665 | 189.769 | 2.354× | `$.authorships[$.authors_count].author.id` |
| integer | O-X21 | exists | 415.558 | 141.614 | 2.934× | `$.title ? (@ like_regex "^a" flag "i")` |
| integer | O-X21 | count | 455.802 | 146.104 | 3.120× | `$.title ? (@ like_regex "^a" flag "i")` |
| integer | O-X22 | exists | 411.616 | 142.615 | 2.886× | `$.primary_topic ? (@.score >= 0.1 && exists(@.domain.id)).subfield.display_name` |
| integer | O-X22 | count | 463.552 | 149.737 | 3.096× | `$.primary_topic ? (@.score >= 0.1 && exists(@.domain.id)).subfield.display_name` |
| integer | O-X23 | exists | 463.084 | 223.524 | 2.072× | `$ ? (exists(@.topics[*] ? (@.score >= 0.8)) \|\| exists(@.concepts[*] ? (@.score >= 0.8)))` |
| integer | O-X23 | count | 535.520 | 222.563 | 2.406× | `$ ? (exists(@.topics[*] ? (@.score >= 0.8)) \|\| exists(@.concepts[*] ? (@.score >= 0.8)))` |
| integer | O-X24 | exists | 409.484 | 146.498 | 2.795× | `$.mesh[*] ? (@.is_major_topic == true && @.descriptor_name != "").qualifier_name` |
| integer | O-X24 | count | 468.384 | 152.671 | 3.068× | `$.mesh[*] ? (@.is_major_topic == true && @.descriptor_name != "").qualifier_name` |
| integer | O-X25 | exists | 411.624 | 187.308 | 2.198× | `$.counts_by_year[*] ? (@.year == $.publication_year).cited_by_count` |
| integer | O-X25 | count | 448.780 | 191.202 | 2.347× | `$.counts_by_year[*] ? (@.year == $.publication_year).cited_by_count` |
| integer | O-X26 | exists | 484.701 | 219.630 | 2.207× | `$.concepts[*] ? ((@.score * 10).floor() == 5).display_name` |
| integer | O-X26 | count | 640.155 | 264.891 | 2.417× | `$.concepts[*] ? ((@.score * 10).floor() == 5).display_name` |
| integer | O-X27 | exists | 415.954 | 156.069 | 2.665× | `$.counts_by_year[*] ? ((@.cited_by_count / 12) >= 1).year` |
| integer | O-X27 | count | 453.412 | 160.662 | 2.822× | `$.counts_by_year[*] ? ((@.cited_by_count / 12) >= 1).year` |
| numeric | O-X1 | exists | 411.686 | 136.587 | 3.014× | `$.id` |
| numeric | O-X1 | count | 476.161 | 140.672 | 3.385× | `$.id` |
| numeric | O-X2 | exists | 424.168 | 137.192 | 3.092× | `$.publication_year ? (@ >= 2020)` |
| numeric | O-X2 | count | 477.906 | 146.783 | 3.256× | `$.publication_year ? (@ >= 2020)` |
| numeric | O-X3 | exists | 415.270 | 156.793 | 2.649× | `$.counts_by_year[*].year` |
| numeric | O-X3 | count | 476.050 | 160.449 | 2.967× | `$.counts_by_year[*].year` |
| numeric | O-X4 | exists | 420.691 | 180.339 | 2.333× | `$.authorships[*].author.display_name` |
| numeric | O-X4 | count | 528.572 | 188.959 | 2.797× | `$.authorships[*].author.display_name` |
| numeric | O-X5 | exists | 427.917 | 202.673 | 2.111× | `$.authorships[0].institutions[*].country_code` |
| numeric | O-X5 | count | 488.889 | 208.311 | 2.347× | `$.authorships[0].institutions[*].country_code` |
| numeric | O-X6 | exists | 442.039 | 189.477 | 2.333× | `$.concepts[*] ? (@.score >= 0.5)` |
| numeric | O-X6 | count | 561.512 | 203.395 | 2.761× | `$.concepts[*] ? (@.score >= 0.5)` |
| numeric | O-X7 | exists | 422.361 | 186.425 | 2.266× | `$.locations[*].source.display_name` |
| numeric | O-X7 | count | 486.827 | 188.970 | 2.576× | `$.locations[*].source.display_name` |
| numeric | O-X8 | exists | 424.308 | 200.076 | 2.121× | `$.authorships[*].affiliations[*].institution_ids[*]` |
| numeric | O-X8 | count | 555.446 | 216.705 | 2.563× | `$.authorships[*].affiliations[*].institution_ids[*]` |
| numeric | O-X9 | exists | 428.306 | 172.643 | 2.481× | `$.topics[*] ? (@.id == "https://openalex.org/T11101" && @.score >= 0.1).display_name` |
| numeric | O-X9 | count | 466.538 | 178.472 | 2.614× | `$.topics[*] ? (@.id == "https://openalex.org/T11101" && @.score >= 0.1).display_name` |
| numeric | O-X10 | exists | 431.015 | 186.746 | 2.308× | `$.locations[*] ? (@.is_oa == true && @.is_published == true && @.source.is_in_doaj == true).source.display_name` |
| numeric | O-X10 | count | 476.210 | 192.327 | 2.476× | `$.locations[*] ? (@.is_oa == true && @.is_published == true && @.source.is_in_doaj == true).source.display_name` |
| numeric | O-X11 | exists | 443.995 | 197.485 | 2.248× | `$.authorships[*] ? (@.is_corresponding == true && exists(@.institutions[*] ? (@.country_code != null && exists(@.lineage[*] ? (@ starts with "https://openalex.org/I")))))` |
| numeric | O-X11 | count | 490.047 | 201.643 | 2.430× | `$.authorships[*] ? (@.is_corresponding == true && exists(@.institutions[*] ? (@.country_code != null && exists(@.lineage[*] ? (@ starts with "https://openalex.org/I")))))` |
| numeric | O-X12 | exists | 447.293 | 204.649 | 2.186× | `$.authorships[*] ? (exists(@.affiliations[*] ? (@.raw_affiliation_string != "" && exists(@.institution_ids[*] ? (@ starts with "https://openalex.org/I")))))` |
| numeric | O-X12 | count | 602.387 | 239.869 | 2.511× | `$.authorships[*] ? (exists(@.affiliations[*] ? (@.raw_affiliation_string != "" && exists(@.institution_ids[*] ? (@ starts with "https://openalex.org/I")))))` |
| numeric | O-X13 | exists | 442.278 | 208.184 | 2.124× | `$.authorships[*] ? (exists(@.institutions[*] ? (@.display_name != "" && exists(@.lineage[last,0,last] ? (@ != "")))))` |
| numeric | O-X13 | count | 612.967 | 254.968 | 2.404× | `$.authorships[*] ? (exists(@.institutions[*] ? (@.display_name != "" && exists(@.lineage[last,0,last] ? (@ != "")))))` |
| numeric | O-X14 | exists | 451.469 | 186.400 | 2.422× | `$.authorships[3,3,0,3,last] ? (@.author.id != null).author.display_name` |
| numeric | O-X14 | count | 537.838 | 194.099 | 2.771× | `$.authorships[3,3,0,3,last] ? (@.author.id != null).author.display_name` |
| numeric | O-X15 | exists | 445.021 | 224.868 | 1.979× | `$.authorships[*].institutions[last,0,last] ? (@.country_code != null).lineage[last,0]` |
| numeric | O-X15 | count | 972.785 | 427.907 | 2.273× | `$.authorships[*].institutions[last,0,last] ? (@.country_code != null).lineage[last,0]` |
| numeric | O-X16 | exists | 430.528 | 205.489 | 2.095× | `$.authorships[*].affiliations[*].institution_ids[last,0,last]` |
| numeric | O-X16 | count | 682.754 | 277.223 | 2.463× | `$.authorships[*].affiliations[*].institution_ids[last,0,last]` |
| numeric | O-X17 | exists | 433.807 | 163.205 | 2.658× | `$.counts_by_year[last,0,last,0 to 2] ? (@.year >= 2020).cited_by_count` |
| numeric | O-X17 | count | 495.999 | 163.918 | 3.026× | `$.counts_by_year[last,0,last,0 to 2] ? (@.year >= 2020).cited_by_count` |
| numeric | O-X18 | exists | 424.998 | 201.438 | 2.110× | `$.locations[*] ? (exists(@.source.issn[*] ? (@ starts with "0"))).source.display_name` |
| numeric | O-X18 | count | 470.059 | 205.557 | 2.287× | `$.locations[*] ? (exists(@.source.issn[*] ? (@ starts with "0"))).source.display_name` |
| numeric | O-X19 | exists | 423.250 | 190.846 | 2.218× | `$.locations[*] ? (((@.source.is_oa == true) is unknown)).id` |
| numeric | O-X19 | count | 459.386 | 195.158 | 2.354× | `$.locations[*] ? (((@.source.is_oa == true) is unknown)).id` |
| numeric | O-X20 | exists | 419.038 | 191.027 | 2.194× | `$.authorships[$.authors_count].author.id` |
| numeric | O-X20 | count | 457.205 | 194.408 | 2.352× | `$.authorships[$.authors_count].author.id` |
| numeric | O-X21 | exists | 424.394 | 145.851 | 2.910× | `$.title ? (@ like_regex "^a" flag "i")` |
| numeric | O-X21 | count | 471.047 | 150.095 | 3.138× | `$.title ? (@ like_regex "^a" flag "i")` |
| numeric | O-X22 | exists | 420.039 | 149.952 | 2.801× | `$.primary_topic ? (@.score >= 0.1 && exists(@.domain.id)).subfield.display_name` |
| numeric | O-X22 | count | 470.291 | 154.479 | 3.044× | `$.primary_topic ? (@.score >= 0.1 && exists(@.domain.id)).subfield.display_name` |
| numeric | O-X23 | exists | 458.946 | 228.215 | 2.011× | `$ ? (exists(@.topics[*] ? (@.score >= 0.8)) \|\| exists(@.concepts[*] ? (@.score >= 0.8)))` |
| numeric | O-X23 | count | 547.315 | 232.488 | 2.354× | `$ ? (exists(@.topics[*] ? (@.score >= 0.8)) \|\| exists(@.concepts[*] ? (@.score >= 0.8)))` |
| numeric | O-X24 | exists | 421.430 | 149.935 | 2.811× | `$.mesh[*] ? (@.is_major_topic == true && @.descriptor_name != "").qualifier_name` |
| numeric | O-X24 | count | 479.641 | 159.949 | 2.999× | `$.mesh[*] ? (@.is_major_topic == true && @.descriptor_name != "").qualifier_name` |
| numeric | O-X25 | exists | 428.423 | 194.738 | 2.200× | `$.counts_by_year[*] ? (@.year == $.publication_year).cited_by_count` |
| numeric | O-X25 | count | 464.592 | 203.433 | 2.284× | `$.counts_by_year[*] ? (@.year == $.publication_year).cited_by_count` |
| numeric | O-X26 | exists | 501.291 | 212.127 | 2.363× | `$.concepts[*] ? ((@.score * 10).floor() == 5).display_name` |
| numeric | O-X26 | count | 651.539 | 247.743 | 2.630× | `$.concepts[*] ? ((@.score * 10).floor() == 5).display_name` |
| numeric | O-X27 | exists | 426.268 | 160.677 | 2.653× | `$.counts_by_year[*] ? ((@.cited_by_count / 12) >= 1).year` |
| numeric | O-X27 | count | 468.073 | 167.811 | 2.789× | `$.counts_by_year[*] ? ((@.cited_by_count / 12) >= 1).year` |

#### synthetic-array-shape-1x2000

| Schema | Query | Operation | JSONB (ms) | SpecSon (ms) | Speedup | JSONPath |
|---|---|---|---:|---:|---:|---|
| numeric | shape1-X1 | exists | 109.825 | 17.449 | 6.294× | `$.id` |
| numeric | shape1-X1 | count | 115.279 | 17.483 | 6.594× | `$.id` |
| numeric | shape1-X2 | exists | 111.480 | 18.255 | 6.107× | `$.target[0][0]` |
| numeric | shape1-X2 | count | 115.488 | 17.926 | 6.442× | `$.target[0][0]` |
| numeric | shape1-X3 | exists | 111.905 | 18.526 | 6.041× | `$.target[0][1999]` |
| numeric | shape1-X3 | count | 116.475 | 18.342 | 6.350× | `$.target[0][1999]` |
| numeric | shape1-X4 | exists | 110.846 | 17.687 | 6.267× | `$.target[0][0 to 7]` |
| numeric | shape1-X4 | count | 124.147 | 19.295 | 6.434× | `$.target[0][0 to 7]` |
| numeric | shape1-X5 | exists | 112.448 | 87.546 | 1.284× | `$.target[0][*] ? (@ < 0.0)` |
| numeric | shape1-X5 | count | 1895.038 | 390.550 | 4.852× | `$.target[0][*] ? (@ < 0.0)` |
| numeric | shape1-X6 | exists | 111.020 | 17.926 | 6.193× | `$.target[*][last]` |
| numeric | shape1-X6 | count | 116.313 | 19.382 | 6.001× | `$.target[*][last]` |
| numeric | shape1-X7 | exists | 111.677 | 17.982 | 6.210× | `$.target[0][1999,0,1999,0 to 3]` |
| numeric | shape1-X7 | count | 124.291 | 19.705 | 6.308× | `$.target[0][1999,0,1999,0 to 3]` |
| numeric | shape1-X8 | exists | 111.403 | 19.159 | 5.815× | `$.target[last][last - 1,last,0]` |
| numeric | shape1-X8 | count | 120.217 | 19.930 | 6.032× | `$.target[last][last - 1,last,0]` |
| numeric | shape1-X9 | exists | 113.221 | 91.017 | 1.244× | `$.target[*] ? (exists(@[last,0] ? (@ < 0.0)))` |
| numeric | shape1-X9 | count | 3927.914 | 3066.442 | 1.281× | `$.target[*] ? (exists(@[last,0] ? (@ < 0.0)))` |
| numeric | shape1-X10 | exists | 111.989 | 87.002 | 1.287× | `$.target[*][*] ? (@ >= 0.0 && @ < 1000000000000.0)` |
| numeric | shape1-X10 | count | 2352.735 | 510.473 | 4.609× | `$.target[*][*] ? (@ >= 0.0 && @ < 1000000000000.0)` |
| numeric | shape1-X11 | exists | 110.865 | 88.092 | 1.259× | `$.target[*][*] ? ((@ == "not-a-number") is unknown)` |
| numeric | shape1-X11 | count | 2941.960 | 333.528 | 8.821× | `$.target[*][*] ? ((@ == "not-a-number") is unknown)` |
| numeric | shape1-X12 | exists | 110.791 | 18.077 | 6.129× | `$.target[0][1000 to 1007,1000,999]` |
| numeric | shape1-X12 | count | 126.428 | 18.580 | 6.805× | `$.target[0][1000 to 1007,1000,999]` |
| numeric | shape1-X13 | exists | 112.035 | 88.306 | 1.269× | `$.target[0][*] ? (@ >= 0.0) ? (@ < 1000000000000.0)` |
| numeric | shape1-X13 | count | 2326.130 | 953.954 | 2.438× | `$.target[0][*] ? (@ >= 0.0) ? (@ < 1000000000000.0)` |
| numeric | shape1-X14 | exists | 112.785 | 19.757 | 5.709× | `$.target[0][last - 7 to last]` |
| numeric | shape1-X14 | count | 124.198 | 19.693 | 6.307× | `$.target[0][last - 7 to last]` |

#### synthetic-array-shape-2000x1

| Schema | Query | Operation | JSONB (ms) | SpecSon (ms) | Speedup | JSONPath |
|---|---|---|---:|---:|---:|---|
| numeric | shape2-X1 | exists | 125.363 | 17.965 | 6.978× | `$.id` |
| numeric | shape2-X1 | count | 130.714 | 18.870 | 6.927× | `$.id` |
| numeric | shape2-X2 | exists | 125.840 | 18.706 | 6.727× | `$.target[0][0]` |
| numeric | shape2-X2 | count | 132.590 | 19.211 | 6.902× | `$.target[0][0]` |
| numeric | shape2-X3 | exists | 125.725 | 18.060 | 6.962× | `$.target[1999][0]` |
| numeric | shape2-X3 | count | 132.710 | 18.022 | 7.364× | `$.target[1999][0]` |
| numeric | shape2-X4 | exists | 126.365 | 17.922 | 7.051× | `$.target[0 to 7][0]` |
| numeric | shape2-X4 | count | 142.674 | 19.645 | 7.263× | `$.target[0 to 7][0]` |
| numeric | shape2-X5 | exists | 127.902 | 87.239 | 1.466× | `$.target[*][0] ? (@ < 0.0)` |
| numeric | shape2-X5 | count | 2794.160 | 389.954 | 7.165× | `$.target[*][0] ? (@ < 0.0)` |
| numeric | shape2-X6 | exists | 127.049 | 18.497 | 6.869× | `$.target[last][*]` |
| numeric | shape2-X6 | count | 131.805 | 18.393 | 7.166× | `$.target[last][*]` |
| numeric | shape2-X7 | exists | 126.163 | 18.559 | 6.798× | `$.target[1999,0,1999,0 to 3][0]` |
| numeric | shape2-X7 | count | 142.037 | 19.147 | 7.418× | `$.target[1999,0,1999,0 to 3][0]` |
| numeric | shape2-X8 | exists | 126.354 | 18.384 | 6.873× | `$.target[last,last - 1,0][last]` |
| numeric | shape2-X8 | count | 139.960 | 21.449 | 6.525× | `$.target[last,last - 1,0][last]` |
| numeric | shape2-X9 | exists | 129.220 | 90.042 | 1.435× | `$.target[*] ? (exists(@[0] ? (@ < 0.0)))` |
| numeric | shape2-X9 | count | 3454.701 | 3481.362 | 0.992× | `$.target[*] ? (exists(@[0] ? (@ < 0.0)))` |
| numeric | shape2-X10 | exists | 129.298 | 89.133 | 1.451× | `$.target[*][*] ? (@ >= 0.0 && @ < 1000000000000.0)` |
| numeric | shape2-X10 | count | 2847.181 | 516.966 | 5.507× | `$.target[*][*] ? (@ >= 0.0 && @ < 1000000000000.0)` |
| numeric | shape2-X11 | exists | 127.327 | 86.917 | 1.465× | `$.target[*][*] ? ((@ == "not-a-number") is unknown)` |
| numeric | shape2-X11 | count | 3395.121 | 334.704 | 10.144× | `$.target[*][*] ? ((@ == "not-a-number") is unknown)` |
| numeric | shape2-X12 | exists | 126.617 | 17.247 | 7.342× | `$.target[1000 to 1007,1000,999][0]` |
| numeric | shape2-X12 | count | 145.777 | 19.180 | 7.600× | `$.target[1000 to 1007,1000,999][0]` |
| numeric | shape2-X13 | exists | 127.687 | 89.991 | 1.419× | `$.target[*][0] ? (@ >= 0.0) ? (@ < 1000000000000.0)` |
| numeric | shape2-X13 | count | 3248.459 | 2635.021 | 1.233× | `$.target[*][0] ? (@ >= 0.0) ? (@ < 1000000000000.0)` |
| numeric | shape2-X14 | exists | 130.437 | 19.489 | 6.693× | `$.target[last - 7 to last][0]` |
| numeric | shape2-X14 | count | 143.080 | 21.073 | 6.790× | `$.target[last - 7 to last][0]` |

#### synthetic-rank-4

| Schema | Query | Operation | JSONB (ms) | SpecSon (ms) | Speedup | JSONPath |
|---|---|---|---:|---:|---:|---|
| numeric | rank-X1 | exists | 646.647 | 185.341 | 3.489× | `$.id` |
| numeric | rank-X1 | count | 704.443 | 189.890 | 3.710× | `$.id` |
| numeric | rank-X2 | exists | 663.590 | 194.757 | 3.407× | `$.target[0][0][0][0]` |
| numeric | rank-X2 | count | 722.221 | 197.349 | 3.660× | `$.target[0][0][0][0]` |
| numeric | rank-X3 | exists | 668.037 | 191.649 | 3.486× | `$.target[3][3][7][7]` |
| numeric | rank-X3 | count | 725.627 | 197.936 | 3.666× | `$.target[3][3][7][7]` |
| numeric | rank-X4 | exists | 663.791 | 194.060 | 3.421× | `$.target[1][*][0][*]` |
| numeric | rank-X4 | count | 1001.407 | 200.255 | 5.001× | `$.target[1][*][0][*]` |
| numeric | rank-X5 | exists | 697.860 | 497.274 | 1.403× | `$.target[*][0][0][0] ? (@ < 0.0)` |
| numeric | rank-X5 | count | 793.739 | 510.300 | 1.555× | `$.target[*][0][0][0] ? (@ < 0.0)` |
| numeric | rank-X6 | exists | 668.592 | 190.886 | 3.503× | `$.target[0][0][0][0 to 3]` |
| numeric | rank-X6 | count | 751.189 | 200.799 | 3.741× | `$.target[0][0][0][0 to 3]` |
| numeric | rank-X7 | exists | 673.598 | 192.991 | 3.490× | `$.target[last][last][last][last]` |
| numeric | rank-X7 | count | 731.762 | 198.526 | 3.686× | `$.target[last][last][last][last]` |
| numeric | rank-X8 | exists | 674.273 | 194.189 | 3.472× | `$.target[3,0,3,1 to 2][3,0,3][7,0,7][7,0,7]` |
| numeric | rank-X8 | count | 2685.698 | 292.251 | 9.190× | `$.target[3,0,3,1 to 2][3,0,3][7,0,7][7,0,7]` |
| numeric | rank-X9 | exists | 679.709 | 195.284 | 3.481× | `$.target[0 to 2,1 to 3,0][0][0][0]` |
| numeric | rank-X9 | count | 889.826 | 204.459 | 4.352× | `$.target[0 to 2,1 to 3,0][0][0][0]` |
| numeric | rank-X10 | exists | 698.289 | 231.593 | 3.015× | `$.target[last - 1,last,0][last,0][last,0][last,0]` |
| numeric | rank-X10 | count | 1175.013 | 246.529 | 4.766× | `$.target[last - 1,last,0][last,0][last,0][last,0]` |
| numeric | rank-X11 | exists | 708.420 | 567.828 | 1.248× | `$.target[*] ? (exists(@[*] ? (exists(@[*] ? (exists(@[*] ? (@ < 0.0)))))))` |
| numeric | rank-X11 | count | 1213.621 | 1209.709 | 1.003× | `$.target[*] ? (exists(@[*] ? (exists(@[*] ? (exists(@[*] ? (@ < 0.0)))))))` |
| numeric | rank-X12 | exists | 4733.870 | 1703.652 | 2.779× | `$.target[*][*][*][*] ? (@ >= 0.0 && @ < 1000000000.0)` |
| numeric | rank-X12 | count | 8008.338 | 2732.220 | 2.931× | `$.target[*][*][*][*] ? (@ >= 0.0 && @ < 1000000000.0)` |
| numeric | rank-X13 | exists | 663.735 | 493.332 | 1.345× | `$.target[*][*][*][*] ? ((@ == "not-a-number") is unknown)` |
| numeric | rank-X13 | count | 14586.478 | 1763.562 | 8.271× | `$.target[*][*][*][*] ? ((@ == "not-a-number") is unknown)` |
| numeric | rank-X14 | exists | 677.520 | 504.176 | 1.344× | `$.target[*][*][*][*] ? (@ < 0.0 \|\| @ > 1000000000000.0)` |
| numeric | rank-X14 | count | 12344.452 | 2657.506 | 4.645× | `$.target[*][*][*][*] ? (@ < 0.0 \|\| @ > 1000000000000.0)` |
| numeric | rank-X15 | exists | 1295.920 | 1144.279 | 1.133× | `$.target[*] ? (!exists(@[0] ? (exists(@[0] ? (exists(@[0] ? (@ < 0.0)))))))` |
| numeric | rank-X15 | count | 1360.320 | 1171.407 | 1.161× | `$.target[*] ? (!exists(@[0] ? (exists(@[0] ? (exists(@[0] ? (@ < 0.0)))))))` |

#### synthetic-width-1

| Schema | Query | Operation | JSONB (ms) | SpecSon (ms) | Speedup | JSONPath |
|---|---|---|---:|---:|---:|---|
| numeric | width-X1 | exists | 0.677 | 0.476 | 1.422× | `$.id` |
| numeric | width-X1 | count | 5.890 | 0.572 | 10.304× | `$.id` |
| numeric | width-X2 | exists | 0.728 | 0.413 | 1.766× | `$.target` |
| numeric | width-X2 | count | 5.298 | 0.567 | 9.337× | `$.target` |
| numeric | width-X3 | exists | 0.897 | 0.449 | 1.996× | `$.target.field_000` |
| numeric | width-X3 | count | 6.107 | 0.666 | 9.164× | `$.target.field_000` |
| numeric | width-X4 | exists | 1.261 | 0.431 | 2.923× | `$.target.field_000 ? (@ < 0.0)` |
| numeric | width-X4 | count | 5.406 | 0.938 | 5.763× | `$.target.field_000 ? (@ < 0.0)` |
| numeric | width-X5 | exists | 1.100 | 0.501 | 2.197× | `$ ? (@.id < 0.0)` |
| numeric | width-X5 | count | 5.506 | 0.874 | 6.301× | `$ ? (@.id < 0.0)` |
| numeric | width-X6 | exists | 1.455 | 0.539 | 2.698× | `$ ? (@.id < 0.0 && @.target.field_000 >= 0.0)` |
| numeric | width-X6 | count | 5.691 | 0.796 | 7.153× | `$ ? (@.id < 0.0 && @.target.field_000 >= 0.0)` |
| numeric | width-X7 | exists | 1.374 | 0.591 | 2.323× | `$.target ? (@.field_000 >= 0.0).field_000` |
| numeric | width-X7 | count | 6.461 | 0.706 | 9.146× | `$.target ? (@.field_000 >= 0.0).field_000` |
| numeric | width-X8 | exists | 1.715 | 0.611 | 2.808× | `$ ? (exists(@.target.field_000 ? (@ < 0.0 \|\| @ > 1000000000000.0)))` |
| numeric | width-X8 | count | 5.808 | 0.877 | 6.624× | `$ ? (exists(@.target.field_000 ? (@ < 0.0 \|\| @ > 1000000000000.0)))` |
| numeric | width-X9 | exists | 1.512 | 0.614 | 2.462× | `$.target.field_000 ? ((@ == "not-a-number") is unknown)` |
| numeric | width-X9 | count | 6.640 | 0.946 | 7.016× | `$.target.field_000 ? ((@ == "not-a-number") is unknown)` |
| numeric | width-X10 | exists | 1.519 | 0.598 | 2.541× | `$ ? (@.id < 0.0 \|\| @.target.field_000 > 0.0)` |
| numeric | width-X10 | count | 6.368 | 0.778 | 8.185× | `$ ? (@.id < 0.0 \|\| @.target.field_000 > 0.0)` |
| numeric | width-X11 | exists | 1.564 | 0.561 | 2.790× | `$.target.field_000 ? (@ >= 0.0 && @ < 1000000000000.0)` |
| numeric | width-X11 | count | 6.850 | 1.030 | 6.650× | `$.target.field_000 ? (@ >= 0.0 && @ < 1000000000000.0)` |
| numeric | width-X12 | exists | 1.120 | 0.435 | 2.575× | `$.target ? (!exists(@.missing)).field_000` |
| numeric | width-X12 | count | 6.418 | 0.909 | 7.058× | `$.target ? (!exists(@.missing)).field_000` |

#### yelp-business

| Schema | Query | Operation | JSONB (ms) | SpecSon (ms) | Speedup | JSONPath |
|---|---|---|---:|---:|---:|---|
| integer | YB-X1 | exists | 21.735 | 11.693 | 1.859× | `$.name` |
| integer | YB-X1 | count | 82.664 | 12.346 | 6.696× | `$.name` |
| integer | YB-X2 | exists | 22.407 | 9.929 | 2.257× | `$.hours.Monday` |
| integer | YB-X2 | count | 78.445 | 13.606 | 5.765× | `$.hours.Monday` |
| integer | YB-X3 | exists | 25.402 | 11.759 | 2.160× | `$.attributes.WiFi` |
| integer | YB-X3 | count | 71.995 | 13.746 | 5.238× | `$.attributes.WiFi` |
| integer | YB-X4 | exists | 25.589 | 11.264 | 2.272× | `$.latitude ? (@ > 0.0)` |
| integer | YB-X4 | count | 87.052 | 15.593 | 5.583× | `$.latitude ? (@ > 0.0)` |
| integer | YB-X5 | exists | 24.471 | 10.837 | 2.258× | `$ ? (exists(@.hours.Friday) \|\| exists(@.hours.Sunday))` |
| integer | YB-X5 | count | 83.093 | 13.278 | 6.258× | `$ ? (exists(@.hours.Friday) \|\| exists(@.hours.Sunday))` |
| integer | YB-X6 | exists | 28.277 | 10.463 | 2.702× | `$ ? (@.review_count >= 10 && @.stars >= 3.5)` |
| integer | YB-X6 | count | 80.852 | 14.181 | 5.701× | `$ ? (@.review_count >= 10 && @.stars >= 3.5)` |
| integer | YB-X7 | exists | 25.439 | 10.265 | 2.478× | `$.attributes ? (@.OutdoorSeating == "True")` |
| integer | YB-X7 | count | 69.194 | 14.328 | 4.829× | `$.attributes ? (@.OutdoorSeating == "True")` |
| integer | YB-X8 | exists | 35.112 | 12.116 | 2.898× | `$ ? (@.is_open == 1 && @.stars >= 4.0 && exists(@.hours.Saturday) && @.attributes.RestaurantsTakeOut == "True")` |
| integer | YB-X8 | count | 80.743 | 16.038 | 5.034× | `$ ? (@.is_open == 1 && @.stars >= 4.0 && exists(@.hours.Saturday) && @.attributes.RestaurantsTakeOut == "True")` |
| integer | YB-X9 | exists | 29.347 | 11.612 | 2.527× | `$ ? (exists(@.hours.Friday) && (exists(@.hours.Sunday) \|\| exists(@.hours.Saturday)))` |
| integer | YB-X9 | count | 85.251 | 12.940 | 6.588× | `$ ? (exists(@.hours.Friday) && (exists(@.hours.Sunday) \|\| exists(@.hours.Saturday)))` |
| integer | YB-X10 | exists | 26.200 | 10.004 | 2.619× | `$.hours ? (exists(@.Monday) && exists(@.Friday)).Sunday` |
| integer | YB-X10 | count | 80.218 | 14.478 | 5.541× | `$.hours ? (exists(@.Monday) && exists(@.Friday)).Sunday` |
| integer | YB-X11 | exists | 30.762 | 12.142 | 2.534× | `$.attributes ? (@.OutdoorSeating == "True" && @.RestaurantsTakeOut == "True").WiFi` |
| integer | YB-X11 | count | 73.385 | 13.764 | 5.332× | `$.attributes ? (@.OutdoorSeating == "True" && @.RestaurantsTakeOut == "True").WiFi` |
| integer | YB-X12 | exists | 70.068 | 21.656 | 3.236× | `$.categories ? (@ like_regex "restaurant" flag "i")` |
| integer | YB-X12 | count | 131.519 | 22.356 | 5.883× | `$.categories ? (@ like_regex "restaurant" flag "i")` |
| integer | YB-X13 | exists | 23.627 | 10.095 | 2.341× | `$.name ? (@ starts with "A")` |
| integer | YB-X13 | count | 65.228 | 16.766 | 3.890× | `$.name ? (@ starts with "A")` |
| integer | YB-X14 | exists | 30.610 | 12.171 | 2.515× | `$ ? (((@.attributes.OutdoorSeating == true) is unknown) && @.is_open == 1)` |
| integer | YB-X14 | count | 75.504 | 15.486 | 4.875× | `$ ? (((@.attributes.OutdoorSeating == true) is unknown) && @.is_open == 1)` |
| integer | YB-X15 | exists | 27.933 | 10.225 | 2.732× | `$ ? (@.stars >= 3.5) ? (@.review_count >= 100).name` |
| integer | YB-X15 | count | 73.018 | 14.936 | 4.889× | `$ ? (@.stars >= 3.5) ? (@.review_count >= 100).name` |
| integer | YB-X16 | exists | 29.835 | 12.601 | 2.368× | `$ ? (!exists(@.hours.Sunday) \|\| @.hours.Sunday != "").business_id` |
| integer | YB-X16 | count | 91.549 | 14.583 | 6.278× | `$ ? (!exists(@.hours.Sunday) \|\| @.hours.Sunday != "").business_id` |
| integer | YB-X17 | exists | 41.005 | 11.102 | 3.694× | `$ ? (@.latitude > 0.0 && @.longitude < 0.0 && @.review_count >= 10).name` |
| integer | YB-X17 | count | 95.883 | 12.735 | 7.529× | `$ ? (@.latitude > 0.0 && @.longitude < 0.0 && @.review_count >= 10).name` |
| integer | YB-X18 | exists | 28.099 | 10.965 | 2.563× | `$.attributes ? (exists(@.WiFi) && !exists(@.AcceptsInsurance)).RestaurantsPriceRange2` |
| integer | YB-X18 | count | 74.381 | 14.701 | 5.059× | `$.attributes ? (exists(@.WiFi) && !exists(@.AcceptsInsurance)).RestaurantsPriceRange2` |
| integer | YB-X19 | exists | 31.945 | 14.429 | 2.214× | `$ ? ((@.stars * @.review_count) >= 400).business_id` |
| integer | YB-X19 | count | 76.094 | 16.339 | 4.657× | `$ ? ((@.stars * @.review_count) >= 400).business_id` |
| integer | YB-X20 | exists | 26.668 | 14.557 | 1.832× | `$ ? (@.longitude.abs() >= 100.0).business_id` |
| integer | YB-X20 | count | 73.302 | 17.989 | 4.075× | `$ ? (@.longitude.abs() >= 100.0).business_id` |
| integer | YB-X21 | exists | 29.226 | 13.756 | 2.125× | `$ ? (@.stars.ceiling() == 4.0).business_id` |
| integer | YB-X21 | count | 79.770 | 17.100 | 4.665× | `$ ? (@.stars.ceiling() == 4.0).business_id` |
| numeric | YB-X1 | exists | 19.111 | 9.803 | 1.950× | `$.name` |
| numeric | YB-X1 | count | 77.280 | 10.814 | 7.146× | `$.name` |
| numeric | YB-X2 | exists | 20.132 | 10.029 | 2.007× | `$.hours.Monday` |
| numeric | YB-X2 | count | 75.948 | 13.996 | 5.426× | `$.hours.Monday` |
| numeric | YB-X3 | exists | 21.238 | 10.439 | 2.034× | `$.attributes.WiFi` |
| numeric | YB-X3 | count | 69.206 | 15.117 | 4.578× | `$.attributes.WiFi` |
| numeric | YB-X4 | exists | 22.312 | 10.415 | 2.142× | `$.latitude ? (@ > 0.0)` |
| numeric | YB-X4 | count | 85.157 | 14.890 | 5.719× | `$.latitude ? (@ > 0.0)` |
| numeric | YB-X5 | exists | 22.906 | 10.916 | 2.098× | `$ ? (exists(@.hours.Friday) \|\| exists(@.hours.Sunday))` |
| numeric | YB-X5 | count | 82.530 | 14.716 | 5.608× | `$ ? (exists(@.hours.Friday) \|\| exists(@.hours.Sunday))` |
| numeric | YB-X6 | exists | 29.174 | 12.567 | 2.321× | `$ ? (@.review_count >= 10 && @.stars >= 3.5)` |
| numeric | YB-X6 | count | 80.786 | 16.059 | 5.030× | `$ ? (@.review_count >= 10 && @.stars >= 3.5)` |
| numeric | YB-X7 | exists | 24.603 | 10.589 | 2.323× | `$.attributes ? (@.OutdoorSeating == "True")` |
| numeric | YB-X7 | count | 70.263 | 12.732 | 5.519× | `$.attributes ? (@.OutdoorSeating == "True")` |
| numeric | YB-X8 | exists | 34.035 | 12.546 | 2.713× | `$ ? (@.is_open == 1 && @.stars >= 4.0 && exists(@.hours.Saturday) && @.attributes.RestaurantsTakeOut == "True")` |
| numeric | YB-X8 | count | 79.747 | 16.213 | 4.919× | `$ ? (@.is_open == 1 && @.stars >= 4.0 && exists(@.hours.Saturday) && @.attributes.RestaurantsTakeOut == "True")` |
| numeric | YB-X9 | exists | 28.756 | 11.360 | 2.531× | `$ ? (exists(@.hours.Friday) && (exists(@.hours.Sunday) \|\| exists(@.hours.Saturday)))` |
| numeric | YB-X9 | count | 84.820 | 15.644 | 5.422× | `$ ? (exists(@.hours.Friday) && (exists(@.hours.Sunday) \|\| exists(@.hours.Saturday)))` |
| numeric | YB-X10 | exists | 26.843 | 12.441 | 2.158× | `$.hours ? (exists(@.Monday) && exists(@.Friday)).Sunday` |
| numeric | YB-X10 | count | 78.868 | 14.957 | 5.273× | `$.hours ? (exists(@.Monday) && exists(@.Friday)).Sunday` |
| numeric | YB-X11 | exists | 27.038 | 10.796 | 2.504× | `$.attributes ? (@.OutdoorSeating == "True" && @.RestaurantsTakeOut == "True").WiFi` |
| numeric | YB-X11 | count | 72.043 | 15.159 | 4.752× | `$.attributes ? (@.OutdoorSeating == "True" && @.RestaurantsTakeOut == "True").WiFi` |
| numeric | YB-X12 | exists | 68.158 | 19.570 | 3.483× | `$.categories ? (@ like_regex "restaurant" flag "i")` |
| numeric | YB-X12 | count | 127.962 | 21.705 | 5.896× | `$.categories ? (@ like_regex "restaurant" flag "i")` |
| numeric | YB-X13 | exists | 22.110 | 9.708 | 2.277× | `$.name ? (@ starts with "A")` |
| numeric | YB-X13 | count | 64.826 | 16.245 | 3.991× | `$.name ? (@ starts with "A")` |
| numeric | YB-X14 | exists | 28.421 | 11.551 | 2.461× | `$ ? (((@.attributes.OutdoorSeating == true) is unknown) && @.is_open == 1)` |
| numeric | YB-X14 | count | 75.468 | 16.087 | 4.691× | `$ ? (((@.attributes.OutdoorSeating == true) is unknown) && @.is_open == 1)` |
| numeric | YB-X15 | exists | 29.709 | 11.609 | 2.559× | `$ ? (@.stars >= 3.5) ? (@.review_count >= 100).name` |
| numeric | YB-X15 | count | 71.869 | 14.653 | 4.905× | `$ ? (@.stars >= 3.5) ? (@.review_count >= 100).name` |
| numeric | YB-X16 | exists | 32.727 | 14.418 | 2.270× | `$ ? (!exists(@.hours.Sunday) \|\| @.hours.Sunday != "").business_id` |
| numeric | YB-X16 | count | 91.136 | 14.864 | 6.131× | `$ ? (!exists(@.hours.Sunday) \|\| @.hours.Sunday != "").business_id` |
| numeric | YB-X17 | exists | 39.684 | 15.336 | 2.588× | `$ ? (@.latitude > 0.0 && @.longitude < 0.0 && @.review_count >= 10).name` |
| numeric | YB-X17 | count | 95.726 | 18.533 | 5.165× | `$ ? (@.latitude > 0.0 && @.longitude < 0.0 && @.review_count >= 10).name` |
| numeric | YB-X18 | exists | 29.559 | 13.179 | 2.243× | `$.attributes ? (exists(@.WiFi) && !exists(@.AcceptsInsurance)).RestaurantsPriceRange2` |
| numeric | YB-X18 | count | 77.799 | 16.699 | 4.659× | `$.attributes ? (exists(@.WiFi) && !exists(@.AcceptsInsurance)).RestaurantsPriceRange2` |
| numeric | YB-X19 | exists | 35.882 | 17.925 | 2.002× | `$ ? ((@.stars * @.review_count) >= 400).business_id` |
| numeric | YB-X19 | count | 82.369 | 18.320 | 4.496× | `$ ? ((@.stars * @.review_count) >= 400).business_id` |
| numeric | YB-X20 | exists | 25.589 | 13.438 | 1.904× | `$ ? (@.longitude.abs() >= 100.0).business_id` |
| numeric | YB-X20 | count | 72.177 | 15.798 | 4.569× | `$ ? (@.longitude.abs() >= 100.0).business_id` |
| numeric | YB-X21 | exists | 29.732 | 15.476 | 1.921× | `$ ? (@.stars.ceiling() == 4.0).business_id` |
| numeric | YB-X21 | count | 77.430 | 15.831 | 4.891× | `$ ? (@.stars.ceiling() == 4.0).business_id` |

#### yelp-review

| Schema | Query | Operation | JSONB (ms) | SpecSon (ms) | Speedup | JSONPath |
|---|---|---|---:|---:|---:|---|
| integer | YR-X1 | exists | 16.716 | 13.008 | 1.285× | `$.review_id` |
| integer | YR-X1 | count | 77.332 | 15.720 | 4.919× | `$.review_id` |
| integer | YR-X2 | exists | 21.751 | 12.979 | 1.676× | `$.stars ? (@ >= 3.5)` |
| integer | YR-X2 | count | 77.881 | 18.371 | 4.239× | `$.stars ? (@ >= 3.5)` |
| integer | YR-X3 | exists | 20.956 | 13.357 | 1.569× | `$.text ? (@ != "")` |
| integer | YR-X3 | count | 84.341 | 17.828 | 4.731× | `$.text ? (@ != "")` |
| integer | YR-X4 | exists | 26.448 | 13.616 | 1.942× | `$ ? (@.cool >= 1 \|\| @.funny >= 1)` |
| integer | YR-X4 | count | 73.718 | 16.157 | 4.563× | `$ ? (@.cool >= 1 \|\| @.funny >= 1)` |
| integer | YR-X5 | exists | 23.692 | 13.707 | 1.728× | `$ ? (@.useful >= 2 && @.stars < 4.0)` |
| integer | YR-X5 | count | 65.746 | 15.356 | 4.281× | `$ ? (@.useful >= 2 && @.stars < 4.0)` |
| integer | YR-X6 | exists | 19.832 | 12.361 | 1.604× | `$ ? (@.date >= "2020-01-01 00:00:00")` |
| integer | YR-X6 | count | 59.976 | 15.835 | 3.788× | `$ ? (@.date >= "2020-01-01 00:00:00")` |
| integer | YR-X7 | exists | 21.251 | 12.666 | 1.678× | `$.business_id ? (@ != "")` |
| integer | YR-X7 | count | 82.395 | 17.682 | 4.660× | `$.business_id ? (@ != "")` |
| integer | YR-X8 | exists | 27.273 | 14.359 | 1.899× | `$ ? (@.useful >= 1 && (@.cool >= 1 \|\| @.funny >= 1)).review_id` |
| integer | YR-X8 | count | 73.990 | 16.849 | 4.391× | `$ ? (@.useful >= 1 && (@.cool >= 1 \|\| @.funny >= 1)).review_id` |
| integer | YR-X9 | exists | 94.679 | 24.106 | 3.928× | `$ ? (@.stars >= 4.0 && @.text like_regex "good" flag "i").business_id` |
| integer | YR-X9 | count | 143.784 | 27.168 | 5.292× | `$ ? (@.stars >= 4.0 && @.text like_regex "good" flag "i").business_id` |
| integer | YR-X10 | exists | 19.929 | 12.723 | 1.566× | `$.text ? (@ starts with "A")` |
| integer | YR-X10 | count | 59.783 | 19.241 | 3.107× | `$.text ? (@ starts with "A")` |
| integer | YR-X11 | exists | 28.729 | 15.057 | 1.908× | `$ ? (@.stars >= 3.0) ? (@.useful >= 1) ? (@.cool >= 0).review_id` |
| integer | YR-X11 | count | 78.614 | 17.194 | 4.572× | `$ ? (@.stars >= 3.0) ? (@.useful >= 1) ? (@.cool >= 0).review_id` |
| integer | YR-X12 | exists | 29.960 | 14.260 | 2.101× | `$ ? (((@.stars == "five") is unknown) && @.useful >= 0).review_id` |
| integer | YR-X12 | count | 91.980 | 16.411 | 5.605× | `$ ? (((@.stars == "five") is unknown) && @.useful >= 0).review_id` |
| integer | YR-X13 | exists | 36.489 | 15.263 | 2.391× | `$ ? (!(@.useful < 0 \|\| @.cool < 0 \|\| @.funny < 0)).user_id` |
| integer | YR-X13 | count | 99.743 | 17.192 | 5.802× | `$ ? (!(@.useful < 0 \|\| @.cool < 0 \|\| @.funny < 0)).user_id` |
| integer | YR-X14 | exists | 21.117 | 13.922 | 1.517× | `$ ? (@.date >= "2020-01-01 00:00:00" && @.date < "2021-01-01 00:00:00").review_id` |
| integer | YR-X14 | count | 62.674 | 16.688 | 3.756× | `$ ? (@.date >= "2020-01-01 00:00:00" && @.date < "2021-01-01 00:00:00").review_id` |
| integer | YR-X15 | exists | 35.091 | 15.043 | 2.333× | `$ ? (@.business_id != "" && @.user_id != "" && @.review_id != "").text` |
| integer | YR-X15 | count | 101.008 | 16.994 | 5.944× | `$ ? (@.business_id != "" && @.user_id != "" && @.review_id != "").text` |
| integer | YR-X16 | exists | 48.881 | 21.603 | 2.263× | `$.text ? (@ like_regex "^[A-Z]")` |
| integer | YR-X16 | count | 116.004 | 22.743 | 5.101× | `$.text ? (@ like_regex "^[A-Z]")` |
| integer | YR-X17 | exists | 35.070 | 17.325 | 2.024× | `$ ? ((@.useful + @.cool + @.funny) >= 5).review_id` |
| integer | YR-X17 | count | 77.487 | 19.246 | 4.026× | `$ ? ((@.useful + @.cool + @.funny) >= 5).review_id` |
| integer | YR-X18 | exists | 21.824 | 12.559 | 1.738× | `$ ? ((@.stars > 5.0) is unknown).review_id` |
| integer | YR-X18 | count | 61.512 | 15.949 | 3.857× | `$ ? ((@.stars > 5.0) is unknown).review_id` |
| integer | YR-X19 | exists | 24.351 | 14.429 | 1.688× | `$ ? (@.useful > @.cool).review_id` |
| integer | YR-X19 | count | 76.036 | 17.658 | 4.306× | `$ ? (@.useful > @.cool).review_id` |
| integer | YR-X20 | exists | 41.236 | 19.705 | 2.093× | `$ ? (((@.useful + @.cool + @.funny) / 3) >= 1).review_id` |
| integer | YR-X20 | count | 88.376 | 21.485 | 4.113× | `$ ? (((@.useful + @.cool + @.funny) / 3) >= 1).review_id` |
| numeric | YR-X1 | exists | 19.977 | 15.413 | 1.296× | `$.review_id` |
| numeric | YR-X1 | count | 79.022 | 17.946 | 4.403× | `$.review_id` |
| numeric | YR-X2 | exists | 26.124 | 15.614 | 1.673× | `$.stars ? (@ >= 3.5)` |
| numeric | YR-X2 | count | 81.004 | 20.947 | 3.867× | `$.stars ? (@ >= 3.5)` |
| numeric | YR-X3 | exists | 23.630 | 15.323 | 1.542× | `$.text ? (@ != "")` |
| numeric | YR-X3 | count | 86.996 | 21.230 | 4.098× | `$.text ? (@ != "")` |
| numeric | YR-X4 | exists | 32.264 | 18.583 | 1.736× | `$ ? (@.cool >= 1 \|\| @.funny >= 1)` |
| numeric | YR-X4 | count | 79.457 | 18.370 | 4.325× | `$ ? (@.cool >= 1 \|\| @.funny >= 1)` |
| numeric | YR-X5 | exists | 26.030 | 15.537 | 1.675× | `$ ? (@.useful >= 2 && @.stars < 4.0)` |
| numeric | YR-X5 | count | 71.604 | 18.368 | 3.898× | `$ ? (@.useful >= 2 && @.stars < 4.0)` |
| numeric | YR-X6 | exists | 23.087 | 16.302 | 1.416× | `$ ? (@.date >= "2020-01-01 00:00:00")` |
| numeric | YR-X6 | count | 64.496 | 18.559 | 3.475× | `$ ? (@.date >= "2020-01-01 00:00:00")` |
| numeric | YR-X7 | exists | 24.026 | 14.431 | 1.665× | `$.business_id ? (@ != "")` |
| numeric | YR-X7 | count | 86.321 | 19.574 | 4.410× | `$.business_id ? (@ != "")` |
| numeric | YR-X8 | exists | 30.422 | 16.153 | 1.883× | `$ ? (@.useful >= 1 && (@.cool >= 1 \|\| @.funny >= 1)).review_id` |
| numeric | YR-X8 | count | 78.349 | 19.817 | 3.954× | `$ ? (@.useful >= 1 && (@.cool >= 1 \|\| @.funny >= 1)).review_id` |
| numeric | YR-X9 | exists | 101.270 | 27.286 | 3.711× | `$ ? (@.stars >= 4.0 && @.text like_regex "good" flag "i").business_id` |
| numeric | YR-X9 | count | 152.994 | 30.277 | 5.053× | `$ ? (@.stars >= 4.0 && @.text like_regex "good" flag "i").business_id` |
| numeric | YR-X10 | exists | 24.059 | 15.674 | 1.535× | `$.text ? (@ starts with "A")` |
| numeric | YR-X10 | count | 66.523 | 22.072 | 3.014× | `$.text ? (@ starts with "A")` |
| numeric | YR-X11 | exists | 32.979 | 17.435 | 1.892× | `$ ? (@.stars >= 3.0) ? (@.useful >= 1) ? (@.cool >= 0).review_id` |
| numeric | YR-X11 | count | 81.232 | 19.768 | 4.109× | `$ ? (@.stars >= 3.0) ? (@.useful >= 1) ? (@.cool >= 0).review_id` |
| numeric | YR-X12 | exists | 33.949 | 16.502 | 2.057× | `$ ? (((@.stars == "five") is unknown) && @.useful >= 0).review_id` |
| numeric | YR-X12 | count | 94.564 | 18.974 | 4.984× | `$ ? (((@.stars == "five") is unknown) && @.useful >= 0).review_id` |
| numeric | YR-X13 | exists | 39.058 | 17.099 | 2.284× | `$ ? (!(@.useful < 0 \|\| @.cool < 0 \|\| @.funny < 0)).user_id` |
| numeric | YR-X13 | count | 102.374 | 19.607 | 5.221× | `$ ? (!(@.useful < 0 \|\| @.cool < 0 \|\| @.funny < 0)).user_id` |
| numeric | YR-X14 | exists | 24.127 | 15.220 | 1.585× | `$ ? (@.date >= "2020-01-01 00:00:00" && @.date < "2021-01-01 00:00:00").review_id` |
| numeric | YR-X14 | count | 64.858 | 19.130 | 3.390× | `$ ? (@.date >= "2020-01-01 00:00:00" && @.date < "2021-01-01 00:00:00").review_id` |
| numeric | YR-X15 | exists | 38.976 | 16.961 | 2.298× | `$ ? (@.business_id != "" && @.user_id != "" && @.review_id != "").text` |
| numeric | YR-X15 | count | 102.361 | 18.269 | 5.603× | `$ ? (@.business_id != "" && @.user_id != "" && @.review_id != "").text` |
| numeric | YR-X16 | exists | 49.909 | 23.397 | 2.133× | `$.text ? (@ like_regex "^[A-Z]")` |
| numeric | YR-X16 | count | 120.175 | 25.675 | 4.681× | `$.text ? (@ like_regex "^[A-Z]")` |
| numeric | YR-X17 | exists | 38.040 | 19.808 | 1.920× | `$ ? ((@.useful + @.cool + @.funny) >= 5).review_id` |
| numeric | YR-X17 | count | 84.099 | 23.717 | 3.546× | `$ ? ((@.useful + @.cool + @.funny) >= 5).review_id` |
| numeric | YR-X18 | exists | 25.626 | 16.363 | 1.566× | `$ ? ((@.stars > 5.0) is unknown).review_id` |
| numeric | YR-X18 | count | 68.748 | 19.494 | 3.527× | `$ ? ((@.stars > 5.0) is unknown).review_id` |
| numeric | YR-X19 | exists | 27.477 | 16.735 | 1.642× | `$ ? (@.useful > @.cool).review_id` |
| numeric | YR-X19 | count | 76.445 | 20.579 | 3.715× | `$ ? (@.useful > @.cool).review_id` |
| numeric | YR-X20 | exists | 43.598 | 21.899 | 1.991× | `$ ? (((@.useful + @.cool + @.funny) / 3) >= 1).review_id` |
| numeric | YR-X20 | count | 92.141 | 25.319 | 3.639× | `$ ? (((@.useful + @.cool + @.funny) / 3) >= 1).review_id` |

## Bundle layout

```text
release/
  libpg_specson.so
  pg_specson.control
  pg_specson--0.1.0.sql
scripts/
  execute_specson_pg.py
  run_specson_experiments.py
  summarize_specson_results.py
  specson_workloads.json
  specson_experiments/
  plot_specson_*.py
datasets/
  github/
  openalex/
  yelp-business/
  yelp-review/
  synthetic-width-1/
  synthetic-rank-4/
  synthetic-array-shape-1x2000/
  synthetic-array-shape-2000x1/
```

The supplied shared library was built for PostgreSQL 18.4 and with native CPU
instructions. Install it only into a PostgreSQL installation with the same
major-version ABI on a compatible machine.

SpecSon currently supports Linux only, and the prebuilt extension in this
bundle is a Linux x86-64 binary. Windows and macOS binaries are not available
yet; we plan to provide them in future releases.

## Install the PostgreSQL extension

Set `PG_CONFIG` to the target PostgreSQL installation. The commands below copy
the library under the name expected by the extension metadata and install the
control and SQL files. They require permission to write into the PostgreSQL
installation directories.

```bash
cd ~/specson
export PG_CONFIG=/opt/postgresql-18.4-native/bin/pg_config

sudo install -m 755 release/libpg_specson.so \
  "$($PG_CONFIG --pkglibdir)/pg_specson.so"
sudo install -m 644 release/pg_specson.control \
  release/pg_specson--0.1.0.sql \
  "$($PG_CONFIG --sharedir)/extension/"
```

Restart PostgreSQL if the server has already loaded an older SpecSon library,
then create the extension in the experiment database:

```bash
psql -d postgres -c 'CREATE EXTENSION IF NOT EXISTS pg_specson;'
psql -d postgres -c \
  "SELECT extname, extversion FROM pg_extension WHERE extname = 'pg_specson';"
```

The experiment user must be able to create schemas, tables, and the
`pg_prewarm` extension in that database.

## Install Python dependencies

Python 3 and Psycopg 3 are required to run PostgreSQL experiments. Matplotlib
and Pillow are required only for the publication plotting scripts.

```bash
cd ~/specson
python3 -m venv .venv
source .venv/bin/activate
python3 -m pip install 'psycopg[binary]>=3'
python3 -m pip install -r scripts/requirements-figures.txt
```

## Prepare datasets

Download the complete dataset bundle, including the JSONL inputs and schemas,
from [Google Drive](https://drive.google.com/file/d/1uap3LueGqBhA5iiS1uKOl4YxlU_f0sS6/view?usp=sharing).
Extract it into the repository root so that the archive's `datasets/`
directory overlays `~/specson/datasets/`. For example, if your browser saved
the archive in `~/Downloads`:

```bash
tar --zstd -xf ~/Downloads/specson-test-datasets.tar.zst -C ~/specson
```

If the downloaded archive is elsewhere, replace the archive path in that
command. After extraction, the files will be under `~/specson/datasets/`.

After extraction, the real-world inputs must be present at these exact paths:

```text
datasets/yelp-review/yelp_academic_dataset_review.jsonl
datasets/yelp-business/yelp_academic_dataset_business.jsonl
datasets/github/2026-06-26-0.jsonl ... 2026-06-26-23.jsonl
datasets/openalex/2026-06-26-part-0000.jsonl
```

The catalog expects 6,990,280 Yelp Review rows, 150,346 Yelp Business rows,
3,795,000 GitHub rows, and 358,387 OpenAlex rows. Query and restore refuse to
run if either the SpecSon or JSONB table is missing or has the wrong row count.

To regenerate the retained synthetic datasets instead of using the bundled
JSONL files, use 10,000 rows and one worker:

```bash
cd ~/specson
for dataset in \
  synthetic-width-1 \
  synthetic-rank-4 \
  synthetic-array-shape-1x2000 \
  synthetic-array-shape-2000x1
do
  python3 "datasets/$dataset/generate.py" \
    --rows 10000 --workers 1 --force
done
```

Each generator writes `data.jsonl` and refreshes `manifest.json` in its own
dataset directory. Generation is deterministic for a fixed schema, seed, and
row count.

Available dataset IDs are:

| ID | Dataset | Variants |
|---:|---|---|
| 1 | Yelp Review | Integer, Numeric |
| 2 | Yelp Business | Integer, Numeric |
| 3 | GitHub Archive | Integer, Numeric |
| 4 | OpenAlex Works | Integer, Numeric |
| 201 | Synthetic Width 1 | Numeric |
| 304 | Synthetic Rank 4 | Numeric |
| 501 | Synthetic Array Shape 1x2000 | Numeric |
| 504 | Synthetic Array Shape 2000x1 | Numeric |

To inspect the catalog after placing the inputs:

```bash
python3 scripts/run_specson_experiments.py datasets
```

## Configure PostgreSQL for formal encode measurements

The formal encode runner rejects configurations that can checkpoint during a
timed bulk write. Configure these benchmark controls and reload PostgreSQL:

```sql
ALTER SYSTEM SET max_wal_size = '32GB';
ALTER SYSTEM SET checkpoint_timeout = '1h';
SELECT pg_reload_conf();
```

These settings are experiment controls, not SpecSon runtime requirements. Make
sure the PostgreSQL data directory has enough free space for the source,
SpecSon, JSONB, TOAST, and WAL data.

## Run the experiments

All examples below pin the client and PostgreSQL backend to one CPU and the
runner also disables PostgreSQL parallel workers. Replace the DSN and CPU with
values appropriate for the machine.

Encode must run first. It unconditionally clears and rebuilds the selected
dataset's raw, SpecSon, and JSONB tables. Storage measurements are recorded in
the encode result.

```bash
cd ~/specson
source .venv/bin/activate

taskset -c 11 python3 scripts/execute_specson_pg.py \
  --allow-real-pg \
  --dataset 3 \
  --parts encode \
  --schema-variants integer,numeric \
  --cpu 11 \
  --dsn 'host=/var/run/postgresql port=5432 user=YOUR_POSTGRES_USER dbname=postgres'
```

Run query and restore independently after a successful encode:

```bash
taskset -c 11 python3 scripts/execute_specson_pg.py \
  --allow-real-pg --dataset 3 --parts query \
  --schema-variants integer,numeric --cpu 11 \
  --dsn 'host=/var/run/postgresql port=5432 user=YOUR_POSTGRES_USER dbname=postgres'

taskset -c 11 python3 scripts/execute_specson_pg.py \
  --allow-real-pg --dataset 3 --parts restore \
  --schema-variants integer,numeric --cpu 11 \
  --dsn 'host=/var/run/postgresql port=5432 user=YOUR_POSTGRES_USER dbname=postgres'
```

For a synthetic dataset, select only the Numeric variant. For example:

```bash
taskset -c 11 python3 scripts/execute_specson_pg.py \
  --allow-real-pg --dataset 304 --parts encode,query,restore \
  --schema-variants numeric --cpu 11 \
  --dsn 'host=/var/run/postgresql port=5432 user=YOUR_POSTGRES_USER dbname=postgres'
```

Use `--queries` to select a query ID or glob, for example `--queries point-first`
or `--queries 'github/G-*/exists'`. Do not compare a partial query run with a
result produced from a different selector.

The formal protocol is implemented by the runner:

- encode uses a recorded conditioning pass followed by one rotating
  measurement round per selected system (three rounds for both real-world
  schema variants plus JSONB, or two for one synthetic variant plus JSONB);
- query uses table-major execution, ten rounds, and discards the first five;
- restore uses three full-data rounds;
- timed queries return the final aggregate and do not use `ORDER BY`;
- SpecSon uses PostgreSQL `STORAGE EXTERNAL` so PostgreSQL does not recompress
  its custom block-grouped LZ4 envelope; JSONB uses PostgreSQL
  `STORAGE EXTENDED` with LZ4.

Each completed part is written atomically to:

```text
experiments/specson/results/<dataset-id>-<dataset-name>-<part>.json
```

The dataset ID is zero-padded to three digits; for example, GitHub query
results are written to `experiments/specson/results/003-GitHub-query.json`.

## Summarize and plot results

Print the consolidated ASCII table. Missing parts are displayed as not run:

```bash
python3 scripts/summarize_specson_results.py
```

Generate real-world encode, restore, and storage figures:

```bash
python3 scripts/plot_specson_results.py
```

Generate real-world query figures:

```bash
python3 scripts/plot_specson_query_results.py \
  experiments/specson/figures/query
```

Generate the synthetic publication figures:

```bash
python3 scripts/plot_specson_synthetic_publication_results.py \
  experiments/specson/figures/synthetic
python3 scripts/plot_specson_synthetic_query_results.py \
  experiments/specson/figures/synthetic-query
```

Plotting scripts refuse to run when their required result files are missing.
All performance ratios are reported as `JSONB/SpecSon`; storage percentages
are reported as `SpecSon/JSONB`.
