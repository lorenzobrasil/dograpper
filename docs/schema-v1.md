# dograpper-context-v1 Schema

## Header Format

Each chunk begins with a metadata block in an HTML comment:

```
<!-- dograpper-context-v1
{ ... JSON ... }
-->
```

## Fields

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| source | string | yes | Relative path of the source file |
| url | string | no | Original URL (from download manifest) |
| chunk_index | int | no | Sub-chunk position (1-based). Omitted if file is not split. |
| total_chunks | int | no | Total sub-chunks for this file. Omitted if file is not split. |
| word_count | int | no | Word count of this chunk's content (excluding header) |
| context_breadcrumb | string[] | no | Heading hierarchy at chunk start. Omitted if no headings. |
| llm_readiness | object | no | Readiness metrics (present when --score is used) |
| schema_version | string | yes | Always "v1" |

## llm_readiness Object

| Field | Type | Description |
|-------|------|-------------|
| score | float | Composite score 0.0-1.0 |
| grade | string | "A", "B", or "C" |
| noise_ratio | float | Proportion of boilerplate removed (0.0-1.0) |

## Versioning

Future versions (v2+) will be backward-compatible. Parsers should
check `schema_version` and ignore unknown fields.
