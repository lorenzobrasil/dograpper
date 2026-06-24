# 3. Chunking conta palavras, não bytes

- Status: aceito
- Data: 2026-06-23

## Contexto

Os limites de ingestão do NotebookLM (alvo principal) são expressos em
palavras. Medir o tamanho de chunk em bytes ou caracteres divergiria do
limite real que o usuário precisa respeitar.

## Decisão

A métrica de tamanho de chunk é `len(text.split())` (palavras). Não trocar
por bytes ou caracteres.

## Consequências

- Os limites de chunk batem com os limites reais do NotebookLM.
- `--max-words-per-chunk` é a unidade de controle do usuário.
