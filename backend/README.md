# Backend do Forecast de Importação

API FastAPI. Instruções de execução e testes no [README da raiz](../README.md).

- `app/calculo/engine/`: motor de cálculo puro (avaliador seguro, pipeline, competência)
- `app/calculo/formulas_padrao.py`: componentes e fórmulas v1 (fonte do seed e dos testes)
- `app/modules/`: rotas e serviços por domínio
- `migrations/`: Alembic (estrutura, triggers de auditoria e constraints de vigência)
