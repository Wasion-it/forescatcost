# DevOps e deploy

## Padrão de produção

O Forecast é publicado com imagens imutáveis no Registry Wasion e executado em Docker Swarm.

Imagens:

- `registry.wasion.com.br/wasion/forecast-backend:sha-<commit>`
- `registry.wasion.com.br/wasion/forecast-frontend:sha-<commit>`

A stack de produção inclui um PostgreSQL leve (`postgres:16-alpine`) como serviço `postgres`, acessível apenas pela rede overlay `forecast_internal` (nenhuma porta é publicada no host). Backend e frontend continuam stateless.

## Deploy de produção em um clique

O workflow `Publicação de produção` segue o mesmo padrão operacional do Sistema-RH. O disparo é manual em **Actions → Publicação de produção → Run workflow** e não exige informar uma tag manualmente.

A execução usa automaticamente o commit selecionado no GitHub Actions e gera a tag imutável `sha-${github.sha}`. A sequência é:

1. preparar o ambiente `prod`;
2. executar testes backend/frontend;
3. validar o build lógico;
4. construir e validar as imagens Docker;
5. publicar as imagens no Registry Wasion;
6. executar o deploy no Docker Swarm;
7. validar o commit publicado via healthcheck;
8. registrar a annotation no Grafana;
9. criar a GitHub Release;
10. gerar o resumo final da publicação.

Assim, o mesmo commit que passou pelo pipeline é o commit empacotado, publicado, implantado e registrado na release.

## Docker Swarm Secrets obrigatórias

Criar previamente no manager do Swarm:

- `forecast_postgres_password`: senha do usuário `forecast` do PostgreSQL da stack.
- `forecast_jwt_secret`: chave JWT forte e exclusiva do ambiente.

Criação no manager do Swarm:

```bash
openssl rand -hex 24 | docker secret create forecast_postgres_password -
openssl rand -hex 32 | docker secret create forecast_jwt_secret -
```

A senha do banco deve conter apenas caracteres hexadecimais (`openssl rand -hex 24`). O backend monta a `DATABASE_URL` (`postgresql+psycopg://forecast:<senha>@postgres:5432/forecast`) a partir dessa senha, sem URL-encode; por isso caracteres especiais não são suportados.

Os valores não devem ser versionados no GitHub nem armazenados no manifesto.

## PostgreSQL da stack

O serviço `postgres` usa `POSTGRES_DB=forecast` e `POSTGRES_USER=forecast`. Na primeira subida, com o volume vazio, a imagem cria o database `forecast` e o usuário automaticamente, usando a senha da secret `forecast_postgres_password`. Nenhuma criação manual de database é necessária. O backend aguarda o banco ficar disponível (até 30 tentativas, a cada 2s) e então aplica as migrations.

Os dados ficam no volume nomeado `forecast_pgdata`, local ao nó manager (o serviço é fixado em `node.role == manager` para o volume não migrar). A atualização do banco usa `stop-first` para nunca haver dois PostgreSQL sobre o mesmo volume.

Backup com `pg_dump`:

```bash
docker exec $(docker ps -q -f name=forecast_postgres) pg_dump -U forecast forecast | gzip > backup.sql.gz
```

Atenção: remover o volume `forecast_pgdata` (por exemplo, `docker volume rm` ou `docker stack rm` seguido de limpeza de volumes) apaga todos os dados do banco. `docker stack rm` sozinho preserva o volume.

## Porta de publicação

Por padrão o frontend é publicado no host na porta `18080`. A variável `FORECAST_FRONTEND_PORT` pode alterar a porta durante o deploy.

O Nginx do frontend encaminha `/api/*` para o serviço backend dentro da rede overlay `forecast_internal`, portanto o backend não precisa publicar porta no host.

O reverse proxy corporativo (Nginx Proxy Manager no servidor de Production Apps) deve encaminhar o hostname público do Forecast para a porta publicada pelo frontend.

## Variáveis de deploy

- `BACKEND_IMAGE`
- `FRONTEND_IMAGE`
- `APP_VERSION`
- `APP_COMMIT`
- `APP_ENVIRONMENT`
- `FORECAST_CORS_ORIGINS`
- `FORECAST_FRONTEND_PORT`

## Migrações

O backend executa `alembic upgrade head` antes de iniciar o Uvicorn, repetindo a tentativa enquanto o PostgreSQL ainda não aceita conexões. Migrações de produção devem permanecer compatíveis com a versão anterior durante atualizações `start-first`.
