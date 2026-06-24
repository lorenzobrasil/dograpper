# 2. Não usar repomix — concatenação em Python puro

- Status: aceito
- Data: 2026-06-23

## Contexto

A geração de chunks poderia delegar a concatenação a ferramentas externas
como o repomix. Isso adicionaria uma dependência de runtime externa e
reduziria o controle determinístico sobre o formato de saída.

## Decisão

Toda a concatenação e o agrupamento de chunks são feitos em Python puro
(`lib/chunker.py`). Não introduzir repomix nem ferramentas equivalentes.

## Consequências

- Saída totalmente determinística e versionável (formato dograpper-context-v1).
- Sem dependência externa de Node/ferramenta de terceiros no caminho crítico.
- Esta é uma decisão tomada — não deve ser revertida sem novo ADR.
