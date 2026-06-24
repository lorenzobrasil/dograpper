# 4. Dependências nativas são opcionais e de import condicional

- Status: aceito
- Data: 2026-06-23

## Contexto

Algumas dependências exigem binários do sistema ou compilação nativa que
não funciona em todos os ambientes — notadamente o Playwright, que requer
`playwright install chromium`. Torná-las obrigatórias quebraria a instalação
em ambientes mínimos.

## Decisão

Libs com binários/compilação nativa problemática são dependências
**opcionais**, importadas condicionalmente dentro da função que as usa, com
mensagem de erro amigável quando ausentes. Playwright nunca é import
top-level. Dependências pip puras (tiktoken, click, pathspec) podem ser
obrigatórias e de import top-level.

## Consequências

- O CLI instala e roda o caminho principal sem chromium/playwright.
- Recursos avançados (crawl SPA) degradam com mensagem clara, sem crash.
