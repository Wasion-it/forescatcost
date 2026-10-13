# 06. Backlog Inicial e Histórias de Usuário

## 1. Épicos

| ID | Épico | Release |
|----|-------|---------|
| E01 | Fundação técnica (repositório, CI/CD, ambientes, SSO, RBAC, auditoria) | MVP |
| E02 | Cadastros de apoio | MVP |
| E03 | Parametrização (parâmetros, alíquotas, componentes) | MVP |
| E04 | Importações | MVP |
| E05 | Motor de cálculo e versionamento | MVP |
| E06 | Provisões e exportação Excel | MVP |
| E07 | Simulação de cenários | R1 |
| E08 | Dashboard | R1 (básico no MVP) |
| E09 | Fechamento de competência | R1 |
| E10 | Editor e governança de fórmulas | R1 |
| E11 | Integrações (PTAX, TecWin, ERP) | R2/R3 |
| E12 | Previsto × realizado | R3 |

## 2. Backlog priorizado

Prioridade MoSCoW: M = Must, S = Should, C = Could. Estimativa em pontos (Fibonacci), a refinar com o time.

| ID | Item | Épico | Prior. | Pts |
|----|------|-------|--------|-----|
| B01 | Setup de repositório, Docker, pre-commit, CI (lint, tipos, testes) | E01 | M | 5 |
| B02 | Autenticação SSO OIDC (front e back) | E01 | M | 8 |
| B03 | RBAC por permissões + mapeamento de perfis | E01 | M | 5 |
| B04 | Auditoria via trigger + tela de consulta | E01 | M | 8 |
| B05 | Cadastro de tipos de importação, moedas e cotações manuais | E02 | M | 3 |
| B06 | Cadastro de transportadoras, despachantes e terminais | E02 | M | 5 |
| B07 | Parâmetros com vigência (CRUD + validação de sobreposição) | E03 | M | 8 |
| B08 | Alíquotas por imposto e tipo, com vigência e origem | E03 | M | 5 |
| B09 | Componentes de custo e fórmulas iniciais (seed versão 1) | E03 | M | 5 |
| B10 | Cadastro e edição de importação com validações | E04 | M | 8 |
| B11 | Lista de importações com filtros e paginação | E04 | M | 5 |
| B12 | Cancelamento de importação | E04 | M | 2 |
| B13 | Avaliador seguro de expressões com Decimal | E05 | M | 8 |
| B14 | Pipeline de cálculo (ordenação, conversão, componentes, competência) | E05 | M | 13 |
| B15 | Golden tests com processos reais das planilhas | E05 | M | 8 |
| B16 | Gravação de versão, memória de cálculo e snapshot | E05 | M | 5 |
| B17 | Tela de detalhe com memória de cálculo e histórico de versões | E05 | M | 8 |
| B18 | Provisão mensal, por DI e por tipo (views + telas) | E06 | M | 8 |
| B19 | Exportação Excel dos relatórios | E06 | M | 5 |
| B20 | Dashboard básico (4 gráficos + KPIs) | E08 | S | 8 |
| B21 | Override de alíquota por processo com justificativa | E03 | S | 3 |
| B22 | Comparação entre versões de cálculo | E05 | S | 5 |
| B23 | Simulação de cenários + comparação | E07 | S | 8 |
| B24 | Recálculo em lote com análise de impacto | E05 | S | 8 |
| B25 | Fechamento e reabertura de competência | E09 | S | 8 |
| B26 | Editor de fórmulas com teste, aprovação e publicação | E10 | S | 13 |
| B27 | Estratégia de armazenagem por períodos/faixas (Chibatão) | E05 | S | 5 |
| B28 | Armazenagem aérea (após definição da regra) | E05 | S | 5 |
| B29 | Importação de cotações PTAX (API do BCB) | E11 | C | 5 |
| B30 | Itens/NCM por processo e alíquotas por NCM | E03 | C | 13 |
| B31 | Integração TecWinWeb (alíquotas) | E11 | C | 13 |
| B32 | Integração ERP (envio de provisão / recebimento de realizados) | E11 | C | 13 |
| B33 | Registro de realizados e relatório previsto × realizado | E12 | C | 13 |
| B34 | Suporte a CBS/IBS (reforma tributária) como novos impostos | E03 | S | 5 |
| B35 | Importação inicial de processos em aberto a partir das planilhas | E04 | M | 5 |

## 3. Histórias de usuário

### HU01: Cadastrar importação (B10)
Como analista do PCM, quero cadastrar um processo de importação com seus dados de DI, valores e logística, para que o sistema calcule a previsão sem planilha.

Critérios de aceite:
```gherkin
Cenário: Cadastro válido com cálculo
  Dado que estou autenticado como PCM
  E existem parâmetros vigentes para todos os componentes
  Quando preencho os campos obrigatórios e clico em "Salvar e calcular"
  Então o processo é salvo com status "CALCULADO"
  E vejo o total provisionado e a memória de cálculo por componente

Cenário: Moeda sem taxa
  Dado que a moeda da invoice é CNY
  Quando deixo a Taxa CNY em branco
  Então o sistema impede o salvamento e destaca o campo "Taxa CNY"

Cenário: DI duplicada
  Dado que já existe um processo com a DI "26/1234567-8"
  Quando informo a mesma DI em um novo processo
  Então o sistema bloqueia e exibe um link para o processo existente
```

### HU02: Calcular TCIF com regra do dia 15 (B14)
Como analista do PCM, quero que a TCIF seja provisionada no mês seguinte quando a DI for registrada após o dia 15, para que a provisão reflita o desembolso real.

```gherkin
Cenário: DI até o dia 15
  Dado uma DI com data 15/10/2026 e 10 itens
  Quando o processo é calculado
  Então a TCIF é R$ 695,00 (10 × 45,00 + 245,00)
  E a competência da TCIF é 10/2026

Cenário: DI após o dia 15
  Dado uma DI com data 16/10/2026
  Então a competência da TCIF é 11/2026

Cenário: Virada de ano
  Dado uma DI com data 20/12/2026
  Então a competência da TCIF é 01/2027
```

### HU03: Calcular despachante por tipo (B14)
Como analista do PCM, quero que o honorário do despachante seja aplicado conforme o tipo de importação, para não precisar lembrar os valores.

```gherkin
Cenário: Industrialização
  Dado um processo do tipo Industrialização
  Então o componente Despachante é R$ 715,00
Cenário: Uso e Consumo
  Dado um processo do tipo Uso e Consumo
  Então o componente Despachante é R$ 900,00
```

### HU04: Transportes local e secundário (B14)
Como analista do PCM, quero que os transportes sejam calculados por container mais um percentual sobre a carga, com valores da transportadora selecionada.

```gherkin
Cenário: Transporte secundário
  Dado 2 containers e valor da carga de R$ 200.000,00
  E os parâmetros de transporte secundário vigentes são R$ 1.000,00 e 0,01%
  Então o transporte secundário é R$ 2.020,00
```

### HU05: Memória de cálculo (B17)
Como analista do Financeiro, quero ver como cada valor foi calculado (fórmula, variáveis e parâmetros), para confiar na provisão e responder a auditorias.

```gherkin
Cenário: Visualizar memória
  Dado um processo calculado
  Quando abro a aba "Memória de cálculo"
  Então vejo, para cada componente, a expressão, os valores das variáveis, a origem das alíquotas e o resultado
```

### HU06: Histórico imutável (B16, B22)
Como analista do PCM, quero que cada recálculo gere uma nova versão sem apagar a anterior, para comparar e justificar mudanças.

```gherkin
Cenário: Recalcular após mudança de câmbio
  Dado um processo com versão 1 vigente
  Quando altero a Taxa USD e recalculo informando o motivo "Atualização PTAX"
  Então a versão 2 passa a ser a vigente
  E a versão 1 continua disponível no histórico
  E a comparação mostra a diferença por componente
```

### HU07: Parâmetro com vigência (B07)
Como analista do PCM, quero cadastrar um novo valor de TCIF com data de início, para que cálculos futuros usem o novo valor sem alterar os antigos.

```gherkin
Cenário: Nova vigência
  Dado que a TCIF por item é R$ 45,00 desde 01/01/2026
  Quando cadastro R$ 50,00 com vigência a partir de 01/11/2026
  Então a vigência anterior é encerrada em 31/10/2026
  E processos calculados antes não são alterados

Cenário: Sobreposição
  Quando tento cadastrar uma vigência que se sobrepõe a outra existente
  Então o sistema rejeita e informa o conflito
```

### HU08: Provisão mensal (B18)
Como analista do Financeiro, quero ver a provisão por mês de competência e componente, para planejar o caixa.

```gherkin
Cenário: Consolidação
  Dado processos calculados com competências 10/2026 e 11/2026
  Quando consulto a provisão de 10/2026 a 12/2026
  Então vejo uma tabela competência × componente com totais
  E processos cancelados e simulações não são considerados
  E o CIF não soma no total
```

### HU09: Exportar Excel (B19)
Como analista do Financeiro, quero exportar a provisão para Excel, para anexar em reportes e conciliações.

```gherkin
Cenário: Exportação
  Dado uma consulta de provisão com filtros aplicados
  Quando clico em "Exportar Excel"
  Então recebo um .xlsx com as mesmas linhas da tela
  E os valores são numéricos com formato monetário
  E o cabeçalho traz filtros, data/hora e usuário de emissão
```

### HU10: Simular cenário (B23)
Como analista do PCM ou do Financeiro, quero simular variações de câmbio e alíquotas, para avaliar o impacto antes de decidir.

```gherkin
Cenário: Simulação sem efeito na provisão
  Dado um processo calculado
  Quando simulo a Taxa USD +10%
  Então vejo a comparação vigente × cenário por componente
  E a provisão do processo não é alterada
```

### HU11: Fechar competência (B25)
Como analista do Financeiro, quero fechar a competência do mês, para congelar a provisão informada à contabilidade.

```gherkin
Cenário: Fechamento
  Dado a competência 10/2026 aberta
  Quando fecho a competência
  Então é gravado um snapshot da provisão
  E alterações em processos com valores em 10/2026 ficam bloqueadas

Cenário: Reabertura
  Dado a competência 10/2026 fechada
  Quando um usuário autorizado reabre informando o motivo
  Então a reabertura é auditada e o snapshot anterior é preservado
```

### HU12: Auditoria (B04)
Como administrador, quero consultar quem alterou cada dado e quando, com valores antes e depois, para atender a auditorias internas.

### HU13: Gestão de usuários (B03)
Como administrador, quero atribuir perfis aos usuários, para controlar o acesso por função.

### HU14: Publicar fórmula com aprovação (B26)
Como administrador, quero alterar a fórmula de um componente, testá-la com casos reais e publicá-la após aprovação de outra pessoa, para mudar regras com segurança.

```gherkin
Cenário: Teste falhando bloqueia publicação
  Dado uma nova versão da fórmula do CIF
  Quando algum caso de teste diverge do esperado
  Então a opção "Enviar para aprovação" fica desabilitada

Cenário: Segregação de funções
  Dado que submeti a fórmula
  Então não posso aprová-la com meu próprio usuário
```

### HU15: Dashboard (B20)
Como gestor do Financeiro, quero visualizar importações por mês, valor provisionado, valor por tipo e evolução mensal, para acompanhar os custos de importação.

## 4. Definition of Ready / Done

DoR: história com critérios de aceite, regras de negócio confirmadas (sem pontos em aberto bloqueantes), dados de exemplo e estimativa.

DoD: código revisado (PR aprovado), testes automatizados passando (incluindo golden tests), cobertura mínima atendida, migração Alembic revisada, documentação/ADR atualizada, auditoria cobrindo as novas tabelas, implantado em HML e validado pelo PO.
