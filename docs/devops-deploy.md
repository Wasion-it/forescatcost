# DevOps e deploy

## Padrão de produção

O Forecast é publicado com imagens imutáveis no Registry Wasion e executado em Docker Swarm.

Imagens:

- `registry.wasion.com.br/wasion/forecast-backend:sha-<commit>`
- `registry.wasion.com.br/wasion/forecast-frontend:sha-<commit>`

A stack de produção é stateless. O PostgreSQL de produção deve ser externo à stack da aplicação.

## Docker Swarm Secrets obrigatórias

Criar previamente no manager do Swarm:

- `forecast_database_url`: URL SQLAlchemy completa do PostgreSQL de produção.
- `forecast_jwt_secret`: chave JWT forte e exclusiva do ambiente.

Os valores não devem ser versionados no GitHub nem armazenados no manifesto.

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
- `FORECAST_CORS_ORIGENS`
- `FORECAST_FRONTEND_PORT`

## Migrações

O backend executa `alembic upgrade head` antes de iniciar o Uvicorn. Migrações de produção devem permanecer compatíveis com a versão anterior durante atualizações `start-first`.
