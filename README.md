# dograpper

**doc + wrapper** — CLI que baixa documentações técnicas inteiras e empacota em chunks prontos para importar no [Google NotebookLM](https://notebooklm.google.com/).

## O problema

O NotebookLM impõe dois limites para fontes de um notebook: um teto de palavras por fonte e um número máximo de fontes. Documentações como Kubernetes, Rust ou AWS facilmente estouram ambos os limites. O dograpper resolve isso em dois passos:

1. **`download`** — espelha o site da documentação localmente (via `wget` ou `playwright` para SPAs)
2. **`pack`** — agrupa os arquivos em chunks que respeitam os limites, prontos para upload manual

---

## Instalação

Requer Python 3.10+ e [uv](https://docs.astral.sh/uv/).

```bash
git clone https://github.com/seu-usuario/dograpper.git
cd dograpper
uv sync
```

### Dependências do sistema

O subcomando `download` usa `wget` por padrão:

```bash
# macOS
brew install wget

# Ubuntu/Debian
sudo apt install wget
```

Para sites SPA (React, Next.js, etc.), é necessário o `playwright`:

```bash
uv sync --extra headless
playwright install chromium
```


---

## Início rápido

```bash
# 1. Baixar a documentação do Click (site pequeno, bom para testar)
dograpper download https://click.palletsprojects.com/en/stable/ -o ./click-docs -d 2

# 2. Empacotar em chunks
dograpper pack ./click-docs -o ./chunks

# 3. Importar os arquivos de ./chunks/ no NotebookLM como fontes
```

---

## Uso

### `dograpper download`

Espelha um site de documentação no disco local.

```bash
dograpper download <url> -o <diretório> [opções]
```

| Opção | Alias | Default | Descrição |
|---|---|---|---|
| `--output` | `-o` | *obrigatório* | Diretório de destino |
| `--depth` | `-d` | `0` (ilimitado) | Profundidade máxima de links |
| `--headless` | — | `false` | Pular wget e usar playwright direto |
| `--delay` | — | `0` | Intervalo entre requisições (ms) |
| `--include-extensions` | — | `html,md,txt` | Extensões permitidas (csv) |
| `--manifest` | — | `.dograpper-manifest.json` | Caminho do arquivo de cache |

**Detecção automática de SPA**: se o wget baixar apenas shells HTML vazios (típico de React/Next.js), o dograpper detecta isso automaticamente e refaz o download com playwright. Use `--headless` para pular direto para playwright quando já souber que o site é uma SPA.

**Downloads incrementais**: um arquivo de manifest é gerado após cada download, registrando os arquivos baixados. Re-execuções futuras podem usar esse manifest como referência.

#### Exemplos

```bash
# Documentação do Rust, sem limite de profundidade
dograpper download https://docs.rust-lang.org -o ./rust-docs

# SPA com rate limiting
dograpper download https://react.dev --headless -o ./react-docs --delay 500

# Apenas HTML e Markdown, máximo 3 níveis
dograpper download https://docs.python.org/3/ -o ./python-docs -d 3 --include-extensions "html,md"
```

### `dograpper pack`

Agrupa os arquivos baixados em chunks com contagem de palavras controlada.

```bash
dograpper pack <diretório_input> -o <diretório_output> [opções]
```

| Opção | Alias | Default | Descrição |
|---|---|---|---|
| `--output` | `-o` | *obrigatório* | Diretório para os chunks |
| `--max-words-per-chunk` | — | `500000` | Limite de palavras por chunk |
| `--max-chunks` | — | `50` | Limite de chunks gerados |
| `--strategy` | — | `size` | Estratégia: `size` ou `semantic` |
| `--ignore-file` | — | `./.docsignore` | Arquivo de exclusão (sintaxe gitignore) |
| `--ignore` | — | *(nenhum)* | Padrões de exclusão inline (repetível) |
| `--prefix` | — | `docs_chunk_` | Prefixo dos arquivos gerados |
| `--with-index` / `--no-index` | — | `--with-index` | Cabeçalho com índice de arquivos |
| `--format` | — | `md` | Formato de saída: `txt`, `md`, `xml` |
| `--no-extract` | — | `false` | Desativa extração inteligente de conteúdo HTML |
| `--show-tokens` | — | `false` | Exibe contagem de tokens no resumo final |
| `--token-encoding` | — | `cl100k` | Encoding do tokenizer: `cl100k`, `o200k`, `p50k` |
| `--dry-run` | — | `false` | Simula o pack sem escrever arquivos; exibe relatório de compressão e projeção |
| `--dedup` | — | `off` | Deduplicação de blocos: `off`, `exact`, `fuzzy`, `both` |
| `--dedup-threshold` | — | `3` | Distância de Hamming máxima para dedup fuzzy (0-10) |
| `--context-header` | — | `false` | Injeta cabeçalho de contexto (source + breadcrumb de headings) por arquivo no chunk |

**Extração inteligente** (ativa por padrão): antes de empacotar, o dograpper extrai apenas o conteúdo principal de cada HTML (usando `<main>`, `<article>`, ou scoring por densidade), removendo boilerplate como navbars, sidebars, footers, breadcrumbs, botões "copy to clipboard", banners de versão, etc. Use `--no-extract` para manter o HTML integral (comportamento legado).

**Deduplicação** (`--dedup`): remove blocos de texto duplicados entre arquivos de documentação. Comum em sites que repetem headers, footers, disclaimers ou blocos de navegação em várias páginas. Três modos:
- `exact` — remove blocos idênticos (normalizado por case e whitespace) via hash MD5
- `fuzzy` — remove blocos quase idênticos via SimHash + distância de Hamming (controlada por `--dedup-threshold`)
- `both` — aplica exact primeiro, depois fuzzy nos blocos restantes

Blocos com menos de 10 palavras são ignorados para evitar falsos positivos em headings curtos. A primeira ocorrência (ordem alfabética de arquivo) é sempre preservada.

**Dry-run** (`--dry-run`): simula o pack sem escrever nenhum arquivo. Exibe um relatório completo com contagem de arquivos, palavras (bruto vs. extraído vs. pós-dedup), projeção de chunks, top 10 arquivos por tamanho, e warnings de oversize. Útil para calibrar parâmetros antes de empacotar.

**Cabeçalho de contexto** (`--context-header`): injeta metadados de origem no topo de cada arquivo dentro do chunk, ancorando o conteúdo na estrutura da documentação original. Para arquivos HTML, extrai a hierarquia de headings (h1 > h2 > h3) e formata como breadcrumb. Para arquivos não-HTML, inclui apenas o caminho de origem. O cabeçalho usa comentários HTML (`<!-- -->`) que são invisíveis quando renderizados como Markdown mas legíveis por LLMs. As palavras do cabeçalho não contam para o limite de `--max-words-per-chunk`.

**Estratégia `size`** (default): percorre os arquivos em ordem alfabética, acumulando por contagem de palavras. Abre um novo chunk ao atingir o limite.

**Estratégia `semantic`**: agrupa arquivos do mesmo diretório (módulo) no mesmo chunk antes de aplicar o limite de palavras. Preserva a coesão temática da documentação. Grupos que excedem o limite são subdivididos automaticamente.

**Cabeçalho de chunk** (com `--with-index`): cada chunk inclui um índice dos arquivos que contém, com contagem de palavras individual.

#### Exemplos

```bash
# Pack básico com defaults
dograpper pack ./rust-docs -o ./chunks

# Limites mais apertados
dograpper pack ./rust-docs -o ./chunks --max-words-per-chunk 300000 --max-chunks 30

# Agrupar por módulo, filtrar imagens e 404
dograpper pack ./rust-docs -o ./chunks \
  --strategy semantic \
  --ignore "*.png" \
  --ignore "**/404.html"

# Sem cabeçalho, formato txt
dograpper pack ./rust-docs -o ./chunks --no-index --format txt

# Sem extração inteligente (HTML integral)
dograpper pack ./rust-docs -o ./chunks --no-extract

# Com contagem de tokens no resumo
dograpper pack ./rust-docs -o ./chunks --show-tokens

# Tokens com encoding específico (GPT-4o)
dograpper pack ./rust-docs -o ./chunks --show-tokens --token-encoding o200k

# Simulação sem escrever arquivos (dry-run)
dograpper pack ./rust-docs -o ./chunks --dry-run

# Deduplicação exata (remove blocos repetidos entre páginas)
dograpper pack ./rust-docs -o ./chunks --dedup exact

# Deduplicação completa (exact + fuzzy) com threshold conservador
dograpper pack ./rust-docs -o ./chunks --dedup both --dedup-threshold 2

# Dry-run com dedup e tokens para calibrar parâmetros
dograpper pack ./rust-docs -o ./chunks --dedup both --show-tokens --dry-run

# Com cabeçalho de contexto (breadcrumb de headings por arquivo)
dograpper pack ./rust-docs -o ./chunks --context-header

# Combo: dedup + contexto + tokens
dograpper pack ./rust-docs -o ./chunks --dedup both --context-header --show-tokens
```

### Flags globais

| Flag | Alias | Default | Descrição |
|---|---|---|---|
| `--verbose` | `-v` | `false` | Log detalhado (DEBUG) |
| `--quiet` | `-q` | `false` | Apenas erros críticos |
| `--config` | — | `.dograpper.json` | Arquivo de configuração |

`--verbose` e `--quiet` são mutuamente exclusivos.

---

## Configuração

Crie um arquivo `.dograpper.json` na raiz do projeto para evitar repetir flags:

```json
{
  "download": {
    "depth": 3,
    "include-extensions": "html,md",
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

**Precedência**: defaults do código → `.dograpper.json` → flags da CLI. Flags da CLI sempre vencem.

Use `--config` para apontar para um arquivo diferente:

```bash
dograpper --config ./projects/rust/.dograpper.json pack ./rust-docs -o ./chunks
```

---

## Arquivo `.docsignore`

Crie um `.docsignore` na raiz do projeto para excluir arquivos do pack (sintaxe gitignore):

```gitignore
# Imagens
*.png
*.jpg
*.gif
*.svg

# Binários
*.pdf
*.zip
*.tar.gz

# Páginas indesejadas
**/404.html
**/changelog/**
```

O arquivo pode ser customizado via `--ignore-file` ou complementado com `--ignore` inline.

---

## Resumo de output

Ao final do `pack`, o dograpper exibe um resumo:

```
Pack complete:
  Files processed: 47
  Files excluded:  12
  Chunks generated: 5 / 50 (max)
  Words per chunk:  ~94.000 avg (min: 78.230, max: 112.400)
  Total words:     470.120
  Output:          ./chunks/
```

Com `--show-tokens`, linhas adicionais são exibidas:

```
  Tokens per chunk: ~127.000 avg (min: 105.610, max: 151.740)
  Total tokens:    634.800
  Encoding:        cl100k_base
```

Com `--dedup`, linhas adicionais são exibidas:

```
  Dedup mode:        both
  Blocks analisados: 128
  Blocks removidos:  11 (11 exact + 0 fuzzy)
  Palavras removidas: 256 (~1%)
```

Com `--dry-run`, nenhum arquivo é escrito. Um relatório completo é exibido:

```
Dry-run report (nenhum arquivo foi escrito):
───────────────────────────────────────────────────────

  Arquivos encontrados:  47
  Arquivos excluídos:    12
  Arquivos processados:  35

  Palavras (bruto):      52,000
  Palavras (extraído):   41,500
  Redução por extração:  20%

  Estratégia:            size
  Limite por chunk:      500,000 palavras
  Chunks projetados:     1 / 50 (max)

  Top 10 arquivos por palavras (após extração):
  ─────────────────────────────────────────────────────
   1. api/index.html                            9,634 words  (-27%)
   ...

───────────────────────────────────────────────────────
Ajuste parâmetros e rode sem --dry-run para empacotar.
```

Warnings são exibidos quando:
- Um arquivo individual excede `--max-words-per-chunk` (é colocado sozinho em um chunk)
- O total de chunks excede `--max-chunks`

---

## Arquitetura

```
src/dograpper/
├── cli.py                  # Entry point, grupo click, flags globais
├── commands/
│   ├── download.py         # Orquestração do download
│   └── pack.py             # Orquestração do pack
├── lib/
│   ├── chunker.py          # Estratégias de chunking e escrita de chunks
│   ├── config_loader.py    # Merge de configuração com precedência
│   ├── ignore_parser.py    # Filtro de arquivos (usa pathspec)
│   ├── manifest.py         # Leitura/escrita de manifest JSON
│   ├── playwright_crawl.py # Crawler headless para SPAs
│   ├── spa_detector.py     # Heurística de detecção de SPA
│   └── wget_mirror.py      # Wrapper do wget --mirror
└── utils/
    ├── content_extractor.py # Extração inteligente de conteúdo HTML (remove boilerplate)
    ├── dedup.py            # Deduplicação cross-file (exact MD5 + fuzzy SimHash)
    ├── dry_run_report.py   # Relatório de simulação do pack (--dry-run)
    ├── heading_extractor.py # Extração de headings HTML para cabeçalho de contexto
    ├── html_stripper.py    # Conversão de HTML para texto puro (stdlib html.parser)
    ├── logger.py           # Setup de logging
    ├── token_counter.py    # Contagem de tokens (tiktoken opcional, fallback estimativa)
    └── word_counter.py     # Contagem de palavras
```

---

## Desenvolvimento

```bash
# Instalar em modo editável com dependências de dev (pytest incluso)
uv sync --extra dev

# Rodar testes
uv run --extra dev pytest tests/ -v

# Rodar o CLI
uv run dograpper --help
uv run dograpper download --help
uv run dograpper pack --help
```

Cada subcomando aceita `-h` como atalho para `--help` e exibe exemplos práticos no rodapé.

---

## Licença

MIT