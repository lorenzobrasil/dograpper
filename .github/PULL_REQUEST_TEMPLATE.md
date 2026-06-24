## Resumo

<!-- O que esta PR muda e por quê. Uma ou duas frases. -->

## Tipo de mudança

- [ ] `feat` — nova funcionalidade
- [ ] `fix` — correção de bug
- [ ] `refactor` — mudança interna sem alterar comportamento
- [ ] `docs` — documentação
- [ ] `ci` / `build` — pipeline ou empacotamento
- [ ] `test` — apenas testes

## Checklist

- [ ] `uv run pytest tests/ -v` passa integralmente
- [ ] Novas deps com binários/compilação nativa são **opcionais** (import condicional)
- [ ] Chunking continua contando **palavras** (`len(text.split())`), não bytes
- [ ] Playwright permanece import condicional (nunca top-level)
- [ ] Precedência de config preservada: defaults < `.dograpper.json` < flags CLI
- [ ] Leitura de arquivos mantém `errors="replace"`
- [ ] `about_dograpper.md` / `docs/schema-v1.md` atualizados se o comportamento ou schema mudou

## Como testar

<!-- Comandos concretos para reproduzir/validar. Ex.:
uv run dograpper pack ./test-docs -o ./chunks --dry-run --show-tokens
-->

## Notas adicionais

<!-- Riscos, decisões de design, follow-ups. -->
