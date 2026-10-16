# Forecast de Importação

Sistema web do PCM para prever custos e impostos de importação e entregar ao Financeiro a provisão mensal. A documentação funcional e técnica está em [docs/](docs/README.md).

| Camada | Tecnologia |
|--------|------------|
| Backend | Python 3.13, FastAPI, SQLAlchemy 2, Alembic, Pydantic v2 (pasta `backend/`, gerenciada com `uv`) |
| Banco | PostgreSQL 16 (Docker) |
| Frontend | React 19, TypeScript, Vite, TanStack Query (pasta `frontend/`) |

## Como rodar (desenvolvimento)

Pré-requisitos: Docker, [uv](https://docs.astral.sh/uv/) e Node.js 22.12+.

```powershell
# 1. Banco (porta 5433; cria também o banco forecast_test)
docker compose up -d db

# 2. Backend
cd backend
uv sync
Copy-Item .env.example .env          # ajuste se necessário
uv run alembic upgrade head
uv run python -m app.seed --exemplos # dados base + 9 processos de exemplo
uv run uvicorn app.main:app --reload --port 8000

# 3. Frontend (outro terminal)
cd frontend
npm install
npm run dev                          # http://localhost:5173 (proxy /api → :8000)
```

Usuários criados pelo seed (senha definida em `SEED_SENHA`, padrão `Forecast@2026!`):

| E-mail | Perfil |
|--------|--------|
| pcm@forecast.local | PCM: cadastra, calcula, mantém parâmetros |
| financeiro@forecast.local | Financeiro: consulta provisões e exporta |
| admin@forecast.local | Administrador: usuários, parâmetros, auditoria |

A documentação da API fica em http://localhost:8000/api/docs (desativada quando `AMBIENTE=prd`).

## Testes e qualidade

```powershell
cd backend
uv run pytest            # motor de cálculo + API contra o banco forecast_test
uv run ruff check .

cd ../frontend
npm test                 # vitest
npm run build            # typecheck + build
```

## O que o MVP entrega

- Cadastro, edição (com controle de concorrência), consulta e cancelamento de processos (DI ou DUIMP, ou só data prevista).
- Motor de cálculo puro com fórmulas versionadas em banco e avaliador seguro (sem `eval`), aritmética `Decimal` e regra de competência do dia 15.
- Cada cálculo é uma versão imutável, com memória por componente, snapshot de entradas e parâmetros e hash de integridade. O recálculo exige motivo.
- Parâmetros e alíquotas com vigência (sem sobreposição, garantida por constraint no PostgreSQL) e valores por escopo (tipo de importação, transportadora, terminal).
- Provisão mensal, por processo e por tipo, com exportação para Excel. Painel com série de 12 meses.
- Controle de acesso por permissões granulares e auditoria por trigger no banco (append-only, com usuário e campos alterados).

## Pendências conhecidas antes de produção

- Autenticação: o MVP usa login local com senha (bcrypt + JWT em `sessionStorage`). O alvo é SSO OIDC (Entra ID/Keycloak). Falta também limitar tentativas de login.
- Alíquotas e alguns parâmetros do seed são exemplos e precisam ser validados pelo Fiscal (ver `docs/01-visao-e-requisitos.md`, seção 7).
- Ficaram para a R1: editor de fórmulas com aprovação, simulação de cenários, fechamento de competência e recálculo em lote.
- Validar os valores com os golden cases das planilhas atuais (período paralelo).
