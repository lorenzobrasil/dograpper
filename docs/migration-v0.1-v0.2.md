# Migration Guide: v0.1.0 → v0.2.0

## Mudanças que quebram compatibilidade

### Formato XML depreciado
`--format xml` agora retorna erro. Migre para `md` (default) ou `jsonl`.

### Header de contexto: formato v1
O `--context-header` agora gera header JSON estruturado
(`dograpper-context-v1`) em vez de linhas `<!-- source: -->` separadas.
Se você parseia os headers antigos, atualize para extrair o JSON do
bloco `<!-- dograpper-context-v1 ... -->`.

## Novas flags

| Flag | Descrição |
|------|-----------|
| `--bundle notebooklm` | Empacotamento otimizado para NotebookLM (≤50 chunks) |
| `--score` | LLM Readiness Score por chunk |
| `--cross-refs` | Grafo de referências cruzadas entre chunks |
| `--delta` | Reprocessa apenas arquivos alterados |
| `--format jsonl` | Export JSONL para pipelines de RAG |

## Novo subcomando

`dograpper sync <url> -o <dir>` — download + pack delta em cadeia.

## Novos artefatos

| Arquivo | Gerado por |
|---------|------------|
| `cross_refs.json` | `--cross-refs` |
| `llm-readiness.json` | `--score` |
| `IMPORT_GUIDE.md` | `--bundle` |
| `delta_manifest.json` | `--delta` |
