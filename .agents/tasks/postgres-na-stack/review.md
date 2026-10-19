# PostgreSQL leve dentro da stack Swarm de produção

A mudança adiciona o serviço `postgres` (`postgres:16-alpine`) ao `docker-compose.prod.yml`, com volume nomeado, healthcheck e senha vinda de Docker secret. O backend deixa de ler a secret `forecast_database_url` e passa a montar a `DATABASE_URL` a partir de `forecast_postgres_password`. O `alembic upgrade head` ganhou um laço de retry no `command`. O workflow de deploy passou a exigir as novas secrets e a esperar o postgres convergir antes do backend. A grafia do CORS foi corrigida para `FORECAST_CORS_ORIGINS`, e o `docs/devops-deploy.md` foi atualizado.

Watch for: nenhum bloqueio encontrado. Pontos não bloqueantes: o laço de retry também repete em falha real de migration (confirmed), rotação da secret não altera a senha de um volume já inicializado (likely), e o comportamento em Swarm real não foi testado (a evidência cobre só compose config, `sh -n` e simulação do laço).

**Verdict**: APPROVED

## High-level view

O postgres roda como réplica única fixada no manager, com dados em volume local e acesso apenas pela overlay `forecast_internal`. Não há `ports:`. A senha chega por `POSTGRES_PASSWORD_FILE` apontando para `/run/secrets/...`, e o backend lê o mesmo arquivo dentro do `command`.

A inicialização do backend tolera o banco subir devagar: até 30 tentativas de 2s no `alembic`, janela de pelo menos 60s, menor que o tempo que o HEALTHCHECK da imagem leva para marcar o container como unhealthy (~120s). O retry fica no `command` porque o `docker-entrypoint.sh` roda antes dele e não enxerga o `DATABASE_URL` exportado ali.

O workflow valida as duas secrets novas, publica a stack e só passa para a espera do backend depois que o postgres chega a `Running`. Com healthcheck definido, o Swarm só reporta `Running` depois de saudável. Os três artefatos (compose, workflow, docs) usam o mesmo contrato de secrets e a grafia corrigida do CORS.

<details>
<summary>Issues (3)</summary>

1. **Retry também em erro real de migration** (confirmed, não bloqueante) — o `until alembic upgrade head` repete 30 vezes inclusive quando a migration falha por erro de SQL, atrasando a falha em ~60s+. Opcional: distinguir indisponibilidade de banco (por exemplo `pg_isready`/tentativa de conexão) de erro de migration.
2. **Rotação da secret não altera senha existente** (likely, não bloqueante) — `POSTGRES_PASSWORD_FILE` só é usado na criação do volume. Trocar `forecast_postgres_password` depois quebra a conexão do backend. Documentar o procedimento (`ALTER USER` antes de rotacionar).
3. **Sem teste em Swarm real** (confirmed, não bloqueante) — não houve deploy, `alembic upgrade head` contra Postgres 16 nem `actionlint`. Validar no primeiro deploy.

</details>

<details>
<summary>Details</summary>

## Checagens obrigatórias a-f

**(a) Sem porta publicada: passa (confirmed).** O serviço `postgres` no compose não tem `ports:`, e só se conecta a `forecast_internal`. A rede é `attachable: true` (preexistente), então containers avulsos anexados à overlay podem alcançar o banco; a senha continua exigida.

**(b) Senha só por secret/_FILE: passa (confirmed).** O postgres usa `POSTGRES_PASSWORD_FILE: /run/secrets/forecast_postgres_password`; não existe `POSTGRES_PASSWORD` no manifesto de produção (o `docker-compose.yml` de dev e o `includes-test.yml` usam senhas de desenvolvimento/CI, fora do escopo). No backend, a senha é lida via `$(cat ...)` dentro do container, sem `set -x` e sem `echo` da URL; `docker service inspect` mostra só o caminho do arquivo. A senha entra na URL sem URL-encode; a doc restringe a senha a hexadecimal (`openssl rand -hex 24`), o que torna isso seguro. O workflow não valida o formato da senha. Uma senha com `@`, `/` ou `:` quebraria a URL (possible, mitigado pela doc).

**(c) Sem crash loop se o postgres demorar até ~60s: passa (confirmed).** O laço faz até 30 tentativas com `sleep 2`, cobrindo no mínimo 60s mais o tempo de cada tentativa. O HEALTHCHECK do `backend/Dockerfile` (`start-period=30s`, `interval=30s`, `retries=3`) só marca unhealthy depois de ~120s, então o Swarm não mata o task durante o retry. `psycopg[binary]` está em `pyproject.toml` e o `migrations/env.py` consome `DATABASE_URL` pelas settings, então o driver `postgresql+psycopg` e a variável exportada no command são os usados pelo alembic e pelo uvicorn. A evidência registrada inclui `sh -n` do script extraído e uma simulação com `alembic` falso falhando 2 vezes e passando na 3ª.

O efeito colateral do retry é o item 1 do resumo de Issues: um erro real de migration também é repetido 30 vezes antes de falhar.

**(d) Escape de `$`: passa (confirmed).** Todos os `$` do script do backend estão como `$$`: `$$(cat ...)` (duas vezes), `$$tentativa` (duas vezes) e `$$((tentativa + 1))`. A evidência confirma que `docker compose config` preservou `$$` e expandiu sem erro.

**(e) Espera do postgres não deixa passar postgres não saudável: passa (confirmed no script; likely quanto ao comportamento do Swarm).** O laço roda logo após o `docker stack deploy` e antes da espera do backend. Só `grep -q '^Running'` encerra com sucesso; na 24ª iteração sem `Running` ele imprime os logs e faz `exit 1`. O script roda com `set -e` e `script_stop: true`, então falha de `docker service ps` também interrompe o deploy (fail-closed). Como o serviço tem healthcheck (`pg_isready`), o Swarm mantém o task em `Starting` até ficar saudável, portanto `Running` implica saudável. Comportamento do estado `Starting` em Swarm real não foi testado.

**(f) Contrato de secrets e grafia: passa (confirmed).** Compose (`secrets:` do backend, do postgres e bloco externo), workflow (laço de validação e mensagem de criação) e docs listam exatamente `forecast_postgres_password` e `forecast_jwt_secret`. `git grep` em `forecast_database_url|CORS_ORIGENS` no worktree não deixa referência a `forecast_database_url`. As ocorrências restantes de `CORS_ORIGENS` são o nome da variável interna do backend (`backend/app/core/config.py`, `.env.example`, `docker-compose.yml` de dev e a chave `CORS_ORIGENS:` no compose de produção), que não são a grafia `FORECAST_CORS_ORIGENS`. `deploy-production.yml` já usava `FORECAST_CORS_ORIGINS` e agora o compose o consome.

## Rotação de senha em volume já inicializado

`POSTGRES_PASSWORD_FILE` só é lido pela imagem na primeira subida com volume vazio. A doc descreve a criação inicial da secret, mas não avisa que recriar a secret com novo valor não troca a senha do role `forecast` em `forecast_pgdata`; o backend passaria a falhar na conexão e o retry de 30 tentativas terminaria em `exit 1` em loop de restart. Não é regressão (a stack nunca teve banco próprio), mas vale uma linha na doc.

## Cobertura e lacunas de verificação

A evidência em `verificacao.md` cobre `docker compose config`, `sh -n` do command e do script do workflow, parse YAML dos dois workflows e `git grep`. Não cobre: `actionlint`, deploy em Swarm real (secrets, placement no manager, criação do database por `POSTGRES_DB`, convergência), nem `alembic upgrade head` contra Postgres 16. Nenhum código de backend/frontend mudou, então a ausência de testes de aplicação é coerente. O backup via `docker exec $(docker ps -q -f name=forecast_postgres) pg_dump` na doc depende de o filtro casar um único container no nó manager (confirmed pelo placement fixo).

Pontos menores, não bloqueantes: imagem em tag flutuante `16-alpine` (sem digest) e sem `stop_grace_period` explícito para o postgres (default 10s costuma bastar com shutdown rápido).

</details>

<details>
<summary>File map</summary>

- `docker-compose.prod.yml`: novo serviço `postgres`, volume `forecast_pgdata`, secret `forecast_postgres_password`, command do backend com `DATABASE_URL` montada e retry de migrations, CORS corrigido.
- `.github/workflows/includes-remote-deploy.yml`: lista de secrets exigidas atualizada, instruções de criação, espera de convergência do postgres, `docker service ps` extra no erro do backend.
- `docs/devops-deploy.md`: contrato de secrets, seção do PostgreSQL da stack (volume, backup, aviso de remoção), variável CORS corrigida, texto de migrações.

Diff completo: `git diff origin/main...HEAD` em `.worktrees/postgres-na-stack`.

</details>
