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
uv add playwright
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
    ├── logger.py           # Setup de logging
    └── word_counter.py     # Contagem de palavras
```

---

## Desenvolvimento

```bash
# Instalar em modo editável com dependências de dev
uv sync

# Rodar testes
uv run pytest tests/ -v

# Rodar o CLI
uv run dograpper --help
```

---

## Licença

MIT