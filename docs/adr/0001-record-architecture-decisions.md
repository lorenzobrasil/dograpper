# 1. Registrar decisões de arquitetura

- Status: aceito
- Data: 2026-06-23

## Contexto

O dograpper tem várias decisões arquiteturais inegociáveis (ver "Regras
críticas" no CLAUDE.md). Elas precisam de um registro durável, versionado
e descoberto por humanos e por agentes, em vez de viverem só na memória.

## Decisão

Usar Architecture Decision Records (ADRs) em `docs/adr/`, um arquivo por
decisão, numerados sequencialmente. Cada ADR registra contexto, decisão e
consequências. Decisões revogadas são marcadas como `substituído por NNNN`
em vez de apagadas.

## Consequências

- Decisões críticas ficam rastreáveis no histórico do repositório.
- Serve como memória persistente para a equipe e para o harness de agentes.
