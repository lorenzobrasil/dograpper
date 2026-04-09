<!-- TODO: Mover esse arquivo para a raiz do projeto depois de terminar as implementações! -->


# dograpper — Contexto do Projeto

## Visão geral

CLI em Python que baixa documentações técnicas inteiras (Kubernetes, Rust, AWS, etc.) e empacota em chunks prontos para importar no Google NotebookLM. Resolve o problema de documentações que excedem os limites do NotebookLM (máximo de palavras por fonte e máximo de fontes por notebook). Dois subcomandos: `download` (espelha site via wget/playwright) e `pack` (agrupa arquivos em chunks por contagem de palavras).

## Stack técnica

- **Linguagem**: Python 3.10+
- **CLI framework**: click
- **Package manager**: uv
- **Filtro de arquivos**: pathspec (sintaxe gitignore)
- **Crawling SPA**: playwright (dependência opcional, import condicional)
- **Download padrão**: wget (dependência do sistema)
- **Testes**: pytest com click.testing.CliRunner

## Estrutura do repositório

```
src/dograpper/
├── cli.py                  # Entry point click, flags globais (--verbose, --quiet, --config)
├── commands/
│   ├── download.py         # Orquestração: wget → SPA detection → fallback playwright → manifest
│   └── pack.py             # Orquestração: list files → filter → chunk → write → summary
├── lib/
│   ├── chunker.py          # Estratégias size e semantic, dataclasses Chunk/ChunkFile, write_chunks()
│   ├── config_loader.py    # Merge com precedência: defaults < JSON < CLI (usa ctx.get_parameter_source)
│   ├── ignore_parser.py    # filter_files() com pathspec
│   ├── manifest.py         # Dataclasses Manifest/ManifestEntry, load/save/build
│   ├── playwright_crawl.py # Crawler headless, import condicional
│   ├── spa_detector.py     # is_spa() via html.parser da stdlib
│   └── wget_mirror.py      # Wrapper subprocess com retry e backoff
└── utils/
    ├── logger.py           # setup_logger() com suporte a verbose/quiet
    └── word_counter.py     # count_words() e count_words_file()
tests/
├── test_cli_smoke.py       # Help, flags obrigatórias, mutual exclusion
├── test_config.py          # Precedência, JSON inválido, arquivo ausente
├── test_download.py        # wget mock, SPA detector, manifest roundtrip
└── test_pack.py            # word_counter, ignore_parser, chunker, write_chunks, CLI integration
```

## Como rodar localmente

```bash
git clone <repo-url>
cd dograpper
uv sync                    # instala todas as dependências
uv run dograpper --help    # verifica que está funcionando
```

Para testar download real:
```bash
uv run dograpper download https://click.palletsprojects.com/en/stable/ -o ./test-docs -d 2
uv run dograpper pack ./test-docs -o ./chunks
```

## Arquivos de contexto importantes

| Arquivo | Quando ler |
|---|---|
| `about_dograpper.md` | **Sempre.** Spec completa do projeto: comportamento esperado de cada comando, flags, tabela de erros, formato de config, invariantes. É a fonte de verdade. |
| `.dograpper.json.example` | Ao mexer em `config_loader.py` ou no merge de configuração |
| `.docsignore.example` | Ao mexer em `ignore_parser.py` |
| `tests/test_pack.py` | Antes de alterar qualquer coisa em `lib/chunker.py` ou `commands/pack.py` |
| `tests/test_download.py` | Antes de alterar qualquer coisa em `lib/wget_mirror.py`, `lib/spa_detector.py`, ou `commands/download.py` |

## Regras críticas

1. **Não adicionar dependências sem necessidade.** O projeto é deliberadamente leve: `click` e `pathspec` apenas. Playwright é opcional (import condicional). Não adicionar BeautifulSoup, rich, requests, ou qualquer lib sem discussão explícita.
2. **Não usar repomix.** A concatenação de chunks é feita em Python puro. Essa é uma decisão arquitetural tomada — não reverter.
3. **Contagem de palavras, não bytes.** O chunking usa `len(text.split())` como métrica. Os limites do NotebookLM são em palavras. Não mudar para bytes.
4. **Playwright nunca é import top-level.** Sempre import condicional dentro da função, com mensagem de erro amigável se ausente.
5. **Testes existentes não podem quebrar.** Qualquer mudança deve manter `uv run pytest tests/ -v` passando integralmente antes de commitar.
6. **Config precedência é inviolável**: defaults do click < `.dograpper.json` < flags CLI explícitas. Usa `ctx.get_parameter_source()` para distinguir. Não simplificar esse mecanismo.
7. **Encoding tolerante.** Leitura de arquivos sempre com `errors="replace"`. O CLI não deve crashar por causa de caracteres estranhos em HTMLs baixados.

## Padrões de commit e branch

- Commits em português ou inglês, sem preferência rígida
- Formato: `tipo: descrição curta` (ex: `feat: implementar estratégia semantic no chunker`, `fix: corrigir contagem de palavras em arquivos vazios`, `refactor: extrair módulos para lib/`)
- Branch principal: `main`
- Feature branches: `feat/nome-curto` ou `fix/nome-curto`

## CI/CD

Não há pipeline de CI configurado ainda. Para replicar o que um CI faria:

```bash
uv run pytest tests/ -v
```

## Comandos úteis

```bash
# Rodar todos os testes
uv run pytest tests/ -v

# Rodar apenas testes do pack
uv run pytest tests/test_pack.py -v

# Rodar apenas testes do download
uv run pytest tests/test_download.py -v

# Rodar um teste específico
uv run pytest tests/test_pack.py::test_chunk_by_size_basic -v

# Ver help dos comandos
uv run dograpper --help
uv run dograpper download --help
uv run dograpper pack --help

# Download de teste rápido (site pequeno)
uv run dograpper download https://click.palletsprojects.com/en/stable/ -o ./test-docs -d 1

# Pack com limite baixo para forçar múltiplos chunks
uv run dograpper pack ./test-docs -o ./chunks --max-words-per-chunk 5000

# Pack com verbose para debug
uv run dograpper -v pack ./test-docs -o ./chunks --strategy semantic
```