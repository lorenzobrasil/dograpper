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

Para sites SPA (React, Next.js, Mintlify, Docusaurus, etc.), a camada 4
da cascade usa `playwright`:

```bash
uv sync --extra headless
uv run playwright install chromium
```

No Linux, o Chromium exige libs nativas. Em Ubuntu 22.04+ / Debian 12+:

```bash
sudo apt install -y libnspr4 libnss3 libatk1.0-0 libatk-bridge2.0-0 \
  libcups2 libdrm2 libxkbcommon0 libxcomposite1 libxdamage1 libxfixes3 \
  libxrandr2 libgbm1 libpango-1.0-0 libcairo2 libasound2t64
```

Em Ubuntu ≤22.04 o pacote chama `libasound2` (sem o sufixo `t64`).

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

#### Cascade de descoberta (4 camadas)

`download` tenta as fontes de URL em ordem de autoridade, caindo para a
próxima quando a anterior falha ou retorna menos de 3 URLs utilizáveis
(threshold `MIN_URLS_TO_CONSIDER_DISCOVERED`):

1. **`llms.txt`** ([llmstxt.org](https://llmstxt.org)) — índice canônico
   de docs mantido por Mintlify, Anthropic, Stripe. Parser aceita links
   markdown e URLs bare, com fallback para `llms-full.txt`.
2. **`sitemap.xml`** — `sitemapindex` recursivo, gzip automático, escopo
   por **same-netloc OU path-prefix canonicalizado**. Cobre hosts tipo
   Mintlify cujo sub-sitemap fica em CDN (`www.mintlify.com/<projeto>/`)
   mas o path identifica o projeto. Probe também tenta `sitemap_index.xml`
   e `sitemap-index.xml`.
3. **`wget --mirror`** — link-graph crawl tradicional, `User-Agent` de
   Chrome/120 para não ser bloqueado por edge WAFs (Cloudflare, Vercel).
   Executa com `--no-parent`, `--timestamping` (sempre, permite incremental
   via mtime diff), `--convert-links`, `--adjust-extension`, `--page-requisites`.
4. **Playwright (hidratação bounded)** — fallback para SPAs:
   `domcontentloaded` 10s + espera de `a[href]` 5s + 500ms de grace
   (máx 15.5s). Substitui `networkidle` que podia travar em 30s em SPAs
   com RUM beacons.

As camadas 1 e 2 rodam **mesmo com `--headless`**, pois Mintlify e afins
publicam índices autoritativos que são o sinal mais forte em SPAs. Quando
uma camada 1+2 vence, suas URLs são entregues via `wget -i` (com
`--no-parent` + `--timestamping`) ou como `seed_urls` para o Playwright.

**Heurísticos anti-shell**:
- Se `wget -i` trouxer páginas vazias → cascade re-hidrata as mesmas
  URLs no Playwright (`is_spa(output)`).
- Se `wget --mirror` produzir ≤1 arquivo HTML → assume que a recursão
  falhou (site client-rendered) e pula para Playwright.

#### Observabilidade

Cada camada emite uma linha de log `[cascade] layer-N ...` prefixada,
fácil de grepar:

```
INFO: [cascade] layer-1 llms.txt: probing
INFO: [cascade] layer-1 llms.txt: raw=0 in-scope=0
INFO: [cascade] layer-2 sitemap.xml: probing
INFO: [cascade] layer-2 sitemap: raw=120 in-scope=120
INFO: [cascade] layer-2 sitemap: WIN (>=3)
INFO: [cascade] layer-3 wget -i: fetching 120 URLs from sitemap.xml
```

#### Incremental

Um manifest `.dograpper-manifest.json` é gerado após cada download,
registrando arquivos espelhados com hashes SHA-256 e mtimes. Re-execuções
futuras usam esse manifest + `wget --timestamping` para baixar apenas
arquivos alterados no servidor.

#### Exemplos

```bash
# Documentação do Rust, sem limite de profundidade
dograpper download https://docs.rust-lang.org -o ./rust-docs

# SPA com rate limiting
dograpper download https://react.dev --headless -o ./react-docs --delay 500

# Apenas HTML e Markdown, máximo 3 níveis
dograpper download https://docs.python.org/3/ -o ./python-docs -d 3 --include-extensions "html,md"

# Mintlify (layer 2 encontra sub-sitemap no CDN automaticamente)
dograpper download https://mintlify.wiki/user/projeto -o ./projeto-docs
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
| `--bundle` | — | *(nenhum)* | Preset: `notebooklm` ou `rag-standard` |
| `--score` | — | `false` | Calcula LLM Readiness Score e gera `llm-readiness.json` |

#### Pipeline interna de pack

A ordem de operações (cada etapa lê o output da anterior):

```
list files → apply .docsignore → --no-extract? sim: HTML integral / não: extract
           → --dedup → --strategy (size|semantic) → chunking boundary-aware
           → --cross-refs? anotar → --context-header? injetar → --score? anotar
           → --format (md|txt|jsonl) → write → --bundle? guide + cap
```

#### Extração inteligente (ativa por padrão)

Antes de empacotar, o dograpper extrai apenas o conteúdo principal de
cada HTML. Ordem de preferência:

1. Selectors semânticos (`<main>`, `<article>`, `[role=main]`).
2. Scoring por densidade de texto (melhor `<div>` por ratio texto/tags).
3. Fallback: HTML integral com strip de `<script>`, `<style>`, `<nav>`,
   `<footer>`.

Blacklist remove: breadcrumbs, botões "copy to clipboard", banners de
versão, widgets de busca, edit-on-github. Use `--no-extract` para manter
o HTML integral.

#### Deduplicação (`--dedup`)

Remove blocos de texto duplicados entre arquivos (headers, footers,
disclaimers, navegação). Três modos:

- **`exact`** — MD5 hash de bloco normalizado (lowercase + whitespace
  colapsado). Zero falso-positivo.
- **`fuzzy`** — SimHash 64-bit + distância de Hamming ≤ `--dedup-threshold`.
  Detecta variações triviais ("página X de Y", timestamps).
- **`both`** — exact primeiro (barato), depois fuzzy nos restantes.

Blocos com <10 palavras são ignorados (previne falso-positivo em `<h1>`
repetidos). A primeira ocorrência (ordem alfabética) é sempre preservada.

#### Cabeçalho de contexto (`--context-header`)

Injeta metadados estruturados no formato `dograpper-context-v1` (JSON
dentro de comentário HTML) no topo de cada arquivo dentro do chunk.
Campos:

```json
{
  "source": "flask.palletsprojects.com/en/stable/quickstart/index.html",
  "context_breadcrumb": ["Quickstart", "Routing"],
  "chunk_index": 2,
  "total_chunks": 5,
  "word_count": 4820,
  "url": "https://flask.palletsprojects.com/en/stable/quickstart/",
  "llm_readiness": {"score": 0.92, "grade": "A"},
  "schema_version": "v1"
}
```

Campos opcionais (`url`, `llm_readiness`) são omitidos quando não
disponíveis (nunca aparecem como `null`). Spec completa:
[docs/schema-v1.md](docs/schema-v1.md).

#### Referências cruzadas (`--cross-refs`)

Extrai links internos dos HTMLs, resolve caminhos relativos, mapeia cada
destino para o chunk onde o arquivo foi empacotado e gera
`cross_refs.json` com listas `references_to`, `referenced_by` e `links`
por chunk. O texto é anotado in-place com marcadores `[-> chunk_id]`,
permitindo que LLMs naveguem entre chunks.

Links que apontam para arquivos excluídos via `.docsignore` aparecem
como `unresolved` (contados no summary).

#### Formato JSONL (`--format jsonl`)

Cada chunk vira um arquivo `.jsonl` onde cada linha é um objeto por
source file. Ideal para pipelines RAG com chunking próprio downstream.

Schema (campos obrigatórios em **negrito**, opcionais em itálico):

- **`id`** — identificador único do registro
- **`source`** — path relativo do arquivo original
- **`words`** — contagem de palavras
- **`content`** — texto extraído
- **`schema_version`** — `"v1"`
- *`breadcrumb`, `chunk_index`, `total_chunks`* (com `--context-header`)
- *`url`* (quando disponível via manifest)
- *`readiness_grade`* (com `--score`)

#### LLM Readiness Score (`--score`)

Pontuação 0–1 por chunk, derivada de três métricas ponderadas:

| Métrica | Peso | O que mede |
|---|---|---|
| `noise_ratio` | 40% | Proporção de boilerplate remanescente após extração |
| `boundary_integrity` | 30% | Fração de blocos de código/tabelas não quebrados |
| `context_depth` | 30% | Profundidade média de headings (proxy de hierarquia) |

Grade final:
- **A** — score ≥ 0.8 (pronto pra uso direto)
- **B** — 0.6 ≤ score < 0.8 (utilizável, considere refinar extração)
- **C** — score < 0.6 (revisar `.docsignore` ou rodar `--dedup`)

Resultados salvos em `llm-readiness.json`. Quando combinado com
`--context-header` ou `--format jsonl`, o grade é injetado nos
cabeçalhos/registros.

#### Presets (`--bundle`)

Atalhos para combinações comuns. O preset **define os defaults**; flags
explícitas na CLI sobrescrevem.

| Preset | `max-chunks` | `max-words-per-chunk` | `strategy` | `format` | Gera |
|---|---|---|---|---|---|
| `notebooklm` | 50 | 400.000 | `semantic` | `md` | `IMPORT_GUIDE.md` |
| `rag-standard` | 500 | 50.000 | `size` | `jsonl` | — |

Exemplo combinando preset com score:

```bash
dograpper pack ./docs -o ./chunks --bundle notebooklm --context-header --score
```

#### Dry-run (`--dry-run`)

Simula sem escrever. Exibe: contagem de arquivos, palavras, projeção de
chunks, top 10 por tamanho, warnings. Usar para calibrar parâmetros antes
do pack final.

#### Estratégias de chunking

- **`size`** (default) — percorre arquivos em ordem alfabética, acumulando
  palavras. Corta ao atingir `--max-words-per-chunk`. Boundary-aware:
  preserva blocos de código/tabelas atômicos.
- **`semantic`** — agrupa arquivos do mesmo diretório (módulo) no mesmo
  chunk antes de aplicar o limite. Preserva coesão temática. Grupos
  maiores que o limite são subdivididos.

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

Wrapper de conveniência: `download` + `pack --delta` em cadeia. Usa os
mesmos flags de `download` e `pack`, com defaults otimizados para
manutenção contínua.

```bash
dograpper sync <url> -o <dir> [opções]
```

| Opção | Alias | Default | Descrição |
|---|---|---|---|
| `--output` | `-o` | *obrigatório* | Diretório do mirror (HTML espelhado) |
| `--chunks-dir` | — | `<output>/chunks` | Diretório de saída dos chunks |
| `--depth` | `-d` | `0` | Profundidade máxima (passada ao `download`) |
| `--headless` | — | `false` | Playwright direto (passado ao `download`) |
| `--delay` | — | `0` | Rate limiting em ms (passado ao `download`) |
| `--max-words-per-chunk` | — | `500000` | Limite de palavras (passado ao `pack`) |
| `--max-chunks` | — | `50` | Limite de chunks (passado ao `pack`) |
| `--format` | — | `md` | `md` \| `jsonl` (passado ao `pack`) |
| `--bundle` | — | *(nenhum)* | Preset de `pack` |
| `--context-header` | — | `false` | Header v1 (passado ao `pack`) |
| `--score` | — | `false` | LLM Readiness (passado ao `pack`) |

O `pack` é sempre executado com `--delta` implícito — re-processa apenas
arquivos alterados no mirror.

#### Exemplos

```bash
# Sync completo com presets NotebookLM
dograpper sync https://docs.python.org/3/ -o ./py-docs --bundle notebooklm --context-header --score

# Sync diário em cron (incremental de verdade)
dograpper sync https://docs.rust-lang.org -o ./rust-docs --chunks-dir ./out/rust

# Sync SPA
dograpper sync https://react.dev -o ./react-docs --headless --delay 500
```

### Flags globais

| Flag | Alias | Default | Descrição |
|---|---|---|---|
| `--verbose` | `-v` | `false` | Log detalhado (DEBUG + `[cascade]` prefixes) |
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
| `IMPORT_GUIDE.md` | `--bundle notebooklm` | Guia de upload com ordem recomendada |
| `delta_manifest.json` | `--delta` | Mapeamento de arquivos alterados |
| `.dograpper-manifest.json` | `download` | Manifest do mirror (hashes + mtimes) |

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

**Precedência**: defaults do código → `.dograpper.json` → flags da CLI.
Flags da CLI sempre vencem. Internamente isso usa
`ctx.get_parameter_source()` do Click para distinguir defaults implícitos
de valores explícitos.

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

O arquivo pode ser customizado via `--ignore-file` ou complementado com
`--ignore` inline (repetível).

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

Linhas adicionais condicionais (por flag ativada):

| Flag | Linhas extras |
|---|---|
| `--show-tokens` | `Tokens per chunk`, `Total tokens`, `Encoding` |
| `--dedup` | `Dedup mode`, `Blocks analisados`, `Blocks removidos`, `Palavras removidas` |
| `--cross-refs` | `Cross-refs: ./chunks/cross_refs.json (N links, M unresolved)` |
| `--score` | `LLM Readiness: ./chunks/llm-readiness.json`, `Grade distribution` |
| `--delta` | `Delta: N added, M modified, K removed`, `Delta manifest: ...` |

Warnings aparecem quando:
- Um arquivo individual excede `--max-words-per-chunk` (é colocado sozinho
  em um chunk, ultrapassando o limite declarado)
- O total de chunks excede `--max-chunks` (os excedentes são descartados
  com aviso; use `--bundle` para comportamento determinístico)

---

## Troubleshooting

### `download` baixa apenas 1 arquivo

Site é SPA client-rendered sem `llms.txt` nem `sitemap.xml` acessível.
O heurístico anti-shell detecta isso e cai para Playwright automaticamente
— se não cair, verifique se `playwright` está instalado com as libs do
sistema (veja [Instalação](#instalação)).

Log esperado com cascade funcionando:

```
INFO: [cascade] layer-3 wget --mirror: link-graph fallback
INFO: [cascade] layer-4 playwright: --mirror yielded only 1 HTML file(s) (likely client-rendered index)
INFO: SPA detected, falling back to playwright
```

### `libnspr4.so: cannot open shared object file`

Libs do sistema faltando pro Chromium. Rode o apt install da seção
[Dependências do sistema](#dependências-do-sistema).

### Sub-sitemaps cross-host sendo rejeitados

Desde a cascade v1.1, sub-sitemaps em hosts diferentes são aceitos se o
`path-prefix` identificar o projeto (same-netloc **OR** path-prefix).
Cobre Mintlify (sub-sitemap em `www.mintlify.com/<proj>/sitemap.xml`).
Se ainda rejeitar, rode com `-v` para ver a decisão no log
(`sitemap: skipping out-of-scope sub-sitemap`).

### `pack --delta` re-processa tudo na primeira rodada

Comportamento esperado: delta compara contra o manifest da rodada anterior.
Primeira rodada não tem baseline, então todos os arquivos são "added".
Re-execuções subsequentes usam `.dograpper-manifest.json` + mtimes.

### Chunks muito grandes pra NotebookLM

Use `--bundle notebooklm` (limite de 400k words/chunk) + `--strategy semantic`
pra manter módulos coesos. Se ainda estourar, reduza `--max-words-per-chunk`
progressivamente e combine com `--dedup both`.

### `wget returned 8` mas download parece ok

Exit code 8 do wget significa "server error em alguns URLs" — tratado
como sucesso parcial. O manifest registra apenas os arquivos efetivamente
baixados. Rodar novamente (incremental) costuma fechar os gaps.

---

## Arquitetura

```
src/dograpper/
├── cli.py
├── commands/
│   ├── download.py           # Cascade 4-layer + orquestração
│   ├── pack.py
│   └── sync.py               # download + pack delta
├── lib/
│   ├── chunker.py            # Estratégias size/semantic, boundary-aware
│   ├── config_loader.py
│   ├── ignore_parser.py
│   ├── llms_txt_parser.py    # Layer 1 (stdlib-only)
│   ├── sitemap_parser.py     # Layer 2 (sitemapindex recursivo, gzip)
│   ├── url_filter.py         # Same-netloc + path-prefix + depth
│   ├── manifest.py           # Manifest + diff_manifests()
│   ├── playwright_crawl.py   # Layer 4 (bounded hydration + seed_urls)
│   ├── spa_detector.py       # Small-sample branch (N<5)
│   └── wget_mirror.py        # Layer 3 (run_wget_mirror + run_wget_urls)
└── utils/
    ├── content_extractor.py  # Extração inteligente (remove boilerplate)
    ├── dedup.py              # Dedup cross-file (exact + fuzzy)
    ├── dry_run_report.py
    ├── heading_extractor.py  # Headings + format_context_header (v1)
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
# Instalar em modo editável com dependências de dev
uv sync --extra dev

# Rodar testes
uv run pytest tests/ -v

# Rodar um módulo específico
uv run pytest tests/test_download_cascade.py -v

# Rodar o CLI
uv run dograpper --help
uv run dograpper download --help
uv run dograpper pack --help
```

Cada subcomando aceita `-h` como atalho para `--help` e exibe exemplos
práticos no rodapé.

---

## Licença

MIT
