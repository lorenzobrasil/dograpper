# NotebookLM: Otimização de Ingestão

## Pipeline recomendada
```bash
dograpper download <url> -o ./docs
dograpper pack ./docs -o ./chunks --bundle notebooklm --context-header --score
```

## O que o --bundle notebooklm faz
- Limita a ≤50 chunks (teto de fontes do NotebookLM)
- Balanceia palavras uniformemente entre chunks
- Gera IMPORT_GUIDE.md com ordem de upload

## Dicas para Audio Overview
- Faça upload de todos os chunks antes de gerar o overview
- Chunks balanceados produzem overviews mais completos
- Remova chunks de changelog/FAQ para overview mais focado

## Calibrando parâmetros
```bash
# Simulação sem escrever arquivos
dograpper pack ./docs -o ./chunks --bundle notebooklm --dry-run --score
```

## Exemplo com Flask
```bash
dograpper download https://flask.palletsprojects.com/en/stable/ -o ./flask-docs
dograpper pack ./flask-docs -o ./flask-chunks --bundle notebooklm --context-header --score
# Upload os arquivos de ./flask-chunks/ no NotebookLM na ordem do IMPORT_GUIDE.md
```
