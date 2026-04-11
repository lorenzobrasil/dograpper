# RAG: Pipeline de Ingestão

## Pipeline recomendada
```bash
dograpper download <url> -o ./docs
dograpper pack ./docs -o ./chunks --format jsonl --cross-refs --score --context-header
```

## Formato JSONL
Cada linha é um JSON com schema `dograpper-context-v1`:
```json
{"id":"01_api.html","source":"api.html","words":4820,"breadcrumb":["API","Auth"],"readiness_grade":"A","content":"...","schema_version":"v1"}
```

## Cross-references
O `cross_refs.json` mapeia o grafo de referências entre chunks,
permitindo retrieval multi-hop.

## Pipeline típica
```
dograpper pack --format jsonl
    → embeddings (OpenAI/Cohere/local)
    → vector DB (Pinecone/Chroma/Qdrant)
    → retriever com cross-ref graph
```

## Qualidade do contexto
Use `--score` para filtrar chunks com grade C antes de vetorizar.
