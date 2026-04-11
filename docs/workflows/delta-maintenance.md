# Manutenção Incremental com Delta Pack

## O problema
Re-processar documentação inteira a cada update é lento e gera
diff desnecessário em pipelines de CI/CD.

## Solução: --delta
```bash
# Primeira vez: pack completo
dograpper pack ./docs -o ./chunks

# Updates: apenas o que mudou
dograpper pack ./docs -o ./chunks-delta --delta
```

## Sync: download + delta em um comando
```bash
dograpper sync <url> -o ./docs
```

## CI/CD
```yaml
# GitHub Actions example
- run: dograpper sync ${{ env.DOCS_URL }} -o ./docs
- run: dograpper pack ./docs -o ./chunks --delta --score
# Upload chunks-delta para o vector DB
```

## delta_manifest.json
Gerado automaticamente com mapeamento de arquivos added/modified/removed
e quais chunks foram gerados.
