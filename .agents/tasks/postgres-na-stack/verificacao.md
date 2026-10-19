# Verificação: postgres-na-stack

Branch: `deploy/postgres-na-stack` (worktree `c:/Projects/forecast/.worktrees/postgres-na-stack`). Iteração 1 (não havia `review.json`).

## Executado

1. `docker compose -f docker-compose.prod.yml config` com variáveis fictícias (BACKEND_IMAGE, FRONTEND_IMAGE, APP_VERSION, APP_COMMIT, FORECAST_CORS_ORIGINS):
   - Docker 29.8.2 disponível. Expandiu sem erro (apenas avisos esperados de campos que só valem no Swarm e `version` obsoleto, este último preexistente).
   - Serviços: `postgres`, `backend`, `frontend`. Secrets: `forecast_postgres_password` e `forecast_jwt_secret` (ambas externas). Volume: `forecast_pgdata`.
   - `CORS_ORIGENS` recebeu o valor de `FORECAST_CORS_ORIGINS` (grafia corrigida).
   - `$$` foi preservado no command do backend (será `$` para o shell no container). `postgres` sem `ports`, com `node.role == manager`, `stop-first`, limites 512M/128M e healthcheck `pg_isready`.
2. Shell do command do backend: script extraído (`$$` -> `$`) e validado com `sh -n` (Git sh): OK. Simulação com `alembic` falso que falha 2 vezes e passa na 3ª: o laço tentou 3 vezes, seguiu para o `uvicorn` e a URL final ficou `postgresql+psycopg://forecast:<senha>@postgres:5432/forecast`.
3. `entrypoint`: confirmado por leitura que `docker-entrypoint.sh` roda antes do `command` (o `RUN_MIGRATIONS=true` não enxerga `DATABASE_URL` exportado no command). Por isso o retry ficou no command; entrypoint e Dockerfile não foram alterados.
4. `includes-remote-deploy.yml` e `deploy-production.yml`: `yaml.safe_load` OK. O script da etapa "Publicar aplicação no servidor" (com expressões `${{ }}` substituídas) passou em `sh -n`.
5. `git grep` por `forecast_database_url|FORECAST_CORS_ORIGENS` no worktree: nenhuma ocorrência restante.
6. Arquivos temporários removidos (`%TEMP%/fc_*`).

## NÃO verificado

- `actionlint` não está instalado; não foi executado.
- Deploy real no Swarm (secrets, runner self-hosted, registry, criação automática do database pelo `POSTGRES_DB`, placement no manager, convergência dos serviços, `/api/v1/health`): depende do servidor e do runner, não foi testado.
- Execução real do `alembic upgrade head` contra o Postgres 16 não foi feita; só a simulação do laço de retry.
- Nenhum teste da aplicação foi executado (sem alteração em backend/frontend).
