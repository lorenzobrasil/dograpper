# dograpper

**Context Engineering Pipeline for Deterministic LLM Ingestion**

Transforma documentação HTML em contexto estruturado, dedupicado, pontuado
e versionado — pronto para ingestão em NotebookLM, RAG pipelines, Claude
Projects e fine-tuning.

## O problema

LLMs estáticos não navegam na web. Quando recebem documentação crua como
contexto, sofrem com: boilerplate (navbars, footers, banners), duplicação
entre páginas, chunks sem hierarquia, e blocos de código cortados ao meio.
O resultado é degradação de retrieval e alucinação.

## A solução

`dograpper` é uma pipeline determinística que resolve cada etapa:

```
URL → Mirror → Extract → Dedup → Score → Chunk → Export (MD/JSONL)
```

| Etapa | O que faz | Flag |
|-------|-----------|------|
| **Mirror** | Espelha site localmente via wget/playwright | `download` |
| **Extract** | Remove boilerplate, preserva conteúdo principal | (automático) |
| **Dedup** | Elimina blocos repetidos entre páginas | `--dedup` |
| **Score** | Audita qualidade do contexto por chunk | `--score` |
| **Chunk** | Agrupa respeitando limites, preservando blocos de código | `pack` |
| **Context** | Injeta breadcrumb, metadados, schema versionado | `--context-header` |
| **Export** | MD, JSONL, com cross-refs e guia de importação | `--format`, `--cross-refs` |

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
# Pipeline completa: download + pack otimizado para NotebookLM
dograpper download https://flask.palletsprojects.com/en/stable/ -o ./flask-docs
dograpper pack ./flask-docs -o ./chunks --bundle notebooklm --context-header --score

# Ou em um comando:
dograpper sync https://flask.palletsprojects.com/en/stable/ -o ./flask-docs

# Para RAG: export JSONL com cross-references
dograpper pack ./flask-docs -o ./chunks --format jsonl --cross-refs --score

# Updates incrementais (só reprocessa o que mudou)
dograpper pack ./flask-docs -o ./chunks --delta
```

---

## Casos de uso

### NotebookLM
```bash
dograpper pack ./docs -o ./chunks --bundle notebooklm --context-header --score
# Gera ≤50 chunks balanceados + IMPORT_GUIDE.md com ordem de upload
```

### RAG / Vector DB
```bash
dograpper pack ./docs -o ./chunks --format jsonl --cross-refs --score
# JSONL pronto para embeddings, com grafo de referências cruzadas
```

### Manutenção incremental (CI/CD)
```bash
dograpper sync <url> -o ./docs
# Download incremental + pack delta automático
```

### Ambientes air-gapped
Zero chamadas externas após o download. Sem telemetria. Manifest auditável.
Ideal para RAG corporativo e ambientes regulados.

---

## Comandos

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

**Detecção automática de SPA**: se o wget capturar apenas shells HTML vazios (típico de React/Next.js), o dograpper detecta isso automaticamente e refaz o mirror com playwright. Use `--headless` para pular direto para playwright quando já souber que o site é uma SPA.

**Downloads incrementais**: um arquivo de manifest é gerado após cada download, registrando os arquivos espelhados. Re-execuções futuras usam esse manifest como referência.

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

Processa e agrupa arquivos em chunks otimizados para ingestão por LLMs.

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
| `--format` | — | `md` | Formato de saída: `txt`, `md`, `jsonl` |
| `--no-extract` | — | `false` | Desativa extração inteligente de conteúdo HTML |
| `--show-tokens` | — | `false` | Exibe contagem de tokens no resumo final |
| `--token-encoding` | — | `cl100k` | Encoding do tokenizer: `cl100k`, `o200k`, `p50k` |
| `--dry-run` | — | `false` | Simula o pack sem escrever arquivos; exibe relatório |
| `--dedup` | — | `off` | Deduplicação de blocos: `off`, `exact`, `fuzzy`, `both` |
| `--dedup-threshold` | — | `3` | Distância de Hamming máxima para dedup fuzzy (0-10) |
| `--context-header` | — | `false` | Injeta header `dograpper-context-v1` (JSON estruturado) |
| `--cross-refs` | — | `false` | Gera `cross_refs.json` e anota chunks com `[-> chunk_id]` |
| `--delta` | — | `false` | Reprocessa apenas arquivos alterados desde o último pack |
| `--manifest` | — | `.dograpper-manifest.json` | Manifest do download para comparação delta |
| `--bundle` | — | *(nenhum)* | Preset: `notebooklm` (≤50 chunks) ou `rag-standard` |
| `--score` | — | `false` | Calcula LLM Readiness Score e gera `llm-readiness.json` |

**Extração inteligente** (ativa por padrão): antes de empacotar, o dograpper extrai apenas o conteúdo principal de cada HTML (usando `<main>`, `<article>`, ou scoring por densidade), removendo boilerplate como navbars, sidebars, footers, breadcrumbs, botões "copy to clipboard", banners de versão, etc. Use `--no-extract` para manter o HTML integral.

**Deduplicação** (`--dedup`): remove blocos de texto duplicados entre arquivos. Comum em sites que repetem headers, footers, disclaimers ou blocos de navegação em várias páginas. Três modos:
- `exact` — remove blocos idênticos (normalizado por case e whitespace) via hash MD5
- `fuzzy` — remove blocos quase idênticos via SimHash + distância de Hamming (controlada por `--dedup-threshold`)
- `both` — aplica exact primeiro, depois fuzzy nos blocos restantes

Blocos com menos de 10 palavras são ignorados para evitar falsos positivos. A primeira ocorrência (ordem alfabética de arquivo) é sempre preservada.

**Cabeçalho de contexto** (`--context-header`): injeta metadados estruturados no formato `dograpper-context-v1` (JSON dentro de comentário HTML) no topo de cada arquivo dentro do chunk. Inclui: `source`, `breadcrumb` (hierarquia de headings), `chunk_index`/`total_chunks`, `word_count`, `url` (quando disponível via manifest) e `readiness_grade` (quando `--score` está ativo). Campos opcionais são omitidos em vez de nulls. Spec completa: [docs/schema-v1.md](docs/schema-v1.md).

**Referências cruzadas** (`--cross-refs`): extrai links internos de arquivos HTML, resolve caminhos relativos, mapeia cada link para o chunk de destino e gera `cross_refs.json`. O JSON contém listas de `references_to`, `referenced_by` e `links` por chunk. O texto dos chunks é anotado in-place com marcadores `[-> chunk_id]`, permitindo que LLMs naveguem entre chunks.

**Formato JSONL** (`--format jsonl`): gera um arquivo `.jsonl` por chunk, onde cada linha é um objeto JSON representando um arquivo ou sub-chunk. Campos: `id`, `source`, `words`, `content`, `schema_version` (`"v1"`), e opcionais: `breadcrumb`, `chunk_index`, `total_chunks`, `url`, `readiness_grade`. Ideal para pipelines RAG.

**LLM Readiness Score** (`--score`): calcula uma pontuação de qualidade por chunk baseada em três métricas: `noise_ratio` (40%), `boundary_integrity` (30%), `context_depth` (30%). O score final gera um grade: A (≥0.8), B (≥0.6), C (<0.6). Resultados são salvos em `llm-readiness.json`. Quando combinado com `--context-header` ou `--format jsonl`, o grade é injetado nos cabeçalhos/registros.

**Dry-run** (`--dry-run`): simula o pack sem escrever nenhum arquivo. Exibe relatório completo com contagem de arquivos, palavras, projeção de chunks, top 10 arquivos por tamanho, e warnings.

**Estratégia `size`** (default): percorre os arquivos em ordem alfabética, acumulando por contagem de palavras. Abre um novo chunk ao atingir o limite.

**Estratégia `semantic`**: agrupa arquivos do mesmo diretório (módulo) no mesmo chunk antes de aplicar o limite de palavras. Preserva a coesão temática. Grupos que excedem o limite são subdivididos automaticamente.

#### Exemplos

```bash
# Pack básico com defaults
dograpper pack ./rust-docs -o ./chunks

# Otimizado para NotebookLM
dograpper pack ./docs -o ./chunks --bundle notebooklm --context-header --score

# JSONL para RAG com cross-references
dograpper pack ./docs -o ./chunks --format jsonl --cross-refs --score

# Deduplicação completa + contexto + tokens
dograpper pack ./docs -o ./chunks --dedup both --context-header --show-tokens

# Dry-run para calibrar parâmetros
dograpper pack ./docs -o ./chunks --dry-run --dedup both --score --show-tokens

# Agrupar por módulo, filtrar imagens
dograpper pack ./docs -o ./chunks --strategy semantic --ignore "*.png"

# Updates incrementais (delta)
dograpper pack ./docs -o ./chunks --delta
```

### `dograpper sync`

Wrapper de conveniência: `download` + `pack --delta` em cadeia.

```bash
dograpper sync <url> -o <dir> [--chunks-dir <dir>] [--max-words-per-chunk N] [--format md|jsonl]
```

### Flags globais

| Flag | Alias | Default | Descrição |
|---|---|---|---|
| `--verbose` | `-v` | `false` | Log detalhado (DEBUG) |
| `--quiet` | `-q` | `false` | Apenas erros críticos |
| `--config` | — | `.dograpper.json` | Arquivo de configuração |

`--verbose` e `--quiet` são mutuamente exclusivos.

---

## Schema: `dograpper-context-v1`

Cada chunk inclui um header JSON estruturado e versionado (quando `--context-header` ativo):

```html
<!-- dograpper-context-v1
{
  "source": "flask.palletsprojects.com/en/stable/quickstart/index.html",
  "context_breadcrumb": ["Quickstart", "Routing"],
  "word_count": 4820,
  "llm_readiness": {"score": 0.92, "grade": "A"},
  "schema_version": "v1"
}
-->
```

Spec completa: [docs/schema-v1.md](docs/schema-v1.md)

---

## Artefatos gerados

| Artefato | Flag | Descrição |
|----------|------|-----------|
| `docs_chunk_*.md` | (default) | Chunks em Markdown |
| `docs_chunk_*.jsonl` | `--format jsonl` | Uma linha JSON por source file |
| `cross_refs.json` | `--cross-refs` | Grafo de referências entre chunks |
| `llm-readiness.json` | `--score` | Scores de qualidade por chunk |
| `IMPORT_GUIDE.md` | `--bundle` | Guia de upload com ordem recomendada |
| `delta_manifest.json` | `--delta` | Mapeamento de arquivos alterados |

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
    "with-index": true,
    "context-header": true,
    "score": true,
    "dedup": "both"
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

Com `--cross-refs`, uma linha adicional é exibida:

```
  Cross-refs:        ./chunks/cross_refs.json (42 links, 3 unresolved)
```

Com `--score`, linhas adicionais são exibidas:

```
  LLM Readiness:     ./chunks/llm-readiness.json
  Grade distribution: A: 3, B: 2
```

Warnings são exibidos quando:
- Um arquivo individual excede `--max-words-per-chunk` (é colocado sozinho em um chunk)
- O total de chunks excede `--max-chunks`

---

## Arquitetura

```
src/dograpper/
├── cli.py
├── commands/
│   ├── download.py
│   ├── pack.py
│   └── sync.py              # Orquestração download + pack delta
├── lib/
│   ├── chunker.py            # Estratégias size/semantic, boundary-aware, balance
│   ├── config_loader.py
│   ├── ignore_parser.py
│   ├── manifest.py           # Manifest + diff_manifests()
│   ├── playwright_crawl.py
│   ├── spa_detector.py
│   └── wget_mirror.py
└── utils/
    ├── content_extractor.py  # Extração inteligente (remove boilerplate)
    ├── dedup.py              # Dedup cross-file (exact + fuzzy)
    ├── dry_run_report.py
    ├── heading_extractor.py  # Headings + format_context_header (v1 schema)
    ├── html_stripper.py
    ├── link_extractor.py     # Cross-refs entre chunks
    ├── logger.py
    ├── scorer.py             # LLM Readiness Score
    ├── token_counter.py
    └── word_counter.py
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
