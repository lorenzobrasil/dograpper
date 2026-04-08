# dograpper CLI — Especificação Técnica

## OBJETIVO

Construir um CLI chamado `dograpper` (doc + wrapper) que resolve um problema específico: documentações técnicas grandes (ex: Kubernetes, Rust, AWS) não cabem no NotebookLM devido a dois limites — máximo de fontes por notebook e teto de palavras por fonte. O CLI baixa a documentação, empacota em chunks que respeitam esses limites.

## ARQUITETURA GERAL

O CLI possui dois subcomandos encadeados em pipeline:

```
download → pack
```

- `download`: espelha um site de documentação localmente
- `pack`: agrega os arquivos em chunks com contagem de palavras controlada

Linguagem: **Python 3.10+** com `click` para CLI parsing.

Dependências externas: `wget`, `playwright` (opcional).

---

## SUBCOMANDO 1: `download`

### Sintaxe

```
dograpper download <url> [flags]
```

### Comportamento

1. Tenta espelhar o site usando `wget --mirror`.
2. Se o conteúdo baixado for um shell HTML vazio (indica SPA como React/Next.js), **automaticamente** faz fallback para crawling via `playwright`.
3. Se a flag `--headless` for passada, pula direto para `playwright` sem tentar `wget`.
4. Ao final, grava um arquivo de manifest (JSON) que registra quais URLs foram baixadas, permitindo re-execuções incrementais (só baixa o que mudou).

### Flags

| Flag | Alias | Tipo | Default | Descrição |
|---|---|---|---|---|
| `--output` | `-o` | string (path) | **obrigatório** | Diretório de destino dos arquivos baixados |
| `--depth` | `-d` | integer | ilimitado | Profundidade máxima de links a seguir |
| `--headless` | — | boolean | `false` | Forçar crawling via playwright |
| `--delay` | — | integer (ms) | `0` | Intervalo entre requisições (rate limiting) |
| `--include-extensions` | — | string (csv) | `"html,md,txt"` | Extensões permitidas. Arquivos com outras extensões são ignorados |
| `--manifest` | — | string (path) | `.dograpper-manifest.json` | Caminho do arquivo de cache para downloads incrementais |

### Detecção de SPA (heurística para fallback automático)

Após o `wget` completar, verificar os arquivos HTML baixados. Se a maioria contiver apenas um `<div id="root">` ou `<div id="__next">` vazio (corpo com menos de N caracteres de texto visível), considerar que o site é uma SPA e re-executar com `playwright`.

### Estrutura do manifest

```json
{
  "base_url": "https://docs.rust-lang.org",
  "last_run": "2025-01-15T10:30:00Z",
  "files": {
    "book/ch01-00-getting-started.html": {
      "url": "https://docs.rust-lang.org/book/ch01-00-getting-started.html",
      "etag": "abc123",
      "last_modified": "2025-01-10T00:00:00Z",
      "size_bytes": 45230
    }
  }
}
```

---

## SUBCOMANDO 2: `pack`

### Sintaxe

```
dograpper pack <input_dir> [flags]
```

### Comportamento

1. Lê todos os arquivos do diretório de entrada.
2. Aplica regras de exclusão (`.docsignore` + flags `--ignore`).
3. Agrupa os arquivos restantes em chunks sequenciais: `docs_chunk_01.md`, `docs_chunk_02.md`, etc.
4. Cada chunk tem um cabeçalho com índice dos arquivos contidos (se `--with-index` estiver ativo).
5. A concatenação dos arquivos é feita em Python puro — sem dependências externas. Cada arquivo é precedido por um separador `<!-- SOURCE: path/to/file.md -->` para preservar rastreabilidade.
6. Valida que o número total de chunks não exceda `--max-chunks`. Se exceder, emite warning com sugestão de aumentar `--max-words-per-chunk` ou refinar filtros de exclusão.

### Flags

| Flag | Alias | Tipo | Default | Descrição |
|---|---|---|---|---|
| `--output` | `-o` | string (path) | **obrigatório** | Diretório onde os chunks serão salvos |
| `--max-words-per-chunk` | — | integer | `500000` | Limite de palavras por chunk (corresponde ao limite por fonte do NotebookLM) |
| `--max-chunks` | — | integer | `50` | Limite de chunks gerados (corresponde ao limite de fontes por notebook do NotebookLM) |
| `--strategy` | — | enum | `"size"` | `"size"`: empacota por contagem de palavras pura. `"semantic"`: agrupa arquivos por módulo/seção antes de aplicar limite |
| `--ignore-file` | — | string (path) | `./.docsignore` | Caminho para arquivo de exclusão (sintaxe gitignore) |
| `--ignore` | — | string[] | `[]` | Padrões de exclusão inline. Pode ser repetido: `--ignore "*.png" --ignore "**/changelog/**"` |
| `--prefix` | — | string | `"docs_chunk_"` | Prefixo dos arquivos gerados |
| `--with-index` | — | boolean | `true` | Incluir sumário de arquivos no cabeçalho de cada chunk |
| `--format` | — | enum | `"md"` | Formato de saída: `"txt"`, `"md"`, ou `"xml"` |

### Estratégia `semantic`

Agrupar arquivos que pertencem ao mesmo módulo/seção da documentação no mesmo chunk, antes de aplicar o limite de palavras. Usar a estrutura de diretórios como proxy para módulos. Exemplo: todos os arquivos em `book/ch01-*` vão para o mesmo chunk, se couberem.

### Formato do cabeçalho de chunk (quando `--with-index` é true)

```markdown
# Chunk 03 de 12

## Arquivos neste chunk (7 arquivos, ~82.000 palavras):
- book/ch05-00-structs.md (12.300 palavras)
- book/ch05-01-defining-structs.md (8.500 palavras)
- book/ch05-02-example-structs.md (9.100 palavras)
...

---

[conteúdo dos arquivos concatenados abaixo]
```

### Caso especial: arquivo único maior que `--max-words-per-chunk`

Se um único arquivo exceder o limite de palavras do chunk, ele deve ser colocado sozinho em um chunk e um **warning** deve ser emitido no output. O CLI **não deve falhar** — apenas avisar que aquele chunk excede o limite.

---

## FLAGS GLOBAIS (todos os subcomandos)

| Flag | Alias | Tipo | Default | Descrição |
|---|---|---|---|---|
| `--verbose` | `-v` | boolean | `false` | Log detalhado de cada operação |
| `--quiet` | `-q` | boolean | `false` | Suprimir output exceto erros críticos |
| `--config` | — | string (path) | `.dograpper.json` | Arquivo de configuração |

### Precedência de configuração

```
defaults < arquivo de configuração (.dograpper.json) < flags da linha de comando
```

Flags da CLI sempre vencem.

### Formato do arquivo de configuração

```json
{
  "download": {
    "depth": 3,
    "include-extensions": ["html", "md"],
    "manifest": ".dograpper-manifest.json"
  },
  "pack": {
    "max-words-per-chunk": 400000,
    "max-chunks": 50,
    "strategy": "semantic",
    "format": "md",
    "with-index": true
  }
}
```

---

## INVARIANTES E REGRAS GLOBAIS

1. **Idempotência**: re-execuções com os mesmos inputs devem gerar os mesmos outputs.
2. **Output de progresso**: sempre indicar arquivos baixados, arquivos ignorados, chunks gerados, contagem de palavras por chunk e totais.
3. **`--verbose` e `--quiet` são mutuamente exclusivos**. Se ambos forem passados, emitir erro.

---

## TRATAMENTO DE ERROS

| Cenário | Comportamento esperado |
|---|---|
| Falha de rede durante download | Retry com backoff exponencial (3 tentativas). Após falhar, logar o URL e continuar com os demais |
| Site é SPA e `--headless` não foi passado | Fallback automático para playwright. Se playwright não estiver instalado, erro com instrução de instalação |
| Diretório de input do `pack` está vazio | Erro: "No files found in <dir>. Did you run `download` first?" |
| Diretório vazio após aplicar filtros do `.docsignore` | Erro: "All files were excluded by ignore rules. Check your .docsignore or --ignore flags." |
| Arquivo único excede `--max-words-per-chunk` | Warning (não erro). Chunk é gerado mesmo assim, com aviso no output |
| Total de chunks excede `--max-chunks` | Warning com sugestão: "Generated N chunks, exceeding max-chunks limit of M. Consider increasing --max-words-per-chunk or adding --ignore rules." |
| `wget` não está instalado | Erro com instrução de instalação |
| Arquivo de configuração JSON inválido | Erro com linha/coluna do problema de parsing |

---

## EXEMPLOS DE USO

```bash
# Fluxo básico
dograpper download https://docs.rust-lang.org -o ./rust-docs
dograpper pack ./rust-docs -o ./chunks

# Com limites customizados do NotebookLM
dograpper pack ./rust-docs -o ./chunks \
  --max-words-per-chunk 300000 \
  --max-chunks 30

# Com filtros e estratégia semântica
dograpper pack ./rust-docs -o ./chunks \
  --strategy semantic \
  --ignore "*.png" \
  --ignore "**/404.html" \
  --format md

# Usando config por projeto
dograpper --config ./projects/rust/.dograpper.json download https://docs.rust-lang.org
dograpper --config ./projects/rust/.dograpper.json pack ./rust-docs

# SPA com playwright forçado
dograpper download https://react.dev --headless -o ./react-docs --delay 500
```

---

## ESTRUTURA DE ARQUIVOS

```
dograpper/
├── src/
│   └── dograpper/
│       ├── __init__.py
│       ├── cli.py                 # Entry point, configura click
│       ├── commands/
│       │   ├── __init__.py
│       │   ├── download.py        # Lógica do subcomando download
│       │   └── pack.py            # Lógica do subcomando pack
│       ├── lib/
│       │   ├── __init__.py
│       │   ├── wget_mirror.py     # Wrapper do wget --mirror
│       │   ├── playwright_crawl.py# Crawler headless
│       │   ├── spa_detector.py    # Heurística de detecção de SPA
│       │   ├── manifest.py        # Leitura/escrita do manifest
│       │   ├── chunker.py         # Lógica de chunking e concatenação
│       │   ├── ignore_parser.py   # Parser de .docsignore (usa pathspec)
│       │   └── config_loader.py   # Merge de config JSON + flags CLI
│       └── utils/
│           ├── __init__.py
│           ├── logger.py          # Logger com suporte a --verbose/--quiet
│           └── word_counter.py    # Contagem de palavras para chunking
├── tests/
│   ├── __init__.py
│   ├── test_cli_smoke.py
│   ├── test_download.py
│   └── test_pack.py
├── pyproject.toml
├── .docsignore.example
├── .dograpper.json.example
└── README.md
```

### Dependências Python

```toml
[project]
name = "dograpper"
requires-python = ">=3.10"
dependencies = [
    "click>=8.1",
    "pathspec>=1.0.4",
]

[project.optional-dependencies]
headless = ["playwright>=1.40"]
dev = ["pytest>=7.0"]

[project.scripts]
dograpper = "dograpper.cli:main"
```